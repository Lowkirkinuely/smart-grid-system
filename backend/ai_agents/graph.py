"""
LangGraph workflow for Smart Grid Human-in-the-Loop system.
Parallel multi-agent pipeline with ML+LLM fusion and hard HITL interrupt.
"""

import sys
import os
import logging
from typing import Optional
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from langgraph.errors import GraphInterrupt
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_agents.agents import (
    IntakeAgent, GridHealthAgent, DemandAgent,
    DisasterAgent, PriorityAgent, MLAgent
)
from .resilience import (
    safe_run,
    calculate_fused_confidence,
    fuse_risk, max_risk,
    check_disagreement,
    should_escalate_for_anomaly,
    RISK_ORDER, RISK_REVERSE
)

load_dotenv()

logger = logging.getLogger(__name__)


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
    ml_prediction:           Optional[dict]
    priority_status:         Optional[dict]
    final_analysis:          Optional[dict]
    requires_human_approval: bool
    human_decision:          Optional[dict]
    ml_llm_disagreement:     bool
    agent_errors:            Annotated[dict, merge_dicts]


# ── Node functions ─────────────────────────────────────────────────────────────

def node_intake(state: GridAnalysisState) -> dict:
    logger.info("[INTAKE] Preprocessing grid data")
    print("\n\033[94m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m")
    print("\033[94m  🔵 [INTAKE AGENT] Preprocessing grid data...\033[0m")
    result = IntakeAgent.validate(state["grid_data"])
    print(f"\033[94m  ✓ Deficit: {result['deficit_mw']}MW | Overloaded: {result['is_overloaded']} | Heatwave: {result['heatwave_active']}\033[0m")
    return {"intake": result, "agent_errors": {}, "ml_llm_disagreement": False}


def node_ml_analysis(state: GridAnalysisState) -> dict:
    logger.info("[ML] Running pattern analysis and anomaly detection")
    print("\033[35m  🤖 [ML MODEL] Running pattern analysis & anomaly detection...\033[0m")
    try:
        result = MLAgent.analyze(state["grid_data"])
        anom   = "⚠️  ANOMALY" if result["anomaly_detected"] else "normal"
        print(f"\033[35m  ✓ ML Risk: {result['ml_risk_level'].upper()} | Confidence: {result['ml_confidence']} | Pattern: {anom} | Samples: {result['training_samples']}\033[0m")
        print(f"\033[35m  ✓ Top Features: {result['top_risk_features']}\033[0m")
        return {"ml_prediction": result, "agent_errors": {}}
    except Exception as e:
        msg = f"ML model error: {str(e)}"
        logger.error(f"[ML] {msg}", exc_info=True)
        print(f"\033[91m  ✗ [ML MODEL] ERROR — {msg}\033[0m")
        print(f"\033[91m  ✗ Using rule-based fallback based on deficit\033[0m")
        
        # Smart fallback: infer risk from deficit instead of returning "unknown"
        intake = state.get("intake", {})
        deficit = intake.get("deficit_mw", 0)
        is_heatwave = intake.get("heatwave_active", False)
        
        if deficit <= 0:
            fallback_risk = "low"
        elif deficit <= 50:
            fallback_risk = "medium" if is_heatwave else "low"
        elif deficit <= 150:
            fallback_risk = "high"
        else:
            fallback_risk = "critical"
        
        fallback = MLAgent.fallback()
        fallback["ml_risk_level"] = fallback_risk  # Override unknown with smart fallback
        fallback["ml_confidence"] = 0.5  # Low confidence since model failed
        
        return {"ml_prediction": fallback, "agent_errors": {"ml": msg}}


def node_grid_health(state: GridAnalysisState) -> dict:
    logger.info("[GRID HEALTH] Analyzing stability and fault risk")
    print("\033[93m  ⚡ [GRID HEALTH AGENT] Analyzing stability & fault risk...\033[0m")
    result, err = safe_run(
        GridHealthAgent.analyze,
        state["grid_data"], state["intake"],
        agent_name="GridHealthAgent"
    )
    if result:
        print(f"\033[93m  ✓ Fault Risk: {result.get('fault_risk')} | Stability: {result.get('stability_score')}/100 | Cascading: {result.get('cascading_failure_risk')}\033[0m")
    return {
        "grid_health":  result or GridHealthAgent.fallback(state["intake"]),
        "agent_errors": {"grid_health": err} if err else {}
    }


