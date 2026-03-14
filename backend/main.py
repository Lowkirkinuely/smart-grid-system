"""FastAPI backend with AI agents, HITL interrupts, and state persistence."""

import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from langgraph.errors import GraphInterrupt
import json
from datetime import datetime

from backend.ai_agents import GridAnalysisWorkflow, GridInputSchema
from backend.optimizer import GridOptimizer, format_strategies_for_websocket
from backend.websocket_manager import manager

logger = logging.getLogger(__name__)


class ZoneData(BaseModel):
    name: str
    protected: bool = False
    demand: Optional[float] = None


class GridStateRequest(BaseModel):
    demand: int = Field(..., description="Current power demand in MW", ge=0)
    supply: int = Field(..., description="Current power supply in MW", ge=0)
    temperature: int = Field(..., description="Current temperature in Celsius")
    zones: List[ZoneData] = Field(..., description="List of zones in the grid")


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: str
    active_connections: int


class GridStateResponse(BaseModel):
    timestamp: str
    grid_state: Dict[str, Any]
    risk_analysis: Dict[str, Any]
    optimization_plans: List[Dict[str, Any]]
    selected_plan: Optional[int] = None
    thread_id: Optional[str] = Field(None, description="Workflow thread ID (for resumable workflows)")
    requires_human_approval: Optional[bool] = Field(False, description="Whether workflow paused for HITL review")


class PausedWorkflowInfo(BaseModel):
    thread_id: str
    paused_at: str
    reason: str
    risk_level: str
    recommendations: List[Dict[str, Any]]
    analysis: Dict[str, Any]


class ApprovalResponse(BaseModel):
    action: str = Field(..., description="approve or reject")
    thread_id: str
    status: str
    timestamp: str
    message: str
    result: Optional[Dict[str, Any]] = None


class HITLCommand(BaseModel):
    """HITL command received via WebSocket."""
    type: str = Field(..., description="approve_plan or reject_plan")
    thread_id: str
    reason: Optional[str] = None



# FastAPI Application Setup


app = FastAPI(
    title="Smart Grid Optimization Engine (RHY)",
    description="Combines AI analysis (SAN) with OR-Tools optimization",
    version="1.0.0",
)

# Add CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize systems
workflow = GridAnalysisWorkflow()
optimizer = GridOptimizer()



