from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from typing import TypedDict, Optional, Annotated
from dotenv import load_dotenv
from .agents import (
    intake_agent, grid_health_agent,
    demand_agent, disaster_agent, priority_agent
)

load_dotenv()

# ── Reducer for parallel writes ────────────────────────────────────────────────

def merge_dicts(a: dict, b: dict) -> dict:
    return {**a, **b}

# ── State ──────────────────────────────────────────────────────────────────────

class GridAnalysisState(TypedDict):
    grid_data:               dict
    intake:                  Optional[dict]
    grid_health:             Optional[dict]
    demand_analysis:         Optional[dict]
    disaster_risk:           Optional[dict]
    priority_status:         Optional[dict]
    final_analysis:          Optional[dict]
    requires_human_approval: bool
    human_decision:          Optional[dict]
    agent_errors:            Annotated[dict, merge_dicts]   # parallel-safe

# ── Fallback dicts ─────────────────────────────────────────────────────────────

def _grid_health_fallback() -> dict:
    return {
        "overload": True, "load_percentage": 0, "fault_risk": "medium",
        "cascading_failure_risk": False, "stability_score": 50,
        "analysis": "Grid health agent unavailable", "confidence": 0.3
    }

def _demand_fallback() -> dict:
    return {
        "demand_trend": "unknown", "spike_detected": False, "spike_severity": "none",
        "temperature_impact_mw": 0, "forecast_next_hour": "unavailable",
        "recommended_reserve_mw": 0, "confidence": 0.3
    }

def _disaster_fallback() -> dict:
    return {
        "disaster_risk": "medium", "risk_factors": ["data unavailable"],
        "infrastructure_threat": False, "recommended_action": "Manual assessment required",
        "time_to_act_minutes": 30, "confidence": 0.3
    }

def _priority_fallback() -> dict:
    return {
        "protected_zones_safe": True, "critical_zones": [], "at_risk_zones": [],
        "safe_to_cut_zones": [], "protection_strategy": "Priority agent unavailable",
        "estimated_relief_mw": 0, "confidence": 0.3
    }

# ── Safe runner ────────────────────────────────────────────────────────────────

def _safe_run(agent_fn, *args, agent_name: str, state: dict) -> tuple:
    """Runs agent, returns (result, error_msg). Never raises."""
    try:
        return agent_fn(*args), None
    except TimeoutError:
        msg = f"{agent_name} timed out after 15s"
        print(f"\033[91m  ✗ [{agent_name}] TIMEOUT\033[0m")
        return None, msg
    except ValueError as e:
        msg = f"{agent_name} returned invalid JSON: {e}"
        print(f"\033[91m  ✗ [{agent_name}] JSON ERROR: {e}\033[0m")
        return None, msg
    except Exception as e:
        msg = f"{agent_name} unexpected error: {e}"
        print(f"\033[91m  ✗ [{agent_name}] ERROR: {e}\033[0m")
        return None, msg

# ── Node functions ─────────────────────────────────────────────────────────────

def node_intake(state: GridAnalysisState) -> dict:
    print("\n\033[94m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m")
    print("\033[94m  🔵 [INTAKE AGENT] Preprocessing grid data...\033[0m")
    result = intake_agent(state["grid_data"])
    print(f"\033[94m  ✓ Deficit: {result['deficit_mw']}MW | Overloaded: {result['is_overloaded']} | Heatwave: {result['heatwave_active']}\033[0m")
    return {"intake": result, "agent_errors": {}}


def node_grid_health(state: GridAnalysisState) -> dict:
    print("\033[93m  ⚡ [GRID HEALTH AGENT] Analyzing stability & fault risk...\033[0m")
    result, err = _safe_run(
        grid_health_agent, state["grid_data"], state["intake"],
        agent_name="GridHealthAgent", state=state
    )
    if result:
        print(f"\033[93m  ✓ Fault Risk: {result.get('fault_risk')} | Stability: {result.get('stability_score')}/100 | Cascading: {result.get('cascading_failure_risk')}\033[0m")
    return {
        "grid_health":  result or _grid_health_fallback(),
        "agent_errors": {"grid_health": err} if err else {}
    }


def node_demand(state: GridAnalysisState) -> dict:
    print("\033[92m  📈 [DEMAND AGENT] Forecasting consumption trends...\033[0m")
    result, err = _safe_run(
        demand_agent, state["grid_data"], state["intake"],
        agent_name="DemandAgent", state=state
    )
    if result:
        print(f"\033[92m  ✓ Trend: {result.get('demand_trend')} | Spike: {result.get('spike_detected')} | Severity: {result.get('spike_severity')}\033[0m")
    return {
        "demand_analysis": result or _demand_fallback(),
        "agent_errors":    {"demand": err} if err else {}
    }