def node_demand(state: GridAnalysisState) -> dict:
    logger.info("[DEMAND] Forecasting consumption trends")
    print("\033[92m  📈 [DEMAND AGENT] Forecasting consumption trends...\033[0m")
    result, err = safe_run(
        DemandAgent.analyze,
        state["grid_data"], state["intake"],
        agent_name="DemandAgent"
    )
    if result:
        print(f"\033[92m  ✓ Trend: {result.get('demand_trend')} | Spike: {result.get('spike_detected')} | Severity: {result.get('spike_severity')}\033[0m")
    return {
        "demand_analysis": result or DemandAgent.fallback(state["intake"], state["grid_data"]),
        "agent_errors":    {"demand": err} if err else {}
    }


def node_disaster(state: GridAnalysisState) -> dict:
    logger.info("[DISASTER] Evaluating environmental risks")
    print("\033[91m  🌩️  [DISASTER AGENT] Evaluating environmental risks...\033[0m")
    result, err = safe_run(
        DisasterAgent.analyze,
        state["grid_data"], state["intake"],
        agent_name="DisasterAgent"
    )
    if result:
        print(f"\033[91m  ✓ Disaster Risk: {result.get('disaster_risk')} | Time to Act: {result.get('time_to_act_minutes')}min\033[0m")
    return {
        "disaster_risk": result or DisasterAgent.fallback(state["intake"], state["grid_data"]),
        "agent_errors":  {"disaster": err} if err else {}
    }


def node_priority(state: GridAnalysisState) -> dict:
    logger.info("[PRIORITY] Determining zone protection hierarchy")
    print("\033[95m  🏥 [PRIORITY AGENT] Determining zone protection hierarchy...\033[0m")
    intake   = state.get("intake") or {}
    gd       = state["grid_data"]
    result, err = safe_run(
        PriorityAgent.analyze,
        gd,
        state.get("grid_health")     or GridHealthAgent.fallback(intake),
        state.get("demand_analysis") or DemandAgent.fallback(intake, gd),
        state.get("disaster_risk")   or DisasterAgent.fallback(intake, gd),
        agent_name="PriorityAgent"
    )
    if result:
        print(f"\033[95m  ✓ Safe to Cut: {result.get('safe_to_cut_zones')} | Relief: {result.get('estimated_relief_mw')}MW\033[0m")
    return {
        "priority_status": result or PriorityAgent.fallback(gd),
        "agent_errors":    {"priority": err} if err else {}
    }


