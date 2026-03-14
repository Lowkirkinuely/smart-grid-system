"""
AI agents for Smart Grid Human-in-the-Loop system.
Class-based structure with LLM analysis, explicit fallbacks, and logging.
"""

import os
import json
import logging
import httpx
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# httpx client with hard timeout — Groq hangs without this
_http_client = httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0))
client       = Groq(api_key=os.getenv("GROQ_API_KEY"), http_client=_http_client)


# ── Core LLM caller ────────────────────────────────────────────────────────────

def _call_llm(system_prompt: str, user_content: str) -> dict:
    """
    Single entry point for all Groq LLM calls.
    Handles markdown fence stripping and JSON parse errors.
    Raises TimeoutError or ValueError — caught by safe_run in resilience2.py.
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile"
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content}
            ],
            temperature=0.1,
            max_tokens=500
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned empty content")
        raw = content.strip()

        # Strip markdown fences if model wraps response
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    raw = part[4:].strip()
                    break
                elif part.startswith("{"):
                    raw = part.strip()
                    break

        return json.loads(raw.strip())

    except httpx.TimeoutException:
        raise TimeoutError("Groq API timed out after 15s")
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e} | Raw: {raw[:200]}")


# ── IntakeAgent ────────────────────────────────────────────────────────────────

class IntakeAgent:
    """Pure Python preprocessing — no LLM. Validates and enriches raw grid data."""

    @staticmethod
    def validate(grid_data: dict) -> dict:
        """Validates input and computes derived fields."""

        # Input sanity warnings
        if grid_data.get("demand", 0) < 0:
            logger.warning("[INTAKE] Invalid demand value (negative)")
        if grid_data.get("supply", 0) < 0:
            logger.warning("[INTAKE] Invalid supply value (negative)")
        temp = grid_data.get("temperature", 20)
        if temp < -60 or temp > 60:
            logger.warning(f"[INTAKE] Unusual temperature: {temp}°C")

        demand     = grid_data["demand"]
        supply     = grid_data["supply"]
        deficit    = demand - supply
        load_ratio = demand / supply if supply > 0 else 999.0

        result = {
            "deficit_mw":      round(deficit, 2),
            "load_ratio":      round(load_ratio, 3),
            "is_overloaded":   deficit > 0,
            "heatwave_active": temp > 40,
            "protected_count": len([z for z in grid_data["zones"] if z.get("protected")]),
            "total_zones":     len(grid_data["zones"]),
            "validated":       True
        }

        logger.info(
            f"[INTAKE] Validated | D: {demand}MW S: {supply}MW "
            f"Deficit: {deficit}MW Heatwave: {result['heatwave_active']}"
        )
        return result


# ── GridHealthAgent ────────────────────────────────────────────────────────────

class GridHealthAgent:
    """Analyzes grid stability, fault risk, and cascading failure probability."""

    @staticmethod
    def analyze(grid_data: dict, intake: dict) -> dict:
        """LLM-powered stability analysis. Raises on failure — caught by safe_run."""
        system = """You are a power grid stability engineer specializing in fault analysis.
Respond ONLY in valid JSON, no markdown, no extra text:
{
    "overload": true or false,
    "load_percentage": number 0-200,
    "fault_risk": "low" or "medium" or "high" or "critical",
    "cascading_failure_risk": true or false,
    "stability_score": number 0-100,
    "analysis": "one concise technical sentence",
    "confidence": number 0.0-1.0
}"""
        user = (
            f"Load ratio: {intake['load_ratio']}, "
            f"Deficit: {intake['deficit_mw']}MW, "
            f"Demand: {grid_data['demand']}MW, "
            f"Supply: {grid_data['supply']}MW, "
            f"Temperature: {grid_data['temperature']}C, "
            f"Overloaded: {intake['is_overloaded']}"
        )
        result = _call_llm(system, user)
        logger.info(
            f"[GRID HEALTH] Fault: {result.get('fault_risk')} | "
            f"Stability: {result.get('stability_score')}/100 | "
            f"Cascading: {result.get('cascading_failure_risk')}"
        )
        return result

    @staticmethod
    def fallback(intake: dict) -> dict:
        """Rule-based fallback when LLM is unavailable."""
        load_pct = round(intake.get("load_ratio", 1.0) * 100, 1)
        overload = intake.get("is_overloaded", False)
        fault    = "high" if overload else "medium"
        score    = max(0, 100 - load_pct) if load_pct <= 100 else 0

        result = {
            "overload":               overload,
            "load_percentage":        load_pct,
            "fault_risk":             fault,
            "cascading_failure_risk": overload and load_pct > 110,
            "stability_score":        round(score, 1),
            "analysis":               "Grid health agent unavailable — rule-based fallback",
            "confidence":             0.3
        }
        logger.warning("[GRID HEALTH] Using rule-based fallback")
        return result


# ── DemandAgent ────────────────────────────────────────────────────────────────

class DemandAgent:
    """Forecasts consumption trends and detects demand spikes."""

    @staticmethod
    def analyze(grid_data: dict, intake: dict) -> dict:
        """LLM-powered demand forecasting. Raises on failure — caught by safe_run."""
        system = """You are a power demand forecasting specialist.