def node_disaster(state: GridAnalysisState) -> dict:
    print("\033[91m  🌩️  [DISASTER AGENT] Evaluating environmental risks...\033[0m")
    result, err = _safe_run(
        disaster_agent, state["grid_data"], state["intake"],
        agent_name="DisasterAgent", state=state
    )
    if result:
        print(f"\033[91m  ✓ Disaster Risk: {result.get('disaster_risk')} | Time to Act: {result.get('time_to_act_minutes')}min\033[0m")
    return {
        "disaster_risk": result or _disaster_fallback(),
        "agent_errors":  {"disaster": err} if err else {}
    }


def node_priority(state: GridAnalysisState) -> dict:
    print("\033[95m  🏥 [PRIORITY AGENT] Determining zone protection hierarchy...\033[0m")
    result, err = _safe_run(
        priority_agent,
        state["grid_data"],
        state.get("grid_health")     or _grid_health_fallback(),
        state.get("demand_analysis") or _demand_fallback(),
        state.get("disaster_risk")   or _disaster_fallback(),
        agent_name="PriorityAgent", state=state
    )
    if result:
        print(f"\033[95m  ✓ Safe to Cut: {result.get('safe_to_cut_zones')} | Relief: {result.get('estimated_relief_mw')}MW\033[0m")
    return {
        "priority_status": result or _priority_fallback(),
        "agent_errors":    {"priority": err} if err else {}
    }


def node_synthesize(state: GridAnalysisState) -> dict:
    print("\033[96m  🧠 [SYNTHESIZER] Aggregating all agent outputs...\033[0m")

    gh     = state.get("grid_health")     or _grid_health_fallback()
    da     = state.get("demand_analysis") or _demand_fallback()
    dr     = state.get("disaster_risk")   or _disaster_fallback()
    ps     = state.get("priority_status") or _priority_fallback()
    intake = state.get("intake")          or {}
    errors = state.get("agent_errors")    or {}

    risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    risks      = [gh.get("fault_risk", "low"), dr.get("disaster_risk", "low")]
    overall    = max(risks, key=lambda r: risk_order.get(r, 0))

    if gh.get("cascading_failure_risk") and overall == "high":
        overall = "critical"

    raw_confidences = [
        gh.get("confidence", 0.5),
        da.get("confidence", 0.5),
        dr.get("confidence", 0.5),
        ps.get("confidence", 0.5)
    ]
    penalty  = len(errors) * 0.1
    avg_conf = round(max(0.0, sum(raw_confidences) / len(raw_confidences) - penalty), 2)

    recommendations = []
    if gh.get("overload"):
        recommendations.append("⚡ Immediate load shedding required — grid is overloaded")
    if da.get("spike_detected"):
        recommendations.append(f"📈 Demand spike detected — severity: {da.get('spike_severity', 'unknown')}")
    if dr.get("recommended_action"):
        recommendations.append(f"🌩️  {dr['recommended_action']}")
    if ps.get("protection_strategy"):
        recommendations.append(f"🏥 {ps['protection_strategy']}")
    if errors:
        recommendations.append(f"⚠️  {len(errors)} agent(s) degraded — confidence reduced")
    if not recommendations:
        recommendations.append("✅ Grid stable — no immediate action needed")

    requires_approval = overall in ["high", "critical"]

    final = {
        "risk_level":              overall,
        "risk_reason":             gh.get("analysis", "Insufficient data"),
        "recommendations":         recommendations,
        "demand_trend":            da.get("demand_trend", "unknown"),
        "spike_detected":          da.get("spike_detected", False),
        "spike_severity":          da.get("spike_severity", "none"),
        "disaster_risk":           dr.get("disaster_risk", "low"),
        "risk_factors":            dr.get("risk_factors", []),
        "protected_zones_safe":    ps.get("protected_zones_safe", True),
        "critical_zones":          ps.get("critical_zones", []),
        "safe_to_cut_zones":       ps.get("safe_to_cut_zones", []),
        "load_percentage":         gh.get("load_percentage", 0),
        "stability_score":         gh.get("stability_score", 100),
        "cascading_failure_risk":  gh.get("cascading_failure_risk", False),
        "time_to_act_minutes":     dr.get("time_to_act_minutes", 60),
        "avg_confidence":          avg_conf,
        "requires_human_approval": requires_approval,
        "deficit_mw":              intake.get("deficit_mw", 0),
        "agent_errors":            errors
    }

    color = {
        "low": "\033[92m", "medium": "\033[93m",
        "high": "\033[91m", "critical": "\033[31m"
    }.get(overall, "\033[0m")
    print(f"\033[96m  ✓ Risk: {color}{overall.upper()}\033[96m | Confidence: {avg_conf} | HITL: {requires_approval}\033[0m")
    if errors:
        print(f"\033[93m  ⚠ Degraded agents: {list(errors.keys())}\033[0m")
    print("\033[94m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m\n")

    return {"final_analysis": final, "requires_human_approval": requires_approval}


