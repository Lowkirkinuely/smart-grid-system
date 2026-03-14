import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def _call_llm(system_prompt: str, user_content: str) -> dict:
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=0.1,
        max_tokens=500
    )
    raw = response.choices[0].message.content.strip()
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            if part.startswith("json"):
                raw = part[4:].strip()
                break
            elif "{" in part:
                raw = part.strip()
                break
    return json.loads(raw.strip())


def intake_agent(grid_data: dict) -> dict:
    """Preprocesses and validates raw grid data — no LLM needed."""
    deficit = grid_data["demand"] - grid_data["supply"]
    load_ratio = grid_data["demand"] / grid_data["supply"] if grid_data["supply"] > 0 else 999
    return {
        "deficit_mw": round(deficit, 2),
        "load_ratio": round(load_ratio, 3),
        "is_overloaded": deficit > 0,
        "heatwave_active": grid_data["temperature"] > 40,
        "protected_count": len([z for z in grid_data["zones"] if z.get("protected")]),
        "total_zones": len(grid_data["zones"]),
        "validated": True
    }


def grid_health_agent(grid_data: dict, intake: dict) -> dict:
    system = """You are a power grid stability engineer specializing in fault analysis and cascading failure prevention.
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
    return _call_llm(system, user)


def demand_agent(grid_data: dict, intake: dict) -> dict:
    system = """You are a power demand forecasting specialist with expertise in heatwave-driven consumption spikes.
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
    return _call_llm(system, user)


def disaster_agent(grid_data: dict, intake: dict) -> dict:
    system = """You are a disaster risk analyst for critical power infrastructure covering heatwaves, storms, and cascading failures.
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
        f"Deficit: {intake['deficit_mw']}MW. "
        f"High temps stress transformers and increase wildfire/equipment failure risk."
    )
    return _call_llm(system, user)


def priority_agent(grid_data: dict, grid_health: dict, demand: dict, disaster: dict) -> dict:
    system = """You are a critical infrastructure protection coordinator determining zone shutdown priority.
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
    protected = [z for z in grid_data["zones"] if z.get("protected")]
    non_protected = [z for z in grid_data["zones"] if not z.get("protected")]
    user = (
        f"Protected (MUST stay on): {json.dumps(protected)}, "
        f"Non-protected (can cut): {json.dumps(non_protected)}, "
        f"Fault risk: {grid_health.get('fault_risk', 'unknown')}, "
        f"Demand trend: {demand.get('demand_trend', 'unknown')}, "
        f"Disaster risk: {disaster.get('disaster_risk', 'unknown')}, "
        f"Supply: {grid_data['supply']}MW, Demand: {grid_data['demand']}MW"
    )
    return _call_llm(system, user)