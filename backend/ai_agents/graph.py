from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from typing import TypedDict, Optional
from dotenv import load_dotenv
from .agents import (
    intake_agent, grid_health_agent,
    demand_agent, disaster_agent, priority_agent
)

load_dotenv()

# ── State ──────────────────────────────────────────────────────────────────────

class GridAnalysisState(TypedDict):
    grid_data: dict
    intake: Optional[dict]
    # Written by 3 parallel nodes
    grid_health: Optional[dict]
    demand_analysis: Optional[dict]
    disaster_risk: Optional[dict]
    # Written after parallel join
    priority_status: Optional[dict]
    final_analysis: Optional[dict]
    # HITL
    requires_human_approval: bool
    human_decision: Optional[dict]

# ── Node functions ─────────────────────────────────────────────────────────────

def node_intake(state: GridAnalysisState) -> dict:
    print("\n\033[94m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m")
    print("\033[94m  🔵 [INTAKE AGENT] Preprocessing grid data...\033[0m")
    result = intake_agent(state["grid_data"])
    print(f"\033[94m  ✓ Deficit: {result['deficit_mw']}MW | Overloaded: {result['is_overloaded']} | Heatwave: {result['heatwave_active']}\033[0m")
    return {"intake": result}


def node_grid_health(state: GridAnalysisState) -> dict:
    print("\033[93m  ⚡ [GRID HEALTH AGENT] Analyzing stability & fault risk...\033[0m")
    result = grid_health_agent(state["grid_data"], state["intake"])
    print(f"\033[93m  ✓ Fault Risk: {result.get('fault_risk')} | Stability Score: {result.get('stability_score')}/100 | Cascading: {result.get('cascading_failure_risk')}\033[0m")
    return {"grid_health": result}


def node_demand(state: GridAnalysisState) -> dict:
    print("\033[92m  📈 [DEMAND AGENT] Forecasting consumption trends...\033[0m")
    result = demand_agent(state["grid_data"], state["intake"])
    print(f"\033[92m  ✓ Trend: {result.get('demand_trend')} | Spike: {result.get('spike_detected')} | Severity: {result.get('spike_severity')}\033[0m")
    return {"demand_analysis": result}


def node_disaster(state: GridAnalysisState) -> dict:
    print("\033[91m  🌩️  [DISASTER AGENT] Evaluating environmental risks...\033[0m")
    result = disaster_agent(state["grid_data"], state["intake"])
    print(f"\033[91m  ✓ Disaster Risk: {result.get('disaster_risk')} | Time to Act: {result.get('time_to_act_minutes')}min\033[0m")
    return {"disaster_risk": result}


def node_priority(state: GridAnalysisState) -> dict:
    print("\033[95m  🏥 [PRIORITY AGENT] Determining zone protection hierarchy...\033[0m")
    result = priority_agent(
        state["grid_data"],
        state.get("grid_health") or {},
        state.get("demand_analysis") or {},
        state.get("disaster_risk") or {}
    )
    print(f"\033[95m  ✓ Safe to Cut: {result.get('safe_to_cut_zones')} | Relief: {result.get('estimated_relief_mw')}MW\033[0m")
    return {"priority_status": result}


def node_synthesize(state: GridAnalysisState) -> dict:
    print("\033[96m  🧠 [SYNTHESIZER] Aggregating all agent outputs...\033[0m")

    gh = state.get("grid_health") or {}
    da = state.get("demand_analysis") or {}
    dr = state.get("disaster_risk") or {}
    ps = state.get("priority_status") or {}
    intake = state.get("intake") or {}

    risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    risks = [gh.get("fault_risk", "low"), dr.get("disaster_risk", "low")]
    overall_risk = max(risks, key=lambda r: risk_order.get(r, 0))

    # Escalate to critical if cascading failure is imminent
    if gh.get("cascading_failure_risk") and overall_risk == "high":
        overall_risk = "critical"

    confidences = [
        gh.get("confidence", 0.7),
        da.get("confidence", 0.7),
        dr.get("confidence", 0.7),
        ps.get("confidence", 0.7)
    ]
    avg_confidence = round(sum(confidences) / len(confidences), 2)

    recommendations = []
    if gh.get("overload"):
        recommendations.append("⚡ Immediate load shedding required — grid is overloaded")
    if da.get("spike_detected"):
        recommendations.append(f"📈 Demand spike detected — severity: {da.get('spike_severity', 'unknown')}")
    if dr.get("recommended_action"):
        recommendations.append(f"🌩️  {dr['recommended_action']}")
    if ps.get("protection_strategy"):
        recommendations.append(f"🏥 {ps['protection_strategy']}")
    if not recommendations:
        recommendations.append("✅ Grid is stable — no immediate action needed")

    requires_approval = overall_risk in ["high", "critical"]

    final = {
        "risk_level": overall_risk,
        "risk_reason": gh.get("analysis", "No analysis available"),
        "recommendations": recommendations,
        "demand_trend": da.get("demand_trend", "stable"),
        "spike_detected": da.get("spike_detected", False),
        "spike_severity": da.get("spike_severity", "none"),
        "disaster_risk": dr.get("disaster_risk", "low"),
        "risk_factors": dr.get("risk_factors", []),
        "protected_zones_safe": ps.get("protected_zones_safe", True),
        "critical_zones": ps.get("critical_zones", []),
        "safe_to_cut_zones": ps.get("safe_to_cut_zones", []),
        "load_percentage": gh.get("load_percentage", 0),
        "stability_score": gh.get("stability_score", 100),
        "cascading_failure_risk": gh.get("cascading_failure_risk", False),
        "time_to_act_minutes": dr.get("time_to_act_minutes", 60),
        "avg_confidence": avg_confidence,
        "requires_human_approval": requires_approval,
        "deficit_mw": intake.get("deficit_mw", 0)
    }

    risk_colors = {
        "low": "\033[92m", "medium": "\033[93m",
        "high": "\033[91m", "critical": "\033[31m"
    }
    color = risk_colors.get(overall_risk, "\033[0m")
    print(f"\033[96m  ✓ Overall Risk: {color}{overall_risk.upper()}\033[96m | Confidence: {avg_confidence} | Requires HITL: {requires_approval}\033[0m")
    print("\033[94m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m\n")

    return {"final_analysis": final, "requires_human_approval": requires_approval}