# Health Check Endpoint


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    Returns system status and active WebSocket connections.
    """
    return HealthResponse(
        status="healthy",
        service="Smart Grid Optimization Engine (RHY)",
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
        active_connections=manager.get_connection_count(),
    )


@app.post("/grid-state", response_model=GridStateResponse)
async def analyze_grid_state(request: GridStateRequest):
    """
    Primary endpoint: Receive grid data, analyze with SAN, optimize with RHY.
    
    Flow:
    1. Validate input
    2. Run SAN (AI Multi-Agent Analysis) with parallel agents
    3. If risk is high/critical: PAUSE and return thread_id (HITL required)
    4. If approved/low risk: Generate optimization strategies
    5. Broadcast results via WebSocket
    6. Return response with thread_id for tracking
    
    Args:
        request: GridStateRequest containing demand, supply, temperature, zones
    
    Returns:
        GridStateResponse with analysis, thread_id, and optional pause status
    """
    try:
        # Store grid state
        grid_state = {
            "demand": request.demand,
            "supply": request.supply,
            "temperature": request.temperature,
            "zones": [z.model_dump() for z in request.zones],
        }
        
        # ====== STEP 1: Run SAN (AI Multi-Agent Analysis) ======
        await manager.broadcast_status("analyzing", {"stage": "Running parallel AI analysis..."})
        
        # Prepare input for SAN
        san_input = {
            "demand": request.demand,
            "supply": request.supply,
            "temperature": request.temperature,
            "zones": [z.model_dump() for z in request.zones],
        }
        
        # Execute AI analysis workflow (with parallel agents)
        try:
            analysis_result = workflow.analyze(san_input)
        except GraphInterrupt as e:
            # HITL: Workflow paused for human approval
            logger.info(f"Workflow paused for HITL: {str(e)}")
            
            # Extract thread_id from error or state
            thread_id = getattr(e, 'args', [str(e)])[0]
            if "Thread:" in str(e):
                thread_id = str(e).split("Thread:")[-1].strip()
            
            # Broadcast pause notification
            await manager.broadcast_alert(
                "workflow_paused",
                f"Human approval required - Risk level may be critical",
                severity="high",
            )
            await manager.broadcast_status(
                "paused_for_human_review",
                {
                    "thread_id": thread_id,
                    "reason": str(e),
                    "action": "Use /approve or /reject endpoint with thread_id",
                }
            )
            
            # Return response indicating pause
            return GridStateResponse(
                timestamp=datetime.now().isoformat(),
                grid_state=grid_state,
                risk_analysis={
                    "risk_level": "high",
                    "status": "paused_for_human_review",
                    "message": str(e),
                    "recommendations": [],
                    "analysis": {"workflow_paused": True},
                },
                optimization_plans=[],
                selected_plan=None,
                thread_id=thread_id,
                requires_human_approval=True,
            )
        
        # Check if workflow marked the result as requiring human approval
        if analysis_result.requires_human_approval:
            logger.info(f"Workflow requires human approval for thread {analysis_result.thread_id}")
            
            # Broadcast pause notification
            await manager.broadcast_alert(
                "workflow_paused_for_approval",
                f"Human approval needed for {analysis_result.risk_level} risk level",
                severity="high",
            )
            await manager.broadcast_status(
                "paused_for_human_review",
                {
                    "thread_id": analysis_result.thread_id,
                    "risk_level": analysis_result.risk_level,
                    "action": "Use /approve or /reject endpoint with thread_id",
                }
            )
            
            # Return response indicating pause
            return GridStateResponse(
                timestamp=datetime.now().isoformat(),
                grid_state=grid_state,
                risk_analysis={
                    "risk_level": analysis_result.risk_level,
                    "status": "paused_for_human_review",
                    "message": f"Human approval required for {analysis_result.risk_level} risk level",
                    "recommendations": [
                        {
                            "action": rec.action,
                            "priority": rec.priority,
                            "affected_zones": rec.affected_zones,
                        }
                        for rec in analysis_result.recommendations
                    ],
                    "analysis": analysis_result.analysis,
                },
                optimization_plans=[],
                selected_plan=None,
                thread_id=analysis_result.thread_id,
                requires_human_approval=True,
            )
        
        risk_analysis = {
            "risk_level": analysis_result.risk_level,
            "recommendations": [
                {
                    "action": rec.action,
                    "priority": rec.priority,
                    "affected_zones": rec.affected_zones,
                }
                for rec in analysis_result.recommendations
            ],
            "analysis": analysis_result.analysis,
            "avg_confidence": analysis_result.avg_confidence,
        }
        
        # ====== STEP 2: Generate Optimization Strategies ======
        await manager.broadcast_status(
            "optimizing", {"stage": "Generating optimization plans..."}
        )
        
        # Prepare zones for optimizer
        zones_for_optimization = [
            {
                "name": z.name,
                "protected": z.protected,
            }
            for z in request.zones
        ]
        
        # Run optimization
        strategies = optimizer.optimize(
            demand=request.demand,
            supply=request.supply,
            zones=zones_for_optimization,
            risk_level=analysis_result.risk_level,
        )
        
        # Format strategies for transmission
        formatted_strategies = format_strategies_for_websocket(strategies)
        
        # Select best strategy based on risk level
        selected_plan = _select_strategy(
            formatted_strategies, analysis_result.risk_level
        )
        
        # ====== STEP 3: Broadcast via WebSocket ======
        complete_update = {
            "demand": request.demand,
            "supply": request.supply,
            "temperature": request.temperature,
            "zones": grid_state["zones"],
            "risk_level": analysis_result.risk_level,
            "analysis": risk_analysis,
            "optimization_plans": formatted_strategies,
            "selected_strategy_id": selected_plan,
            "thread_id": analysis_result.thread_id,
            "avg_confidence": analysis_result.avg_confidence,
        }
        
        await manager.broadcast_grid_state(complete_update)
        
        # Broadcast optimization update separately
        await manager.broadcast_optimization_update(
            strategies=formatted_strategies,
            selected_strategy_id=selected_plan,
            reason=f"Recommended for {analysis_result.risk_level} risk level",
        )
        
        # Broadcast success status
        await manager.broadcast_status("healthy", {"stage": "Analysis complete"})
        
        # ====== STEP 4: Return Response ======
        return GridStateResponse(
            timestamp=datetime.now().isoformat(),
            grid_state=grid_state,
            risk_analysis=risk_analysis,
            optimization_plans=formatted_strategies,
            selected_plan=selected_plan,
            thread_id=analysis_result.thread_id,
            requires_human_approval=False,
        )
    
    except ValueError as e:
        await manager.broadcast_alert(
            "optimization_error",
            str(e),
            severity="critical",
        )
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Grid state analysis failed: {str(e)}", exc_info=True)
        await manager.broadcast_alert(
            "internal_error",
            f"Grid state analysis failed: {str(e)}",
            severity="critical",
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


# HITL (Human-in-the-Loop) Approval Endpoints


@app.get("/paused-workflows", response_model=Dict[str, List[PausedWorkflowInfo]])
async def get_paused_workflows():
    """
    Get all workflows currently paused for human review.
    
    Returns:
        Dictionary with list of paused workflow information
    """
    paused_list = []
    for thread_id, thread_data in workflow.active_threads.items():
        state = thread_data["state"]
        
        # Ensure recommendations are properly formatted
        recs = state.get("recommendations", [])
        if recs and hasattr(recs[0], 'model_dump'):
            # Pydantic models - convert to dicts
            recs = [r.model_dump() for r in recs]
        elif recs and isinstance(recs[0], dict):
            # Already dicts, use as-is
            pass
        else:
            # Fallback
            recs = []
        
        paused_list.append(
            PausedWorkflowInfo(
                thread_id=thread_id,
                paused_at=thread_data["paused_at"],
                reason=thread_data["reason"],
                risk_level=state.get("risk_level", "unknown"),
                recommendations=recs,
                analysis=state.get("analysis", {}),
            )
        )
    
    logger.info(f"[HITL] Retrieved {len(paused_list)} paused workflows")
    return {"paused_workflows": paused_list}


@app.post("/approve/{thread_id}", response_model=ApprovalResponse)
async def approve_workflow(thread_id: str, reason: str = "Approved by operator"):
    """
    Approve a paused workflow and resume execution.
    
    Args:
        thread_id: Thread ID of the paused workflow
        reason: Optional reason for approval
    
    Returns:
        ApprovalResponse with result of approval
    """
    try:
        if thread_id not in workflow.active_threads:
            logger.warning(f"[HITL] Approval attempt for non-existent thread: {thread_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Paused workflow with thread_id '{thread_id}' not found",
            )
        
        logger.info(f"[HITL] Approving workflow: {thread_id}")
        
        # Resume workflow with approval
        result = workflow.resume_workflow(thread_id, action="approve")
        
        # Broadcast approval to WebSocket clients
        await manager.broadcast_alert(
            "workflow_approved",
            f"Operator approved workflow {thread_id}: {reason}",
            severity="info",
        )
        
        return ApprovalResponse(
            action="approve",
            thread_id=thread_id,
            status="success",
            timestamp=datetime.now().isoformat(),
            message=f"Workflow approved and resumed. Risk level: {result.risk_level}",
            result={
                "risk_level": result.risk_level,
                "human_approved": result.human_approved,
                "avg_confidence": result.avg_confidence,
                "recommendations": [
                    {
                        "action": rec.action,
                        "priority": rec.priority,
                        "affected_zones": rec.affected_zones,
                    }
                    for rec in result.recommendations
                ],
            },
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[HITL] Approval failed for {thread_id}: {str(e)}", exc_info=True)
        await manager.broadcast_alert(
            "workflow_approval_error",
            f"Error approving workflow {thread_id}: {str(e)}",
            severity="high",
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to approve workflow: {str(e)}",
        )


@app.post("/reject/{thread_id}", response_model=ApprovalResponse)
async def reject_workflow(thread_id: str, reason: str = "Rejected by operator"):
    """
    Reject a paused workflow and discard it.
    
    Args:
        thread_id: Thread ID of the paused workflow
        reason: Optional reason for rejection
    
    Returns:
        ApprovalResponse with result of rejection
    """
    try:
        if thread_id not in workflow.active_threads:
            logger.warning(f"[HITL] Rejection attempt for non-existent thread: {thread_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Paused workflow with thread_id '{thread_id}' not found",
            )
        
        logger.info(f"[HITL] Rejecting workflow: {thread_id}")
        
        # Resume workflow with rejection
        result = workflow.resume_workflow(thread_id, action="reject")
        
        # Broadcast rejection to WebSocket clients
        await manager.broadcast_alert(
            "workflow_rejected",
            f"Operator rejected workflow {thread_id}: {reason}",
            severity="warning",
        )
        
        return ApprovalResponse(
            action="reject",
            thread_id=thread_id,
            status="success",
            timestamp=datetime.now().isoformat(),
            message=f"Workflow rejected and discarded. No further action taken.",
            result={
                "status": "rejected",
                "reason": reason,
            },
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[HITL] Rejection failed for {thread_id}: {str(e)}", exc_info=True)
        await manager.broadcast_alert(
            "workflow_rejection_error",
            f"Error rejecting workflow {thread_id}: {str(e)}",
            severity="high",
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reject workflow: {str(e)}",
        )

# WebSocket Endpoint for Real-Time Streaming + HITL Commands


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time grid state and optimization updates.
    
    Connected clients receive:
    - Grid state updates (demand, supply, temperature, zones)
    - Risk analysis results with confidence scores
    - Optimization plans (3 distinct strategies)
    - Alerts and status updates
    - HITL pause/approval notifications
    
    Message types (broadcast):
    - grid_state: Full grid analysis update
    - optimization_update: New optimization strategies
    - alert: Critical alerts (overload, disaster, HITL, etc.)
    - status: System status updates (healthy, analyzing, optimizing, paused_for_human_review)
    
    Commands accepted (client -> server):
    - {"type": "request_history", "limit": 10}
    - {"type": "ping"}
    - {"type": "approve_plan", "thread_id": "uuid", "reason": "optional"}
    - {"type": "reject_plan", "thread_id": "uuid", "reason": "optional"}
    """
    await manager.connect(websocket)
    
    try:
        while True:
            # Keep connection alive and receive any client messages
            data = await websocket.receive_text()
            
            # Handle client messages
            try:
                message = json.loads(data)
                msg_type = message.get("type")
                
                # Request history
                if msg_type == "request_history":
                    limit = message.get("limit", 10)
                    history = manager.get_recent_history(limit)
                    await manager.send_to_client(
                        websocket,
                        {
                            "type": "history_response",
                            "messages": history,
                        },
                    )
                
                # Heartbeat ping
                elif msg_type == "ping":
                    await manager.send_to_client(
                        websocket,
                        {
                            "type": "pong",
                            "timestamp": datetime.now().isoformat(),
                        },
                    )
                
                # HITL: Approve Plan
                elif msg_type == "approve_plan":
                    thread_id = message.get("thread_id")
                    reason = message.get("reason", "Approved via WebSocket")
                    
                    if not thread_id:
                        await manager.send_to_client(
                            websocket,
                            {
                                "type": "error",
                                "message": "Missing thread_id for approve_plan",
                            },
                        )
                        continue
                    
                    try:
                        logger.info(f"[WS-HITL] Approving plan: {thread_id}")
                        result = workflow.resume_workflow(thread_id, action="approve")
                        
                        await manager.broadcast_alert(
                            "workflow_approved_via_ws",
                            f"Plan approved via WebSocket. Risk: {result.risk_level}",
                            severity="info",
                        )
                        
                        await manager.send_to_client(
                            websocket,
                            {
                                "type": "approval_response",
                                "action": "approve",
                                "thread_id": thread_id,
                                "status": "success",
                                "reason": reason,
                                "risk_level": result.risk_level,
                                "avg_confidence": result.avg_confidence,
                            },
                        )
                    
                    except Exception as e:
                        logger.error(f"[WS-HITL] Approval error: {str(e)}")
                        await manager.send_to_client(
                            websocket,
                            {
                                "type": "approval_response",
                                "action": "approve",
                                "thread_id": thread_id,
                                "status": "error",
                                "error": str(e),
                            },
                        )
                
                # HITL: Reject Plan
                elif msg_type == "reject_plan":
                    thread_id = message.get("thread_id")
                    reason = message.get("reason", "Rejected via WebSocket")
                    
                    if not thread_id:
                        await manager.send_to_client(
                            websocket,
                            {
                                "type": "error",
                                "message": "Missing thread_id for reject_plan",
                            },
                        )
                        continue
                    
                    try:
                        logger.info(f"[WS-HITL] Rejecting plan: {thread_id}")
                        result = workflow.resume_workflow(thread_id, action="reject")
                        
                        await manager.broadcast_alert(
                            "workflow_rejected_via_ws",
                            f"Plan rejected via WebSocket: {reason}",
                            severity="warning",
                        )
                        
                        await manager.send_to_client(
                            websocket,
                            {
                                "type": "approval_response",
                                "action": "reject",
                                "thread_id": thread_id,
                                "status": "success",
                                "reason": reason,
                            },
                        )
                    
                    except Exception as e:
                        logger.error(f"[WS-HITL] Rejection error: {str(e)}")
                        await manager.send_to_client(
                            websocket,
                            {
                                "type": "approval_response",
                                "action": "reject",
                                "thread_id": thread_id,
                                "status": "error",
                                "error": str(e),
                            },
                        )
            
            except json.JSONDecodeError:
                pass  # Ignore invalid JSON
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ============================================================================
# Utility Endpoints
# ============================================================================

