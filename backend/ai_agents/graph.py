from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional
from dotenv import load_dotenv
from .agents import grid_health_agent, demand_agent, disaster_agent, priority_agent

load_dotenv()

# ── State definition ──────────────────────────────────────────────────────────

class GridAnalysisState(TypedDict):
    grid_data: dict
    grid_health: Optional[dict]
    demand_analysis: Optional[dict]
    disaster_risk: Optional[dict]
    priority_status: Optional[dict]
    final_analysis: Optional[dict]

# ── Node functions ────────────────────────────────────────────────────────────

def node_grid_health(state: GridAnalysisState) -> GridAnalysisState:
    print("[Agent] Running Grid Health Agent...")
    result = grid_health_agent(state["grid_data"])
    return {**state, "grid_health": result}


def node_demand(state: GridAnalysisState) -> GridAnalysisState:
    print("[Agent] Running Demand Agent...")
    result = demand_agent(state["grid_data"])
    return {**state, "demand_analysis": result}


def node_disaster(state: GridAnalysisState) -> GridAnalysisState:
    print("[Agent] Running Disaster Agent...")
    result = disaster_agent(state["grid_data"])
    return {**state, "disaster_risk": result}


def node_priority(state: GridAnalysisState) -> GridAnalysisState:
    print("[Agent] Running Priority Agent...")
    result = priority_agent(state["grid_data"])
    return {**state, "priority_status": result}


def node_synthesize(state: GridAnalysisState) -> GridAnalysisState:
    """Combines all agent outputs into one final analysis."""
    print("[Agent] Synthesizing results...")
    
    gh = state.get("grid_health") or {}
    da = state.get("demand_analysis") or {}
    dr = state.get("disaster_risk") or {}
    ps = state.get("priority_status") or {}

    # Determine overall risk level
    risk_levels = {
        "low": 0, "medium": 1, "high": 2, "critical": 3
    }
    risks = [
        gh.get("risk", "low"),
        dr.get("disaster_risk", "low")
    ]
    overall_risk = max(risks, key=lambda r: risk_levels.get(r, 0))

    # Build recommendations list
    recommendations = []
    if gh.get("overload"):
        recommendations.append("Immediate load shedding required — grid is overloaded")
    if da.get("spike_detected"):
        recommendations.append("Demand spike detected — prepare rotation plan now")
    if dr.get("recommended_action"):
        recommendations.append(dr["recommended_action"])
    if ps.get("protection_strategy"):
        recommendations.append(ps["protection_strategy"])
    if not recommendations:
        recommendations.append("Grid is stable — no immediate action needed")

    final = {
        "risk_level": overall_risk,
        "risk_reason": gh.get("analysis", "No analysis available"),
        "recommendations": recommendations,
        "demand_trend": da.get("demand_trend", "stable"),
        "spike_detected": da.get("spike_detected", False),
        "disaster_risk": dr.get("disaster_risk", "low"),
        "risk_factors": dr.get("risk_factors", []),
        "protected_zones_safe": ps.get("protected_zones_safe", True),
        "critical_zones": ps.get("critical_zones", []),
        "load_percentage": gh.get("load_percentage", 0)
    }

    return {**state, "final_analysis": final}

# ── Build graph ───────────────────────────────────────────────────────────────

def build_graph():
    workflow = StateGraph(GridAnalysisState)

    workflow.add_node("grid_health", node_grid_health)
    workflow.add_node("demand_agent", node_demand)
    workflow.add_node("disaster_agent", node_disaster)
    workflow.add_node("priority_agent", node_priority)
    workflow.add_node("synthesize", node_synthesize)

    # Sequential pipeline
    workflow.set_entry_point("grid_health")
    workflow.add_edge("grid_health", "demand_agent")
    workflow.add_edge("demand_agent", "disaster_agent")
    workflow.add_edge("disaster_agent", "priority_agent")
    workflow.add_edge("priority_agent", "synthesize")
    workflow.add_edge("synthesize", END)

    return workflow.compile()


graph = build_graph()


def run_analysis(grid_data: dict) -> dict:
    """Entry point — run full agent pipeline on grid data."""
    initial_state: GridAnalysisState = {
        "grid_data": grid_data,
        "grid_health": None,
        "demand_analysis": None,
        "disaster_risk": None,
        "priority_status": None,
        "final_analysis": None,
    }
    result = graph.invoke(initial_state)
    return result["final_analysis"]