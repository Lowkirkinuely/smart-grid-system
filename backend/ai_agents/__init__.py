"""
Smart Grid Health - AI Multi-Agent System for Real-Time Grid Analysis.

This package provides a LangGraph-based multi-agent system with:
- Parallel agent execution (3x faster)
- HITL interrupts for human review
- MemorySaver state persistence
- Groq LLM integration with timeout resilience

Main Components:
- schemas: Pydantic models for input/output validation
- agents: Individual LLM-powered agents with fallbacks
- graph: Parallel LangGraph workflow orchestration
- resilience: Timeout handling and fallback mechanisms
"""

from .schemas import (
    GridInputSchema,
    GridOutputSchema,
    AgentState,
    Zone,
    Recommendation
)

from .agents import (
    IntakeAgent,
    GridHealthAgent,
    DemandAgent,
    DisasterAgent,
    PriorityAgent,
    RiskAssessmentAgent
)

from .graph import GridAnalysisWorkflow

from .resilience import (
    SafeAgent,
    _safe_run,
    DEFAULT_TIMEOUT,
    FALLBACK_CONFIDENCE,
)

__all__ = [
    # Schemas
    "GridInputSchema",
    "GridOutputSchema",
    "AgentState",
    "Zone",
    "Recommendation",
    # Agents
    "IntakeAgent",
    "GridHealthAgent",
    "DemandAgent",
    "DisasterAgent",
    "PriorityAgent",
    "RiskAssessmentAgent",
    # Workflow
    "GridAnalysisWorkflow",
    # Resilience
    "SafeAgent",
    "_safe_run",
    "DEFAULT_TIMEOUT",
    "FALLBACK_CONFIDENCE",
]