@app.get("/strategies-info")
async def get_strategies_info():
    """Get information about the 3 optimization strategies."""
    return {
        "strategies": [
            {
                "id": 1,
                "name": "Gradual Reduction",
                "description": "Slight reduction across all non-protected zones",
                "use_case": "Minor supply shortages (< 10% deficit)",
                "risk_level": "low",
            },
            {
                "id": 2,
                "name": "Full Industrial Cut",
                "description": "Full reduction to non-essential zones, protects residential",
                "use_case": "Severe shortages (> 20% deficit)",
                "risk_level": "high",
            },
            {
                "id": 3,
                "name": "Rotating Cuts",
                "description": "Fair rotating cuts with minimum service guarantee",
                "use_case": "Moderate shortages (10-20% deficit)",
                "risk_level": "medium",
            },
        ],
    }


@app.get("/ws-stats")
async def websocket_stats():
    """Get WebSocket server statistics."""
    return {
        "active_connections": manager.get_connection_count(),
        "broadcast_history_size": len(manager.broadcast_history),
        "recent_messages": manager.get_recent_history(5),
    }


@app.get("/workflow-info")
async def workflow_info():
    """Get information about the SAN (AI Analysis) workflow with HITL support."""
    graph_info = workflow.get_graph_structure()
    
    return {
        "workflow": "SAN - Smart Grid AI Multi-Agent Analysis System",
        "architecture": "Parallel fan-out/fan-in with HITL interrupts",
        "version": "2.0 (HITL + Parallel + Groq LLM)",
        "features": graph_info.get("key_features", []),
        "parallel_execution": {
            "enabled": True,
            "agents": ["grid_health_agent", "demand_agent", "disaster_agent"],
            "speedup": "2-3x faster than sequential",
        },
        "hitl_support": {
            "enabled": True,
            "trigger": "If risk_level is 'high' or 'critical'",
            "pause_node": "human_review",
            "resume_via": "/approve/{thread_id} or /reject/{thread_id}",
            "state_persistence": "MemorySaver (SQLite)",
        },
        "llm_integration": {
            "provider": "Groq",
            "model": "mixtral-8x7b-32768",
            "timeout": "15 seconds per agent",
            "fallback": "Rule-based analysis if LLM fails",
        },
        "confidence_tracking": {
            "per_agent": ["health_confidence", "demand_confidence", "disaster_confidence"],
            "average": "avg_confidence in risk_analysis",
        },
        "nodes": graph_info.get("nodes", []),
        "agents_detail": {
            "intake_agent": "Validates input and initializes thread_id",
            "grid_health_agent": "Groq LLM: Detects overload (demand vs supply)",
            "demand_agent": "Groq LLM: Predicts demand spikes from temperature",
            "disaster_agent": "Groq LLM: Analyzes extreme weather risks",
            "priority_agent": "Consolidates parallel results, protects critical zones",
            "human_review": "HITL: Pauses if risk is high/critical",
            "risk_assessment": "Final risk level + average confidence calculation",
        },
    }