def node_synthesize(state: GridAnalysisState) -> dict:
    logger.info("[SYNTHESIZER] Combining ML + LLM outputs")
    print("\033[96m  🧠 [SYNTHESIZER] Combining ML + LLM outputs...\033[0m")

    intake = state.get("intake")          or {}
    gd     = state["grid_data"]
    gh     = state.get("grid_health")     or GridHealthAgent.fallback(intake)
    da     = state.get("demand_analysis") or DemandAgent.fallback(intake, gd)
    dr     = state.get("disaster_risk")   or DisasterAgent.fallback(intake, gd)
    ps     = state.get("priority_status") or PriorityAgent.fallback(gd)
    ml     = state.get("ml_prediction")   or MLAgent.fallback()
    errors = state.get("agent_errors")    or {}

    # LLM risk aggregation
    llm_risk = max_risk(
        gh.get("fault_risk", "low"),
        dr.get("disaster_risk", "low")
    )
    if gh.get("cascading_failure_risk") and llm_risk == "high":
        llm_risk = "critical"

    # ── ML + LLM fusion ───────────────────────────────────────────────────────
    ml_risk  = ml.get("ml_risk_level", "unknown")
    ml_conf  = ml.get("ml_confidence", 0.0)

    # Weighted vote: LLM gets 60%, ML gets 40%
    if ml_risk != "unknown":
        llm_score = RISK_ORDER.get(llm_risk, 0) * 0.60
        ml_score  = RISK_ORDER.get(ml_risk, 0)  * 0.40
        fused_idx = round(llm_score + ml_score)
        fused_idx = max(0, min(3, fused_idx))
        final_risk = RISK_REVERSE[fused_idx]
    else:
        final_risk = llm_risk

    # ── Disagreement detection ────────────────────────────────────────────────

    llm_idx  = RISK_ORDER.get(llm_risk, 0)
    ml_idx   = RISK_ORDER.get(ml_risk, 0) if ml_risk != "unknown" else llm_idx
    gap      = abs(llm_idx - ml_idx)
    disagree = gap >= 3  # e.g. ML says critical, LLM says low

    # Disagreement detection
    disagree = check_disagreement(llm_risk, ml_risk)
    if disagree:
        logger.warning(f"[SYNTHESIZER] ML/LLM disagreement — ML: {ml_risk}, LLM: {llm_risk}")
        print(f"\033[33m  ⚡ [DISAGREEMENT] ML says '{ml_risk}', LLM says '{llm_risk}' — forcing HITL\033[0m")

    # ── Anomaly bump ──────────────────────────────────────────────────────────
    if ml.get("anomaly_detected") and RISK_ORDER.get(final_risk, 0) < 1:
        print(f"\033[33m  ⚠️  Anomaly detected — escalating risk from {final_risk} to high\033[0m")
        final_risk = "high"

    # ── Confidence ────────────────────────────────────────────────────────────
    llm_confidences = [
        gh.get("confidence", 0.5), da.get("confidence", 0.5),
        dr.get("confidence", 0.5), ps.get("confidence", 0.5)
    ]
    llm_avg_conf   = sum(llm_confidences) / len(llm_confidences)
    fused_conf     = round((llm_avg_conf * 0.6) + (ml_conf * 0.4) - len(errors) * 0.05, 2)
    fused_conf     = max(0.0, fused_conf)

    # ── Recommendations ───────────────────────────────────────────────────────
    recommendations = []
    if gh.get("overload"):
        recommendations.append("⚡ Immediate load shedding required — grid overloaded")
    if da.get("spike_detected"):
        recommendations.append(f"📈 Demand spike — severity: {da.get('spike_severity', 'unknown')}")
    if dr.get("recommended_action"):
        recommendations.append(f"🌩️  {dr['recommended_action']}")
    if ps.get("protection_strategy"):
        recommendations.append(f"🏥 {ps['protection_strategy']}")
    if ml.get("anomaly_detected"):
        recommendations.append(f"🤖 ML anomaly — top drivers: {ml.get('top_risk_features', [])}")
    if disagree:
        recommendations.append(f"⚠️ ML/LLM disagreement — ML: {ml_risk}, LLM: {llm_risk} — human review required")
    if errors:
        recommendations.append(f"⚠️ {len(errors)} agent(s) degraded — confidence reduced")
    if not recommendations:
        recommendations.append("✅ Grid stable — no immediate action needed")

    # ── HITL: All plans require operator approval ────────────────────────
    # This is a Human-in-the-Loop system - no auto-execution of power cuts
    requires_approval = True
    priority_reason = ""
    if final_risk in ["high", "critical"]:
        priority_reason = f"⚠️  PRIORITY: {final_risk.upper()} RISK — Operator review required"
    elif disagree:
        priority_reason = "⚠️  PRIORITY: ML/LLM DISAGREEMENT — Operator review required"
    else:
        priority_reason = f"ℹ️  {final_risk.upper()} risk — Ready for operator approval"

    final = {
        "risk_level":              final_risk,
        "llm_risk_level":          llm_risk,
        "ml_risk_level":           ml_risk,
        "ml_llm_disagreement":     disagree,
        "risk_reason":             f"{priority_reason} | {gh.get('analysis', 'Insufficient data')}",
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
        "avg_confidence":          fused_conf,
        "ml_confidence":           ml_conf,
        "ml_probabilities":        ml.get("ml_probabilities", {}),
        "anomaly_detected":        ml.get("anomaly_detected", False),
        "anomaly_score":           ml.get("anomaly_score", 0.0),
        "top_risk_features":       ml.get("top_risk_features", []),
        "training_samples":        ml.get("training_samples", 0),
        "requires_human_approval": requires_approval,
        "deficit_mw":              intake.get("deficit_mw", 0),
        "agent_errors":            errors
    }

    color = {
        "low": "\033[92m", "medium": "\033[93m",
        "high": "\033[91m", "critical": "\033[31m"
    }.get(final_risk, "\033[0m")
    print(f"\033[96m  ✓ Final Risk: {color}{final_risk.upper()}\033[96m (LLM: {llm_risk} | ML: {ml_risk}) | Confidence: {fused_conf} | HITL: {requires_approval}\033[0m")
    if disagree:
        print(f"\033[33m  ⚡ ML/LLM DISAGREEMENT — forcing human review\033[0m")
    if errors:
        print(f"\033[93m  ⚠ Degraded agents: {list(errors.keys())}\033[0m")
    print("\033[94m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m\n")

    logger.info(f"[SYNTHESIZER] Final: {final_risk} | LLM: {llm_risk} | ML: {ml_risk} | Conf: {fused_conf} | HITL: {requires_approval}")

    return {
        "final_analysis":          final,
        "requires_human_approval": requires_approval,
        "ml_llm_disagreement":     disagree
    }