def node_human_review(state: GridAnalysisState) -> dict:
    fa = state["final_analysis"]
    print(f"\n\033[31m{'━'*50}\033[0m")
    print(f"\033[31m  🚨 [HITL] PAUSING — HUMAN APPROVAL REQUIRED\033[0m")
    print(f"\033[31m  Risk       : {fa['risk_level'].upper()}\033[0m")
    print(f"\033[31m  Reason     : {fa['risk_reason']}\033[0m")
    print(f"\033[31m  Time to Act: {fa.get('time_to_act_minutes')} minutes\033[0m")
    print(f"\033[31m{'━'*50}\033[0m\n")

    human_decision = interrupt({
        "message":                "⚠️ HIGH RISK — Human approval required.",
        "risk_level":             fa["risk_level"],
        "risk_reason":            fa["risk_reason"],
        "cascading_failure_risk": fa.get("cascading_failure_risk"),
        "time_to_act_minutes":    fa.get("time_to_act_minutes"),
        "recommendations":        fa["recommendations"],
        "safe_to_cut_zones":      fa.get("safe_to_cut_zones", []),
    })

    print(f"\033[92m  ✅ [HITL] Operator responded: {human_decision}\033[0m\n")
    return {"human_decision": human_decision}


def node_auto_approve(state: GridAnalysisState) -> dict:
    print("\033[92m  ✅ [AUTO] Low/medium risk — proceeding without human gate.\033[0m\n")
    return {"human_decision": {"decision": "auto_approved"}}


def route_after_synthesize(state: GridAnalysisState) -> str:
    return "human_review" if state["final_analysis"]["risk_level"] in ["high", "critical"] else "auto_approve"


# ── Build graph ────────────────────────────────────────────────────────────────

memory = MemorySaver()

def build_graph():
    workflow = StateGraph(GridAnalysisState)

    workflow.add_node("intake",         node_intake)
    workflow.add_node("grid_health",    node_grid_health)
    workflow.add_node("demand_agent",   node_demand)
    workflow.add_node("disaster_agent", node_disaster)
    workflow.add_node("priority_agent", node_priority)
    workflow.add_node("synthesize",     node_synthesize)
    workflow.add_node("human_review",   node_human_review)
    workflow.add_node("auto_approve",   node_auto_approve)

    workflow.set_entry_point("intake")

    # fan-out: intake → 3 parallel agents
    workflow.add_edge("intake",         "grid_health")
    workflow.add_edge("intake",         "demand_agent")
    workflow.add_edge("intake",         "disaster_agent")

    # fan-in: all 3 → priority
    workflow.add_edge("grid_health",    "priority_agent")
    workflow.add_edge("demand_agent",   "priority_agent")
    workflow.add_edge("disaster_agent", "priority_agent")

    workflow.add_edge("priority_agent", "synthesize")

    workflow.add_conditional_edges(
        "synthesize",
        route_after_synthesize,
        {"human_review": "human_review", "auto_approve": "auto_approve"}
    )

    workflow.add_edge("human_review", END)
    workflow.add_edge("auto_approve",  END)

    return workflow.compile(checkpointer=memory)


graph = build_graph()


def run_analysis(grid_data: dict, thread_id: str) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    initial: GridAnalysisState = {
        "grid_data":               grid_data,
        "intake":                  None,
        "grid_health":             None,
        "demand_analysis":         None,
        "disaster_risk":           None,
        "priority_status":         None,
        "final_analysis":          None,
        "requires_human_approval": False,
        "human_decision":          None,
        "agent_errors":            {}
    }
    result = graph.invoke(initial, config=config)
    return result.get("final_analysis", {})


def resume_with_human_decision(thread_id: str, decision: dict) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(Command(resume=decision), config=config)
    return result.get("final_analysis", {})