def node_human_review(state: GridAnalysisState) -> dict:
    """
    TRUE LangGraph HITL — graph execution pauses here.
    Operator must send a decision via WebSocket to resume.
    """
    fa = state["final_analysis"]
    print(f"\n\033[31m{'━'*50}\033[0m")
    print(f"\033[31m  🚨 [HITL] PAUSING GRAPH — HUMAN APPROVAL REQUIRED\033[0m")
    print(f"\033[31m  Risk Level : {fa['risk_level'].upper()}\033[0m")
    print(f"\033[31m  Reason     : {fa['risk_reason']}\033[0m")
    print(f"\033[31m  Time to Act: {fa.get('time_to_act_minutes')} minutes\033[0m")
    print(f"\033[31m{'━'*50}\033[0m\n")

    # This line PAUSES the graph — execution stops here until resumed
    human_decision = interrupt({
        "message": "⚠️ HIGH RISK — Human approval required before executing any plan.",
        "risk_level": fa["risk_level"],
        "risk_reason": fa["risk_reason"],
        "cascading_failure_risk": fa.get("cascading_failure_risk"),
        "time_to_act_minutes": fa.get("time_to_act_minutes"),
        "recommendations": fa["recommendations"],
        "safe_to_cut_zones": fa.get("safe_to_cut_zones", []),
    })

    print(f"\033[92m  ✅ [HITL] Operator responded: {human_decision}\033[0m\n")
    return {"human_decision": human_decision}


def node_auto_approve(state: GridAnalysisState) -> dict:
    print("\033[92m  ✅ [AUTO] Low/medium risk — proceeding without human gate.\033[0m\n")
    return {"human_decision": {"decision": "auto_approved"}}


# ── Conditional routing ────────────────────────────────────────────────────────

def route_after_synthesize(state: GridAnalysisState) -> str:
    risk = state["final_analysis"]["risk_level"]
    return "human_review" if risk in ["high", "critical"] else "auto_approve"


# ── Build graph ────────────────────────────────────────────────────────────────

memory = MemorySaver()

def build_graph():
    workflow = StateGraph(GridAnalysisState)

    # Register nodes
    workflow.add_node("intake",          node_intake)
    workflow.add_node("grid_health",     node_grid_health)
    workflow.add_node("demand_agent",    node_demand)
    workflow.add_node("disaster_agent",  node_disaster)
    workflow.add_node("priority_agent",  node_priority)
    workflow.add_node("synthesize",      node_synthesize)
    workflow.add_node("human_review",    node_human_review)
    workflow.add_node("auto_approve",    node_auto_approve)

    workflow.set_entry_point("intake")

    # intake → 3 PARALLEL agents (fan-out)
    workflow.add_edge("intake",         "grid_health")
    workflow.add_edge("intake",         "demand_agent")
    workflow.add_edge("intake",         "disaster_agent")

    # 3 parallel agents → priority_agent (fan-in / join)
    workflow.add_edge("grid_health",    "priority_agent")
    workflow.add_edge("demand_agent",   "priority_agent")
    workflow.add_edge("disaster_agent", "priority_agent")

    # priority → synthesize
    workflow.add_edge("priority_agent", "synthesize")

    # synthesize → conditional: HITL or auto
    workflow.add_conditional_edges(
        "synthesize",
        route_after_synthesize,
        {
            "human_review": "human_review",
            "auto_approve": "auto_approve"
        }
    )

    workflow.add_edge("human_review", END)
    workflow.add_edge("auto_approve",  END)

    return workflow.compile(checkpointer=memory)


graph = build_graph()


def run_analysis(grid_data: dict, thread_id: str) -> dict:
    """
    Runs the agent pipeline.
    For high/critical risk: graph pauses at interrupt() waiting for human.
    For low/medium risk: graph completes automatically.
    """
    config = {"configurable": {"thread_id": thread_id}}
    initial_state: GridAnalysisState = {
        "grid_data": grid_data,
        "intake": None,
        "grid_health": None,
        "demand_analysis": None,
        "disaster_risk": None,
        "priority_status": None,
        "final_analysis": None,
        "requires_human_approval": False,
        "human_decision": None
    }
    result = graph.invoke(initial_state, config=config)
    return result.get("final_analysis", {})


def resume_with_human_decision(thread_id: str, decision: dict) -> dict:
    """
    Resumes a paused LangGraph thread after the human operator makes a decision.
    Called from the WebSocket handler when operator sends apply_plan or reject_plans.
    """
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(Command(resume=decision), config=config)
    return result.get("final_analysis", {})