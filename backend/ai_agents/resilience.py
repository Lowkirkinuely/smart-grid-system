"""
Resilience utilities for Smart Grid AI agents.
Replaces ad-hoc try/except in graph.py with structured timeout,
fallback, logging, and confidence degradation.
"""

import logging
from typing import Dict, Any, Callable, Optional, Tuple
from functools import wraps

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 15
FALLBACK_CONFIDENCE     = 0.3


# ── Per-agent fallback dicts ───────────────────────────────────────────────────
# These must match the exact shape expected by node_synthesize in graph.py

AGENT_FALLBACKS: Dict[str, Dict[str, Any]] = {
    "grid_health": {
        "overload":               True,
        "load_percentage":        0.0,
        "fault_risk":             "medium",
        "cascading_failure_risk": False,
        "stability_score":        50.0,
        "analysis":               "Grid health agent unavailable",
        "confidence":             FALLBACK_CONFIDENCE
    },
    "demand": {
        "demand_trend":           "unknown",
        "spike_detected":         False,
        "spike_severity":         "none",
        "temperature_impact_mw":  0.0,
        "forecast_next_hour":     "unavailable",
        "recommended_reserve_mw": 0.0,
        "confidence":             FALLBACK_CONFIDENCE
    },
    "disaster": {
        "disaster_risk":          "medium",
        "risk_factors":           ["data unavailable"],
        "infrastructure_threat":  False,
        "recommended_action":     "Manual assessment required",
        "time_to_act_minutes":    30,
        "confidence":             FALLBACK_CONFIDENCE
    },
    "priority": {
        "protected_zones_safe":   True,
        "critical_zones":         [],
        "at_risk_zones":          [],
        "safe_to_cut_zones":      [],
        "protection_strategy":    "Priority agent unavailable",
        "estimated_relief_mw":    0.0,
        "confidence":             FALLBACK_CONFIDENCE
    },
    "ml": {
        "ml_risk_level":          "unknown",
        "ml_confidence":          0.0,
        "ml_probabilities":       {"low": 0.0, "medium": 0.0, "high": 0.0, "critical": 0.0},
        "anomaly_detected":       False,
        "anomaly_score":          0.0,
        "top_risk_features":      [],
        "training_samples":       0,
        "patterns_learned":       False
    }
}


def get_fallback(agent_name: str) -> Dict[str, Any]:
    """Returns the fallback dict for a named agent. Logs a warning."""
    fallback = AGENT_FALLBACKS.get(agent_name, AGENT_FALLBACKS["grid_health"])
    logger.warning(f"[RESILIENCE] Using fallback for agent '{agent_name}'")
    return dict(fallback)   # return a copy so it's never mutated


# ── Core safe_run used by graph.py nodes ──────────────────────────────────────

