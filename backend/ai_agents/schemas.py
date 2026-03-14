"""
Data schemas for the Smart Grid Human-in-the-Loop System.
Pydantic models for input/output validation across all components.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ── Input Schemas ──────────────────────────────────────────────────────────────

class Zone(BaseModel):
    """Represents a power grid zone."""
    name:      str   = Field(..., description="Zone name e.g. hospital, residential1")
    demand:    float = Field(..., description="Power demand in MW", ge=0)
    protected: bool  = Field(False, description="True = critical zone, never cut")


class GridInputSchema(BaseModel):
    """Input payload received from SUM (simulator) every 5 seconds."""
    demand:      float      = Field(..., description="Total grid demand in MW", ge=0)
    supply:      float      = Field(..., description="Available supply in MW", ge=0)
    temperature: float      = Field(..., description="Ambient temperature in Celsius")
    zones:       List[Zone] = Field(..., description="All grid zones with demand")


# ── Agent Output Schemas ───────────────────────────────────────────────────────

class IntakeResult(BaseModel):
    deficit_mw:       float = Field(..., description="demand - supply in MW")
    load_ratio:       float = Field(..., description="demand / supply ratio")
    is_overloaded:    bool  = Field(..., description="True if demand exceeds supply")
    heatwave_active:  bool  = Field(..., description="True if temperature > 40°C")
    protected_count:  int   = Field(..., description="Number of protected zones")
    total_zones:      int   = Field(..., description="Total zone count")
    validated:        bool  = Field(True)


class GridHealthResult(BaseModel):
    overload:                bool  = Field(...)
    load_percentage:         float = Field(..., description="Load as % of supply capacity")
    fault_risk:              str   = Field(..., description="low/medium/high/critical")
    cascading_failure_risk:  bool  = Field(...)
    stability_score:         float = Field(..., description="0-100, higher is more stable")
    analysis:                str   = Field(..., description="One sentence technical summary")
    confidence:              float = Field(..., ge=0.0, le=1.0)


class DemandResult(BaseModel):
    demand_trend:            str   = Field(..., description="rising/stable/falling")
    spike_detected:          bool  = Field(...)
    spike_severity:          str   = Field(..., description="none/minor/major/extreme")
    temperature_impact_mw:   float = Field(...)
    forecast_next_hour:      str   = Field(...)
    recommended_reserve_mw:  float = Field(...)
    confidence:              float = Field(..., ge=0.0, le=1.0)


class DisasterResult(BaseModel):
    disaster_risk:          str        = Field(..., description="low/medium/high/critical")
    risk_factors:           List[str]  = Field(...)
    infrastructure_threat:  bool       = Field(...)
    recommended_action:     str        = Field(...)
    time_to_act_minutes:    int        = Field(...)
    confidence:             float      = Field(..., ge=0.0, le=1.0)


class PriorityResult(BaseModel):
    protected_zones_safe:   bool       = Field(...)
    critical_zones:         List[str]  = Field(...)
    at_risk_zones:          List[str]  = Field(...)
    safe_to_cut_zones:      List[str]  = Field(...)
    protection_strategy:    str        = Field(...)
    estimated_relief_mw:    float      = Field(...)
    confidence:             float      = Field(..., ge=0.0, le=1.0)


class MLPredictionResult(BaseModel):
    ml_risk_level:      str            = Field(..., description="low/medium/high/critical/unknown")
    ml_confidence:      float          = Field(..., ge=0.0, le=1.0)
    ml_probabilities:   Dict[str, float] = Field(...)
    anomaly_detected:   bool           = Field(...)
    anomaly_score:      float          = Field(...)
    top_risk_features:  List[str]      = Field(...)
    training_samples:   int            = Field(...)
    patterns_learned:   bool           = Field(...)


# ── Optimization Plan Schema ───────────────────────────────────────────────────

class OptimizationPlan(BaseModel):
    plan_id:          int       = Field(..., description="1, 2, or 3")
    label:            str       = Field(..., description="Human-readable plan name")
    cuts:             List[str] = Field(..., description="Zone names to cut power to")
    power_saved:      float     = Field(..., description="MW saved by this plan")
    deficit_mw:       float     = Field(..., description="Original deficit this plan addresses")
    deficit_covered:  bool      = Field(..., description="True if plan fully covers deficit")
    note:             str       = Field(..., description="Explanation of strategy")


# ── Final Analysis Output Schema ───────────────────────────────────────────────

class FinalAnalysis(BaseModel):
    """Complete output from the LangGraph pipeline — broadcast to dashboard."""

    # Core risk
    risk_level:             str        = Field(..., description="Fused ML+LLM risk: low/medium/high/critical")
    llm_risk_level:         str        = Field(..., description="LLM-only risk assessment")
    ml_risk_level:          str        = Field(..., description="ML-only risk assessment")
    ml_llm_disagreement:    bool       = Field(..., description="True if ML and LLM differ by 2+ levels")
    risk_reason:            str        = Field(..., description="One sentence explanation")
    recommendations:        List[str]  = Field(..., description="Actionable recommendations")

    # Demand
    demand_trend:           str        = Field(...)
    spike_detected:         bool       = Field(...)
    spike_severity:         str        = Field(...)

    # Disaster
    disaster_risk:          str        = Field(...)
    risk_factors:           List[str]  = Field(...)

    # Infrastructure
    protected_zones_safe:   bool       = Field(...)
    critical_zones:         List[str]  = Field(...)
    safe_to_cut_zones:      List[str]  = Field(...)

    # Grid health
    load_percentage:        float      = Field(...)
    stability_score:        float      = Field(...)
    cascading_failure_risk: bool       = Field(...)
    time_to_act_minutes:    int        = Field(...)

    # ML fields
    avg_confidence:         float      = Field(..., ge=0.0, le=1.0)
    ml_confidence:          float      = Field(..., ge=0.0, le=1.0)
    ml_probabilities:       Dict[str, float] = Field(...)
    anomaly_detected:       bool       = Field(...)
    anomaly_score:          float      = Field(...)
    top_risk_features:      List[str]  = Field(...)
    training_samples:       int        = Field(...)

    # HITL
    requires_human_approval: bool      = Field(...)
    deficit_mw:             float      = Field(...)
    agent_errors:           Dict[str, str] = Field(default_factory=dict)


class GridOutputSchema(BaseModel):
    """Full broadcast payload sent to RIS dashboard via WebSocket."""
    type:                    str              = Field(default="plans")
    thread_id:               str             = Field(..., description="UUID for HITL thread tracking")
    grid_state:              Dict[str, Any]  = Field(...)
    plans:                   List[OptimizationPlan] = Field(...)
    ai_analysis:             FinalAnalysis   = Field(...)
    requires_human_approval: bool            = Field(...)


# ── HITL Decision Schema ───────────────────────────────────────────────────────

class HumanDecision(BaseModel):
    """Shape of operator decision sent via WebSocket."""
    type:           str            = Field(..., description="apply_plan / reject_plans / manual_override")
    thread_id:      str            = Field(..., description="Thread ID from broadcast payload")
    plan_id:        Optional[int]  = Field(None, description="Required for apply_plan")
    note:           Optional[str]  = Field(None, description="Operator note")
    reason:         Optional[str]  = Field(None, description="Required for reject_plans")
    confirmed_risk: Optional[str]  = Field(None, description="Operator's confirmed risk — used for ML learning")


# ── ML Stats Schema ────────────────────────────────────────────────────────────

class MLStats(BaseModel):
    training_samples:   int            = Field(...)
    is_trained:         bool           = Field(...)
    patterns_learned:   bool           = Field(..., description="True if >= 50 real samples")
    label_distribution: Dict[str, int] = Field(..., description="Count per risk class")


# ── Agent State (LangGraph) ────────────────────────────────────────────────────

class AgentState(BaseModel):
    """
    Full state object flowing through the LangGraph pipeline.
    Every node reads from and writes to this.
    """
    # Input
    grid_data:    Dict[str, Any] = Field(...)

    # Parallel agent outputs
    intake:           Optional[Dict[str, Any]] = None
    grid_health:      Optional[Dict[str, Any]] = None
    demand_analysis:  Optional[Dict[str, Any]] = None
    disaster_risk:    Optional[Dict[str, Any]] = None
    ml_prediction:    Optional[Dict[str, Any]] = None

    # Fan-in output
    priority_status:  Optional[Dict[str, Any]] = None

    # Synthesized output
    final_analysis:   Optional[Dict[str, Any]] = None

    # HITL
    requires_human_approval: bool = False
    human_decision:          Optional[Dict[str, Any]] = None
    ml_llm_disagreement:     bool = False

    # Error tracking — Annotated in TypedDict for parallel safety
    agent_errors: Dict[str, str] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True