Respond ONLY in valid JSON, no markdown, no extra text:
{
    "demand_trend": "rising" or "stable" or "falling",
    "spike_detected": true or false,
    "spike_severity": "none" or "minor" or "major" or "extreme",
    "temperature_impact_mw": number,
    "forecast_next_hour": "brief forecast under 10 words",
    "recommended_reserve_mw": number,
    "confidence": number 0.0-1.0
}"""
        user = (
            f"Temperature: {grid_data['temperature']}C, "
            f"Heatwave: {intake['heatwave_active']}, "
            f"Demand: {grid_data['demand']}MW, "
            f"Supply: {grid_data['supply']}MW, "
            f"Zones: {json.dumps(grid_data['zones'])}"
        )
        result = _call_llm(system, user)
        logger.info(
            f"[DEMAND] Trend: {result.get('demand_trend')} | "
            f"Spike: {result.get('spike_detected')} | "
            f"Severity: {result.get('spike_severity')}"
        )
        return result

    @staticmethod
    def fallback(intake: dict, grid_data: dict) -> dict:
        """Rule-based fallback when LLM is unavailable."""
        heatwave = intake.get("heatwave_active", False)
        overload = intake.get("is_overloaded", False)
        spike    = heatwave or overload

        result = {
            "demand_trend":           "rising" if spike else "stable",
            "spike_detected":         spike,
            "spike_severity":         "major" if heatwave else ("minor" if overload else "none"),
            "temperature_impact_mw":  round(grid_data["demand"] * 0.15, 1) if heatwave else 0.0,
            "forecast_next_hour":     "Demand likely to increase" if spike else "Demand stable",
            "recommended_reserve_mw": round(grid_data["supply"] * 0.1, 1),
            "confidence":             0.3
        }
        logger.warning("[DEMAND] Using rule-based fallback")
        return result


# ── DisasterAgent ──────────────────────────────────────────────────────────────

class DisasterAgent:
    """Evaluates environmental and disaster risk factors."""

    @staticmethod
    def analyze(grid_data: dict, intake: dict) -> dict:
        """LLM-powered disaster risk assessment. Raises on failure — caught by safe_run."""
        system = """You are a disaster risk analyst for critical power infrastructure.