def node_human_review(state: GridAnalysisState) -> dict:
    fa       = state["final_analysis"]
    disagree = state.get("ml_llm_disagreement", False)

    logger.warning(f"[HITL] PAUSING — Risk: {fa['risk_level'].upper()} | Disagreement: {disagree}")
    print(f"\n\033[31m{'━'*50}\033[0m")
    print(f"\033[31m  🚨 [HITL] PAUSING — HUMAN APPROVAL REQUIRED\033[0m")
    print(f"\033[31m  Final Risk : {fa['risk_level'].upper()}\033[0m")
    print(f"\033[31m  LLM says   : {fa.get('llm_risk_level', 'unknown')}\033[0m")
    print(f"\033[31m  ML says    : {fa.get('ml_risk_level', 'unknown')}\033[0m")
    if disagree:
        print(f"\033[33m  ⚡ REASON   : ML/LLM disagreement — human tie-breaker needed\033[0m")
    print(f"\033[31m  Time to Act: {fa.get('time_to_act_minutes')} minutes\033[0m")
    print(f"\033[31m{'━'*50}\033[0m\n")

    human_decision = interrupt({
        "message":                "⚠️ Human approval required",
        "risk_level":             fa["risk_level"],
        "llm_risk_level":         fa.get("llm_risk_level"),
        "ml_risk_level":          fa.get("ml_risk_level"),
        "ml_llm_disagreement":    disagree,
        "risk_reason":            fa["risk_reason"],
        "cascading_failure_risk": fa.get("cascading_failure_risk"),
        "time_to_act_minutes":    fa.get("time_to_act_minutes"),
        "recommendations":        fa["recommendations"],
        "safe_to_cut_zones":      fa.get("safe_to_cut_zones", []),
        "anomaly_detected":       fa.get("anomaly_detected", False),
        "top_risk_features":      fa.get("top_risk_features", [])
    })

    logger.info(f"[HITL] Operator responded: {human_decision}")
    print(f"\033[92m  ✅ [HITL] Operator responded: {human_decision}\033[0m\n")
    return {"human_decision": human_decision}


def node_auto_approve(state: GridAnalysisState) -> dict:
    logger.info("[AUTO] Low/medium risk — proceeding without human gate")
    print("\033[92m  ✅ [AUTO] Low/medium risk — proceeding automatically.\033[0m\n")
    return {"human_decision": {"decision": "auto_approved"}}


def route_after_synthesize(state: GridAnalysisState) -> str:
    """Route to human review for ALL cases — plan execution always requires operator approval."""
    fa       = state["final_analysis"]
    disagree = state.get("ml_llm_disagreement", False)
    # For a Human-in-the-Loop grid system, operator ALWAYS reviews before execution
    # High/critical/disagreement are just flagged as priority
    return "human_review"


# ── GridAnalysisWorkflow class ─────────────────────────────────────────────────

