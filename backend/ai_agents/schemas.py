"""
Data schemas for the Smart Grid AI Multi-Agent System.
Defines Pydantic models for input/output validation.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class Zone(BaseModel):
    """Represents a zone in the power grid."""
    name: str = Field(..., description="Name of the zone")
    protected: bool = Field(..., description="Whether this zone is critical (hospital, airport, etc.)")


class GridInputSchema(BaseModel):
    """Input schema for the grid analysis system."""
    demand: int = Field(..., description="Current power demand in MW", ge=0)
    supply: int = Field(..., description="Current power supply in MW", ge=0)
    temperature: int = Field(..., description="Current temperature in Celsius")
    zones: List[Zone] = Field(..., description="List of zones in the grid")


class Recommendation(BaseModel):
    """A single recommendation for grid management."""
    action: str = Field(..., description="The recommended action")
    priority: str = Field(..., description="Priority level: low, medium, high")
    affected_zones: Optional[List[str]] = Field(None, description="Zones affected by this recommendation")


class GridOutputSchema(BaseModel):
    """Output schema for the grid analysis system with enhanced HITL payload."""
    risk_level: str = Field(..., description="Risk level: low, medium, high, or critical")
    recommendations: List[Recommendation] = Field(..., description="List of recommendations")
    analysis: dict = Field(..., description="Detailed analysis from each agent")
    
    # Enhanced HITL fields
    thread_id: Optional[str] = Field(None, description="Unique workflow thread ID for resumability")
    avg_confidence: Optional[float] = Field(None, description="Average confidence across all agents (0-1)")
    requires_human_approval: Optional[bool] = Field(False, description="Whether human approval is needed")
    human_approved: Optional[bool] = Field(None, description="Whether human approved (if prompted)")


class AgentState(BaseModel):
    """State object passed through the multi-agent workflow."""
    input_data: GridInputSchema
    
    # Agent analysis results
    overload: bool = False
    demand_spike: bool = False
    disaster_risk: bool = False
    protected_zones_at_risk: List[str] = []
    
    # Overall risk assessment
    risk_level: str = "low"
    recommendations: List[Recommendation] = []
    analysis: Dict[str, Any] = {}
    
    # HITL (Human-in-the-Loop) fields
    thread_id: Optional[str] = Field(None, description="Unique thread ID for workflow resumability")
    requires_human_approval: bool = Field(False, description="HITL: Pause for human review")
    required_human_approval: bool = Field(False, description="Backend flag for approval requirement")
    human_approved: Optional[bool] = Field(None, description="Human decision (approve/reject)")
    timestamp: Optional[str] = Field(None, description="Workflow timestamp")
    
    # Confidence scores (per agent)
    health_confidence: float = Field(default=0.5, description="GridHealthAgent confidence (0-1)")
    demand_confidence: float = Field(default=0.5, description="DemandAgent confidence (0-1)")
    disaster_confidence: float = Field(default=0.5, description="DisasterAgent confidence (0-1)")
    
    class Config:
        arbitrary_types_allowed = True
