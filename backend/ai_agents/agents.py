import os
import json
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def _call_llm(system_prompt: str, user_content: str) -> dict:
    """Base LLM caller — strips markdown, parses JSON."""
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=0.1
    )
    raw = response.choices[0].message.content.strip()
    # Strip markdown code fences if model adds them
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def grid_health_agent(grid_data: dict) -> dict:
    """Detects overload conditions and grid stress."""
    system = """You are a power grid health analyst.
    Analyze the grid load and respond ONLY in valid JSON, no markdown, no extra text:
    {
        "overload": true or false,
        "load_percentage": number between 0 and 200,
        "risk": "low" or "medium" or "high" or "critical",
        "analysis": "one sentence explanation"
    }"""
    
    deficit = grid_data["demand"] - grid_data["supply"]
    user = (
        f"Demand: {grid_data['demand']}MW, "
        f"Supply: {grid_data['supply']}MW, "
        f"Deficit: {deficit}MW, "
        f"Temperature: {grid_data['temperature']}C"
    )
    return _call_llm(system, user)


def demand_agent(grid_data: dict) -> dict:
    """Predicts demand trends based on temperature and zone data."""
    system = """You are a power demand forecasting analyst.
    Respond ONLY in valid JSON, no markdown:
    {
        "demand_trend": "rising" or "stable" or "falling",
        "spike_detected": true or false,
        "temperature_impact": "brief description",
        "forecast_next_hour": "brief forecast"
    }"""
    
    user = (
        f"Temperature: {grid_data['temperature']}C, "
        f"Current demand: {grid_data['demand']}MW, "
        f"Zones: {json.dumps(grid_data['zones'])}"
    )
    return _call_llm(system, user)


def disaster_agent(grid_data: dict) -> dict:
    """Evaluates environmental and disaster risk."""
    system = """You are a disaster risk analyst for power infrastructure.
    Respond ONLY in valid JSON, no markdown:
    {
        "disaster_risk": "low" or "medium" or "high",
        "risk_factors": ["factor1", "factor2"],
        "recommended_action": "one sentence action"
    }"""
    
    user = (
        f"Temperature: {grid_data['temperature']}C, "
        f"Demand: {grid_data['demand']}MW, "
        f"Supply: {grid_data['supply']}MW. "
        f"High temperature indicates heatwave risk."
    )
    return _call_llm(system, user)


def priority_agent(grid_data: dict) -> dict:
    """Ensures critical infrastructure stays protected."""
    system = """You are a critical infrastructure protection analyst.
    Respond ONLY in valid JSON, no markdown:
    {
        "protected_zones_safe": true or false,
        "critical_zones": ["zone_name"],
        "at_risk_zones": ["zone_name"],
        "protection_strategy": "one sentence strategy"
    }"""
    
    protected = [z for z in grid_data["zones"] if z.get("protected", False)]
    non_protected = [z for z in grid_data["zones"] if not z.get("protected", False)]
    
    user = (
        f"Protected zones (must stay on): {json.dumps(protected)}, "
        f"Non-protected zones (can be cut): {json.dumps(non_protected)}, "
        f"Available supply: {grid_data['supply']}MW"
    )
    return _call_llm(system, user)