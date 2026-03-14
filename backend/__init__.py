"""
Smart Grid Optimization System Backend

Modules:
- ai_agents: SAN (AI Multi-Agent Analysis System)
- optimizer: RHY (Optimization Engine with OR-Tools)
- websocket_manager: Real-time WebSocket broadcasting
- main: FastAPI application server
"""

# Import and re-export AI Agents
from backend.ai_agents import (
    GridInputSchema,
    GridOutputSchema,
    AgentState,
    Zone,
    Recommendation,
    GridHealthAgent,
    DemandAgent,
    DisasterAgent,
    PriorityAgent,
    RiskAssessmentAgent,
    GridAnalysisWorkflow,
)

# Import and re-export Optimization Engine
from backend.optimizer import (
    GridOptimizer,
    OptimizationStrategy,
    format_strategies_for_websocket,
)

# Import and re-export WebSocket Manager
from backend.websocket_manager import (
    ConnectionManager,
    manager,
)

__all__ = [
    # AI Agents (SAN)
    "GridInputSchema",
    "GridOutputSchema",
    "AgentState",
    "Zone",
    "Recommendation",
    "GridHealthAgent",
    "DemandAgent",
    "DisasterAgent",
    "PriorityAgent",
    "RiskAssessmentAgent",
    "GridAnalysisWorkflow",
    # Optimization Engine (RHY)
    "GridOptimizer",
    "OptimizationStrategy",
    "format_strategies_for_websocket",
    # WebSocket Manager
    "ConnectionManager",
    "manager",
]