def safe_run(
    agent_fn:   Callable,
    *args,
    agent_name: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Wraps a synchronous agent function call with:
    - Exception isolation (one agent failure never kills the pipeline)
    - Timeout detection (via httpx timeout raised inside Groq client)
    - Structured error message returned alongside None result
    - Logging at correct severity

    Returns:
        (result_dict, None)       — on success
        (None, error_message)     — on any failure

    Usage in graph.py:
        result, err = safe_run(grid_health_agent, grid_data, intake, agent_name="GridHealthAgent")
        if result is None:
            result = get_fallback("grid_health")
    """
    try:
        result = agent_fn(*args)
        if result is None:
            raise ValueError(f"{agent_name} returned None")
        logger.debug(f"[RESILIENCE] {agent_name} completed successfully")
        return result, None

    except TimeoutError:
        msg = f"{agent_name} timed out after {DEFAULT_TIMEOUT_SECONDS}s"
        logger.error(f"[RESILIENCE] ⏱ {msg}")
        print(f"\033[91m  ✗ [{agent_name}] TIMEOUT — using fallback\033[0m")
        return None, msg

    except ValueError as e:
        msg = f"{agent_name} returned invalid JSON: {e}"
        logger.error(f"[RESILIENCE] 🔴 {msg}")
        print(f"\033[91m  ✗ [{agent_name}] JSON ERROR — using fallback\033[0m")
        return None, msg

    except Exception as e:
        msg = f"{agent_name} unexpected error: {type(e).__name__}: {e}"
        logger.error(f"[RESILIENCE] 🔴 {msg}")
        print(f"\033[91m  ✗ [{agent_name}] ERROR — using fallback\033[0m")
        return None, msg


# ── Confidence calculation ─────────────────────────────────────────────────────

def calculate_fused_confidence(
    llm_confidences: list,
    ml_confidence:   float,
    error_count:     int,
    llm_weight:      float = 0.6,
    ml_weight:       float = 0.4,
    penalty_per_error: float = 0.05
) -> float:
    """
    Computes weighted average confidence across LLM agents and ML model.
    Penalises by number of failed agents.

    Args:
        llm_confidences:   List of confidence scores from LLM agents (0.0–1.0)
        ml_confidence:     Confidence from ML RandomForest model (0.0–1.0)
        error_count:       Number of agents that failed/used fallback
        llm_weight:        Weight given to LLM average (default 0.6)
        ml_weight:         Weight given to ML confidence (default 0.4)
        penalty_per_error: Confidence penalty per failed agent (default 0.05)

    Returns:
        Fused confidence float clamped to [0.0, 1.0]
    """
    if not llm_confidences:
        llm_avg = FALLBACK_CONFIDENCE
    else:
        llm_avg = sum(llm_confidences) / len(llm_confidences)

    fused   = (llm_avg * llm_weight) + (ml_confidence * ml_weight)
    penalty = error_count * penalty_per_error
    result  = max(0.0, min(1.0, fused - penalty))

    logger.debug(
        f"[RESILIENCE] Confidence: llm_avg={llm_avg:.2f} ml={ml_confidence:.2f} "
        f"errors={error_count} penalty={penalty:.2f} fused={result:.2f}"
    )
    return round(result, 2)


# ── Risk level utilities ───────────────────────────────────────────────────────

RISK_ORDER:   Dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}
RISK_REVERSE: Dict[int, str] = {0: "low", 1: "medium", 2: "high", 3: "critical"}


def max_risk(*risk_levels: str) -> str:
    """Returns the highest risk level from a list of risk strings."""
    return max(risk_levels, key=lambda r: RISK_ORDER.get(r, 0))


def fuse_risk(llm_risk: str, ml_risk: str,
              llm_weight: float = 0.6, ml_weight: float = 0.4) -> str:
    """
    Weighted fusion of LLM and ML risk levels.
    Falls back to LLM risk if ML is unknown.
    """
    if ml_risk == "unknown":
        return llm_risk

    llm_score  = RISK_ORDER.get(llm_risk, 0) * llm_weight
    ml_score   = RISK_ORDER.get(ml_risk, 0)  * ml_weight
    fused_idx  = round(llm_score + ml_score)
    fused_idx  = max(0, min(3, fused_idx))
    return RISK_REVERSE[fused_idx]


def check_disagreement(llm_risk: str, ml_risk: str, threshold: int = 2) -> bool:
    """
    Returns True if ML and LLM differ by threshold or more risk levels.
    A gap of 2 means e.g. ML says critical (3), LLM says low (1) — force HITL.
    """
    if ml_risk == "unknown":
        return False
    gap = abs(RISK_ORDER.get(llm_risk, 0) - RISK_ORDER.get(ml_risk, 0))
    return gap >= threshold


def should_escalate_for_anomaly(current_risk: str, anomaly_detected: bool) -> str:
    """
    If anomaly detected and risk is currently low or medium, escalate to high.
    Protects against ML missing a novel pattern.
    """
    if anomaly_detected and RISK_ORDER.get(current_risk, 0) < 2:
        logger.warning("[RESILIENCE] Anomaly detected — escalating risk to HIGH")
        print(f"\033[33m  ⚠️  Anomaly detected — escalating {current_risk} → high\033[0m")
        return "high"
    return current_risk