# ============================================================================
# Helper Functions
# ============================================================================

def _select_strategy(
    strategies: List[Dict[str, Any]], risk_level: str
) -> Optional[int]:
    """
    Select the best strategy based on risk level.
    
    Args:
        strategies: List of 3 formatted strategies
        risk_level: Current risk level
    
    Returns:
        Strategy ID (1, 2, or 3) or None
    """
    strategy_selection = {
        "low": 1,        # Gradual Reduction - minimal disruption
        "medium": 3,     # Rotating Cuts - balanced approach
        "high": 2,       # Full Industrial Cut - protect critical
        "critical": 2,   # Full Industrial Cut - emergency mode
    }
    
    return strategy_selection.get(risk_level, 3)


@app.on_event("startup")
async def startup_event():
    """Called on server startup."""
    print("\n" + "=" * 70)
    print("Smart Grid Optimization Engine (RHY) - Starting Up")
    print("=" * 70)
    print("\nIntegrated Systems:")
    print("  • SAN (AI Multi-Agent Analysis System)")
    print("  • RHY (Optimization Engine with OR-Tools)")
    print("  • WebSocket Real-Time Broadcasting")
    print("\nEndpoints:")
    print("  • POST   /grid-state         - Analyze and optimize grid state")
    print("  • GET    /health             - Health check")
    print("  • GET    /strategies-info    - Strategy information")
    print("  • GET    /workflow-info      - SAN workflow information")
    print("  • GET    /ws-stats           - WebSocket statistics")
    print("  • WS     /ws                 - Real-time WebSocket stream")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    import uvicorn
    
    print("Starting server with: uvicorn backend.main:app --reload")
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