Respond ONLY in valid JSON, no markdown, no extra text:
{
    "disaster_risk": "low" or "medium" or "high" or "critical",
    "risk_factors": ["factor1", "factor2"],
    "infrastructure_threat": true or false,
    "recommended_action": "one sentence action",
    "time_to_act_minutes": number,
    "confidence": number 0.0-1.0
}"""
        user = (
            f"Temperature: {grid_data['temperature']}C, "
            f"Heatwave: {intake['heatwave_active']}, "
            f"Grid overloaded: {intake['is_overloaded']}, "
            f"Deficit: {intake['deficit_mw']}MW."
        )
        result = _call_llm(system, user)
        logger.info(
            f"[DISASTER] Risk: {result.get('disaster_risk')} | "
            f"Time to Act: {result.get('time_to_act_minutes')}min"
        )
        return result

    @staticmethod
    def fallback(intake: dict, grid_data: dict) -> dict:
        """Rule-based fallback when LLM is unavailable."""
        temp     = grid_data.get("temperature", 20)
        heatwave = intake.get("heatwave_active", False)
        overload = intake.get("is_overloaded", False)

        if temp > 45:
            risk, factors, time_min = "critical", ["extreme heatwave", "equipment stress"], 15
        elif heatwave and overload:
            risk, factors, time_min = "high", ["heatwave", "grid overload"], 30
        elif heatwave or overload:
            risk, factors, time_min = "medium", ["heatwave" if heatwave else "grid stress"], 60
        else:
            risk, factors, time_min = "low", ["normal conditions"], 120

        result = {
            "disaster_risk":         risk,
            "risk_factors":          factors,
            "infrastructure_threat": risk in ["high", "critical"],
            "recommended_action":    "Manual assessment required — fallback mode",
            "time_to_act_minutes":   time_min,
            "confidence":            0.3
        }
        logger.warning(f"[DISASTER] Using rule-based fallback | Risk: {risk}")
        return result


# ── PriorityAgent ──────────────────────────────────────────────────────────────

class PriorityAgent:
    """Determines zone protection hierarchy — what's safe to cut."""

    @staticmethod
    def analyze(grid_data: dict, grid_health: dict, demand: dict, disaster: dict) -> dict:
        """LLM-powered zone prioritization. Raises on failure — caught by safe_run."""
        system = """You are a critical infrastructure protection coordinator.
Respond ONLY in valid JSON, no markdown, no extra text:
{
    "protected_zones_safe": true or false,
    "critical_zones": ["zone_name"],
    "at_risk_zones": ["zone_name"],
    "safe_to_cut_zones": ["zone_name"],
    "protection_strategy": "one sentence strategy",
    "estimated_relief_mw": number,
    "confidence": number 0.0-1.0
}"""
        protected     = [z for z in grid_data["zones"] if z.get("protected")]
        non_protected = [z for z in grid_data["zones"] if not z.get("protected")]
        user = (
            f"Protected (MUST stay on): {json.dumps(protected)}, "
            f"Non-protected (can cut): {json.dumps(non_protected)}, "
            f"Fault risk: {grid_health.get('fault_risk', 'unknown')}, "
            f"Demand trend: {demand.get('demand_trend', 'unknown')}, "
            f"Disaster risk: {disaster.get('disaster_risk', 'unknown')}, "
            f"Supply: {grid_data['supply']}MW, Demand: {grid_data['demand']}MW"
        )
        result = _call_llm(system, user)
        logger.info(
            f"[PRIORITY] Safe to cut: {result.get('safe_to_cut_zones')} | "
            f"Relief: {result.get('estimated_relief_mw')}MW"
        )
        return result

    @staticmethod
    def fallback(grid_data: dict) -> dict:
        """Rule-based fallback — never cut protected zones, everything else fair game."""
        protected     = [z["name"] for z in grid_data["zones"] if z.get("protected")]
        non_protected = [z["name"] for z in grid_data["zones"] if not z.get("protected")]
        relief_mw     = sum(z["demand"] for z in grid_data["zones"] if not z.get("protected"))

        result = {
            "protected_zones_safe":  True,
            "critical_zones":        protected,
            "at_risk_zones":         [],
            "safe_to_cut_zones":     non_protected,
            "protection_strategy":   "Priority agent unavailable — protecting all critical zones by default",
            "estimated_relief_mw":   round(relief_mw, 1),
            "confidence":            0.3
        }
        logger.warning("[PRIORITY] Using rule-based fallback")
        return result


# ── MLAgent ────────────────────────────────────────────────────────────────────

class MLAgent:
    """Wraps the ML model (RandomForest + IsolationForest) as an agent-style class."""

    @staticmethod
    def analyze(grid_data: dict) -> dict:
        """Runs ML prediction. Raises on failure — caught by graph node."""
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from ml.model import ml_model

        result = ml_model.predict(grid_data)
        logger.info(
            f"[ML AGENT] Risk: {result['ml_risk_level']} | "
            f"Confidence: {result['ml_confidence']} | "
            f"Anomaly: {result['anomaly_detected']} | "
            f"Samples: {result['training_samples']}"
        )
        return result

    @staticmethod
    def fallback() -> dict:
        """Returns safe fallback when ML model is unavailable."""
        logger.warning("[ML AGENT] Using fallback — model unavailable")
        return {
            "ml_risk_level":     "unknown",
            "ml_confidence":     0.0,
            "ml_probabilities":  {"low": 0.0, "medium": 0.0, "high": 0.0, "critical": 0.0},
            "anomaly_detected":  False,
            "anomaly_score":     0.0,
            "top_risk_features": [],
            "training_samples":  0,
            "patterns_learned":  False
        }