class GridAnalysisWorkflow:

    def __init__(self):
        self.memory         = MemorySaver()
        self.compiled_graph = self._build_graph()
        logger.info("[WORKFLOW] GridAnalysisWorkflow initialised")

    def _build_graph(self):
        workflow = StateGraph(GridAnalysisState)

        workflow.add_node("intake",         node_intake)
        workflow.add_node("ml_analysis",    node_ml_analysis)
        workflow.add_node("grid_health",    node_grid_health)
        workflow.add_node("demand_agent",   node_demand)
        workflow.add_node("disaster_agent", node_disaster)
        workflow.add_node("priority_agent", node_priority)
        workflow.add_node("synthesize",     node_synthesize)
        workflow.add_node("human_review",   node_human_review)
        workflow.add_node("auto_approve",   node_auto_approve)

        workflow.set_entry_point("intake")

        # fan-out: intake → 4 parallel (1 ML + 3 LLM)
        workflow.add_edge("intake",         "ml_analysis")
        workflow.add_edge("intake",         "grid_health")
        workflow.add_edge("intake",         "demand_agent")
        workflow.add_edge("intake",         "disaster_agent")

        # fan-in: all 4 → priority
        workflow.add_edge("ml_analysis",    "priority_agent")
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

        return workflow.compile(checkpointer=self.memory)

    def run_analysis(self, grid_data: dict, thread_id: str) -> dict:
        """Run full agent pipeline. Graph pauses at HITL for high/critical risk."""
        logger.info(f"[WORKFLOW] Starting analysis | thread: {thread_id}")
        config  = {"configurable": {"thread_id": thread_id}}
        initial: GridAnalysisState = {
            "grid_data":               grid_data,
            "intake":                  None,
            "grid_health":             None,
            "demand_analysis":         None,
            "disaster_risk":           None,
            "ml_prediction":           None,
            "priority_status":         None,
            "final_analysis":          None,
            "requires_human_approval": False,
            "human_decision":          None,
            "ml_llm_disagreement":     False,
            "agent_errors":            {}
        }
        try:
            result = self.compiled_graph.invoke(initial, config=config)
            logger.info(
                f"[WORKFLOW] Completed | thread: {thread_id} | "
                f"risk: {result.get('final_analysis', {}).get('risk_level')}"
            )
            return result.get("final_analysis", {})
        except GraphInterrupt:
            logger.warning(f"[WORKFLOW] Paused at HITL interrupt | thread: {thread_id}")
            raise

    def resume_with_human_decision(self, thread_id: str, decision: dict) -> dict:
        """Resume a paused graph thread after operator decision."""
        logger.info(f"[WORKFLOW] Resuming | thread: {thread_id} | decision: {decision.get('decision')}")
        config = {"configurable": {"thread_id": thread_id}}
        try:
            result = self.compiled_graph.invoke(Command(resume=decision), config=config)
            logger.info(f"[WORKFLOW] Resumed successfully | thread: {thread_id}")
            return result.get("final_analysis", {})
        except Exception as e:
            logger.error(f"[WORKFLOW] Resume failed | thread: {thread_id} | error: {e}")
            raise

    def get_graph_structure(self) -> dict:
        """Returns graph metadata for demo and debugging."""
        return {
            "nodes": [
                "intake", "ml_analysis", "grid_health",
                "demand_agent", "disaster_agent",
                "priority_agent", "synthesize",
                "human_review", "auto_approve"
            ],
            "parallel_groups": [
                ["ml_analysis", "grid_health", "demand_agent", "disaster_agent"]
            ],
            "edges": [
                ("START",          "intake"),
                ("intake",         "ml_analysis"),
                ("intake",         "grid_health"),
                ("intake",         "demand_agent"),
                ("intake",         "disaster_agent"),
                ("ml_analysis",    "priority_agent"),
                ("grid_health",    "priority_agent"),
                ("demand_agent",   "priority_agent"),
                ("disaster_agent", "priority_agent"),
                ("priority_agent", "synthesize"),
                ("synthesize",     "human_review OR auto_approve"),
                ("human_review",   "END"),
                ("auto_approve",   "END"),
            ],
            "key_features": [
                "4-way parallel fan-out (1 ML + 3 LLM agents)",
                "Class-based agents with explicit rule-based fallbacks",
                "ML/LLM weighted risk fusion (60/40 split)",
                "Disagreement detection — forces HITL if gap >= 2 levels",
                "Anomaly escalation — IsolationForest bumps risk if unusual pattern",
                "Hard HITL interrupt() — graph execution genuinely pauses",
                "MemorySaver checkpointing — resumable via thread_id",
                "Per-agent fallbacks — one failure never kills pipeline",
                "Online learning — model retrains after every human approval",
                "Confidence penalty — degrades with failed agents"
            ]
        }


# ── Module-level singleton + convenience functions ─────────────────────────────
# Keeps main.py import interface unchanged

_workflow = GridAnalysisWorkflow()

def run_analysis(grid_data: dict, thread_id: str) -> dict:
    return _workflow.run_analysis(grid_data, thread_id)

def resume_with_human_decision(thread_id: str, decision: dict) -> dict:
    return _workflow.resume_with_human_decision(thread_id, decision)

def get_graph_structure() -> dict:
    return _workflow.get_graph_structure()