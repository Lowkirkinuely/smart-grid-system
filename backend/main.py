"""
Smart Grid — Human-in-the-Loop Backend
FastAPI server with AI agents, OR-Tools optimization, HITL WebSocket, MongoDB persistence.
"""

import os
import uuid
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from langgraph.errors import GraphInterrupt

load_dotenv()

if not os.getenv("GROQ_API_KEY"):
    raise RuntimeError("GROQ_API_KEY is missing from .env file!")

from websocket_manager import manager
from optimizer import optimize_power, optimizer, format_plans_for_broadcast
from ai_agents.graph import run_analysis, resume_with_human_decision, get_graph_structure
from ml.model import ml_model
from database import db

logger = logging.getLogger(__name__)

# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Smart Grid — Human-in-the-Loop Backend",
    description="AI multi-agent analysis + OR-Tools optimization + HITL WebSocket + MongoDB",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request / Response models ──────────────────────────────────────────────────

class Zone(BaseModel):
    name:      str
    demand:    float
    protected: bool = False

class GridState(BaseModel):
    demand:      float = Field(..., ge=0, description="Total grid demand in MW")
    supply:      float = Field(..., ge=0, description="Available supply in MW")
    temperature: float = Field(..., description="Ambient temperature in Celsius")
    zones:       List[Zone]

class HealthResponse(BaseModel):
    status:             str
    service:            str
    version:            str
    timestamp:          str
    active_connections: int
    ml_samples:         int
    ml_trained:         bool
    paused_threads:     List[str]
    db_connected:       bool

class GridStateResponse(BaseModel):
    status:                  str
    timestamp:               str
    thread_id:               str
    plans_generated:         int
    risk_level:              str
    ml_risk_level:           str
    llm_risk_level:          str
    ml_llm_disagreement:     bool
    anomaly_detected:        bool
    requires_human_approval: bool

# ── In-memory state ────────────────────────────────────────────────────────────

latest_grid_state  = {}
latest_plans       = []
latest_ai_analysis = {}
current_thread_id  = None
paused_threads: set = set()
state_lock = asyncio.Lock()

# ── Lifecycle ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    await db.connect()
    print("\n" + "="*65)
    print("  Smart Grid — Human-in-the-Loop Backend  v2.0.0")
    print("="*65)
    print("  Endpoints:")
    print("    GET    /health                  Health check + ML stats")
    print("    POST   /grid-state              Analyze + optimize grid")
    print("    GET    /status                  Current state snapshot")
    print("    GET    /ml/stats                ML model learning progress")
    print("    GET    /workflow-info           LangGraph pipeline structure")
    print("    GET    /strategies-info         Optimizer plan descriptions")
    print("    GET    /ws-stats                WebSocket statistics")
    print("    GET    /history/grid            Grid state history (MongoDB)")
    print("    GET    /history/analyses        AI analysis history (MongoDB)")
    print("    GET    /history/decisions       Human decision audit log (MongoDB)")
    print("    GET    /history/decisions/stats Decision statistics (MongoDB)")
    print("    WS     /ws                      Real-time operator dashboard")
    print("="*65 + "\n")
    logger.info("[STARTUP] Smart Grid backend ready")


@app.on_event("shutdown")
async def shutdown_event():
    await db.disconnect()
    logger.info("[SHUTDOWN] Smart Grid backend stopped")

# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="healthy",
        service="Smart Grid — Human-in-the-Loop Backend",
        version="2.0.0",
        timestamp=datetime.now().isoformat(),
        active_connections=manager.get_connection_count(),
        ml_samples=len(ml_model.history_y),
        ml_trained=ml_model.is_trained,
        paused_threads=list(paused_threads),
        db_connected=db.is_connected
    )


@app.post("/grid-state", response_model=GridStateResponse)
async def receive_grid_state(state: GridState):
    global latest_grid_state, latest_plans, latest_ai_analysis, current_thread_id

    grid_dict = state.dict()
    thread_id = str(uuid.uuid4())

    logger.info(f"[GRID-STATE] New request | thread: {thread_id} | demand: {grid_dict['demand']}MW")

    # Broadcast pipeline start
    await manager.broadcast_status("analyzing", {
        "stage":     "Running parallel AI analysis + optimization...",
        "thread_id": thread_id
    })

    # OR-Tools — offloaded to thread so event loop stays free
    plans = await asyncio.to_thread(optimize_power, grid_dict)

    # LangGraph multi-agent pipeline
    try:
        ai_analysis = await asyncio.to_thread(run_analysis, grid_dict, thread_id)
    except GraphInterrupt:
        logger.warning(f"[GRID-STATE] Graph paused at HITL | thread: {thread_id}")
        ai_analysis = {
            "risk_level": "high", "risk_reason": "Paused for human review",
            "recommendations": ["Human approval required before proceeding"],
            "requires_human_approval": True, "avg_confidence": 0.0,
            "ml_risk_level": "unknown", "llm_risk_level": "unknown",
            "ml_llm_disagreement": False, "anomaly_detected": False,
            "agent_errors": {}
        }
    except Exception as e:
        logger.error(f"[GRID-STATE] AI pipeline error: {e}")
        ai_analysis = {
            "risk_level": "unknown", "risk_reason": "AI analysis unavailable",
            "recommendations": ["Manual assessment required"],
            "requires_human_approval": False, "avg_confidence": 0.0,
            "ml_risk_level": "unknown", "llm_risk_level": "unknown",
            "ml_llm_disagreement": False, "anomaly_detected": False,
            "agent_errors": {"pipeline": str(e)}
        }

    requires_approval = ai_analysis.get("requires_human_approval", False)

    # Recommended plan ID based on risk level
    recommended_plan = optimizer.select_recommended_plan(
        plans, ai_analysis.get("risk_level", "low")
    )

    # Safely update global state
    async with state_lock:
        latest_grid_state  = grid_dict
        latest_plans       = plans
        latest_ai_analysis = ai_analysis
        current_thread_id  = thread_id
        if requires_approval:
            paused_threads.add(thread_id)

    # Save to MongoDB — fire and forget, never blocks response
    asyncio.create_task(db.save_grid_state(grid_dict, thread_id))
    asyncio.create_task(db.save_analysis(thread_id, ai_analysis, plans))

    # Broadcast HITL alert if needed
    if requires_approval:
        await manager.broadcast_alert(
            alert_type="hitl_required",
            message=f"Human approval required — Risk: {ai_analysis.get('risk_level', 'unknown').upper()}",
            severity="critical" if ai_analysis.get("risk_level") == "critical" else "high",
            data={
                "thread_id":           thread_id,
                "risk_level":          ai_analysis.get("risk_level"),
                "time_to_act_minutes": ai_analysis.get("time_to_act_minutes"),
                "ml_llm_disagreement": ai_analysis.get("ml_llm_disagreement", False)
            }
        )

    # Main broadcast
    await manager.broadcast({
        "type":                    "plans",
        "thread_id":               thread_id,
        "timestamp":               datetime.now().isoformat(),
        "grid_state":              grid_dict,
        "plans":                   format_plans_for_broadcast(plans),
        "recommended_plan":        recommended_plan,
        "ai_analysis":             ai_analysis,
        "requires_human_approval": requires_approval
    })

    logger.info(
        f"[GRID-STATE] Complete | thread: {thread_id} | "
        f"risk: {ai_analysis.get('risk_level')} | HITL: {requires_approval}"
    )

    return GridStateResponse(
        status="ok",
        timestamp=datetime.now().isoformat(),
        thread_id=thread_id,
        plans_generated=len(plans),
        risk_level=ai_analysis.get("risk_level", "unknown"),
        ml_risk_level=ai_analysis.get("ml_risk_level", "unknown"),
        llm_risk_level=ai_analysis.get("llm_risk_level", "unknown"),
        ml_llm_disagreement=ai_analysis.get("ml_llm_disagreement", False),
        anomaly_detected=ai_analysis.get("anomaly_detected", False),
        requires_human_approval=requires_approval
    )


@app.get("/status")
async def get_status():
    async with state_lock:
        return {
            "grid_state":      latest_grid_state,
            "plans":           latest_plans,
            "ai_analysis":     latest_ai_analysis,
            "thread_id":       current_thread_id,
            "paused_threads":  list(paused_threads),
            "ml_samples":      len(ml_model.history_y),
            "ml_trained":      ml_model.is_trained,
            "db_connected":    db.is_connected,
            "timestamp":       datetime.now().isoformat()
        }


@app.get("/ml/stats")
def get_ml_stats():
    return {
        "training_samples":   len(ml_model.history_y),
        "is_trained":         ml_model.is_trained,
        "patterns_learned":   len(ml_model.history_y) >= 50,
        "label_distribution": {
            "low":      ml_model.history_y.count(0),
            "medium":   ml_model.history_y.count(1),
            "high":     ml_model.history_y.count(2),
            "critical": ml_model.history_y.count(3)
        }
    }


@app.get("/workflow-info")
def workflow_info():
    graph = get_graph_structure()
    return {
        "workflow":        "Smart Grid AI Multi-Agent Pipeline",
        "architecture":    "Parallel fan-out/fan-in with HITL interrupt",
        "version":         "2.0.0",
        "features":        graph.get("key_features", []),
        "nodes":           graph.get("nodes", []),
        "parallel_groups": graph.get("parallel_groups", []),
        "edges":           graph.get("edges", []),
        "hitl_support": {
            "enabled":    True,
            "trigger":    "risk_level in ['high', 'critical'] OR ml_llm_disagreement",
            "pause_node": "human_review",
            "resume_via": "WebSocket: apply_plan or reject_plans message"
        },
        "ml_integration": {
            "model":           "RandomForest + IsolationForest",
            "fusion":          "60% LLM + 40% ML weighted vote",
            "online_learning": "Retrains after every human approval"
        },
        "llm_integration": {
            "provider": "Groq",
            "model":    "llama-3.1-8b-instant",
            "timeout":  "15 seconds per agent"
        }
    }


@app.get("/strategies-info")
def strategies_info():
    return {
        "strategies": [
            {
                "plan_id": 1, "label": "Minimum Disruption (Optimal)",
                "description": "Mathematically least disruptive cut — OR-Tools optimal",
                "use_case": "When minimizing total MW cut is the priority",
                "recommended_for": ["low", "medium"]
            },
            {
                "plan_id": 2, "label": "Industrial Priority Cut",
                "description": "Cuts industrial zones first — minimizes residential impact",
                "use_case": "Heatwaves — protect residential cooling",
                "recommended_for": ["high", "critical"]
            },
            {
                "plan_id": 3, "label": "Residential Rotation",
                "description": "Distributes cuts across residential — protects industry",
                "use_case": "When industrial continuity is critical",
                "recommended_for": ["medium"]
            }
        ]
    }


@app.get("/ws-stats")
def websocket_stats():
    return {
        "active_connections":     manager.get_connection_count(),
        "broadcast_history_size": len(manager.broadcast_history),
        "recent_messages":        manager.get_recent_history(5),
        "paused_threads":         list(paused_threads)
    }


# ── MongoDB history endpoints ──────────────────────────────────────────────────

@app.get("/history/grid")
async def grid_history(limit: int = 50):
    """Last N grid readings from simulator."""
    return await db.get_grid_history(limit)


@app.get("/history/analyses")
async def analysis_history(limit: int = 20):
    """Last N AI pipeline results."""
    return await db.get_recent_analyses(limit)


@app.get("/history/decisions")
async def decision_history(limit: int = 50):
    """Full human decision audit log."""
    return await db.get_decision_history(limit)


@app.get("/history/decisions/stats")
async def decision_stats():
    """Aggregated stats on human decisions."""
    return await db.get_decision_stats()


# ── WebSocket ──────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send current state immediately on connect
        async with state_lock:
            snapshot = (
                latest_grid_state, current_thread_id,
                latest_plans, latest_ai_analysis
            ) if latest_grid_state else None

        if snapshot:
            gs, tid, plans, ai = snapshot
            await websocket.send_json({
                "type":                    "plans",
                "thread_id":               tid,
                "timestamp":               datetime.now().isoformat(),
                "grid_state":              gs,
                "plans":                   format_plans_for_broadcast(plans),
                "recommended_plan":        optimizer.select_recommended_plan(plans, ai.get("risk_level", "low")),
                "ai_analysis":             ai,
                "requires_human_approval": ai.get("requires_human_approval", False)
            })

        while True:
            data     = await websocket.receive_json()
            msg_type = data.get("type")

            # ── HITL: Operator approves a plan ───────────────────────────────
            if msg_type == "apply_plan":
                plan_id   = data.get("plan_id")
                note      = data.get("note", "No note provided")
                thread_id = data.get("thread_id")

                async with state_lock:
                    is_valid = thread_id and thread_id in paused_threads
                    if is_valid:
                        paused_threads.discard(thread_id)
                        grid_copy = dict(latest_grid_state)
                        ai_copy   = dict(latest_ai_analysis)

                if not is_valid:
                    await manager.send_to_client(websocket, {
                        "type":    "error",
                        "message": f"Thread '{thread_id}' not paused. Paused: {list(paused_threads)}"
                    })
                    continue

                logger.info(f"[HITL] ✅ Plan {plan_id} approved | thread: {thread_id}")
                print(f"\n\033[92m[HITL] ✅ Plan {plan_id} approved | Thread: {thread_id}\033[0m")
                print(f"\033[92m[HITL]    Note: {note}\033[0m\n")

                try:
                    await asyncio.to_thread(resume_with_human_decision, thread_id, {
                        "decision": "approve", "plan_id": plan_id, "note": note
                    })
                except Exception as e:
                    logger.error(f"[HITL] Resume failed: {e}")
                    await manager.send_to_client(websocket, {
                        "type": "error", "message": f"Resume failed: {str(e)}"
                    })
                    continue

                # Online learning
                try:
                    confirmed_risk = ai_copy.get("risk_level", "unknown")
                    if confirmed_risk != "unknown":
                        await asyncio.to_thread(ml_model.update, grid_copy, confirmed_risk)
                        logger.info(f"[ML] Updated | risk: {confirmed_risk} | samples: {len(ml_model.history_y)}")
                        print(f"\033[35m[ML] Updated | risk: {confirmed_risk} | samples: {len(ml_model.history_y)}\033[0m")
                except Exception as e:
                    logger.warning(f"[ML] Update failed: {e}")

                # Save human decision to MongoDB
                asyncio.create_task(db.save_human_decision(
                    thread_id=thread_id,
                    decision_type="approve",
                    plan_id=plan_id,
                    note=note,
                    risk_level=ai_copy.get("risk_level", "unknown")
                ))
                asyncio.create_task(db.save_ml_update(
                    len(ml_model.history_y),
                    ai_copy.get("risk_level", "unknown")
                ))

                await manager.broadcast({
                    "type":          "plan_applied",
                    "plan_id":       plan_id,
                    "thread_id":     thread_id,
                    "operator_note": note,
                    "ml_samples":    len(ml_model.history_y),
                    "timestamp":     datetime.now().isoformat(),
                    "message":       f"✅ Operator applied Plan {plan_id}: {note}"
                })

            # ── HITL: Operator rejects all plans ─────────────────────────────
            elif msg_type == "reject_plans":
                reason    = data.get("reason", "Operator override")
                thread_id = data.get("thread_id")

                async with state_lock:
                    is_valid = thread_id and thread_id in paused_threads
                    if is_valid:
                        paused_threads.discard(thread_id)
                        grid_copy = dict(latest_grid_state)
                        ai_copy   = dict(latest_ai_analysis)

                if not is_valid:
                    await manager.send_to_client(websocket, {
                        "type": "error", "message": f"Thread '{thread_id}' not paused."
                    })
                    continue

                logger.info(f"[HITL] ❌ Plans rejected | thread: {thread_id} | reason: {reason}")
                print(f"\n\033[91m[HITL] ❌ Plans REJECTED | Thread: {thread_id} | Reason: {reason}\033[0m\n")

                try:
                    await asyncio.to_thread(resume_with_human_decision, thread_id, {
                        "decision": "reject", "reason": reason
                    })
                except Exception as e:
                    logger.error(f"[HITL] Resume failed: {e}")
                    await manager.send_to_client(websocket, {
                        "type": "error", "message": f"Resume failed: {str(e)}"
                    })
                    continue

                # Learn from rejection
                try:
                    rejected_risk = data.get("confirmed_risk")
                    if rejected_risk and rejected_risk != "unknown":
                        await asyncio.to_thread(ml_model.update, grid_copy, rejected_risk)
                        logger.info(f"[ML] Updated from rejection | risk: {rejected_risk}")
                        print(f"\033[35m[ML] Updated from rejection | risk: {rejected_risk}\033[0m")
                except Exception as e:
                    logger.warning(f"[ML] Update from rejection failed: {e}")

                # Save to MongoDB
                asyncio.create_task(db.save_human_decision(
                    thread_id=thread_id,
                    decision_type="reject",
                    plan_id=None,
                    note=reason,
                    risk_level=ai_copy.get("risk_level", "unknown"),
                    confirmed_risk=data.get("confirmed_risk")
                ))

                await manager.broadcast({
                    "type":      "plans_rejected",
                    "reason":    reason,
                    "thread_id": thread_id,
                    "timestamp": datetime.now().isoformat(),
                    "message":   f"❌ All plans rejected: {reason}"
                })

            # ── Manual override ───────────────────────────────────────────────
            elif msg_type == "manual_override":
                action = data.get("action")
                logger.info(f"[HITL] Manual override: {action}")
                print(f"\n\033[93m[HITL] 🔧 Manual override: {action}\033[0m\n")
                await manager.broadcast({
                    "type":      "override_applied",
                    "action":    action,
                    "timestamp": datetime.now().isoformat(),
                    "message":   f"🔧 Manual override: {action}"
                })

            # ── Heartbeat ─────────────────────────────────────────────────────
            elif msg_type == "pong":
                pass

            # ── Unknown ───────────────────────────────────────────────────────
            else:
                await manager.send_to_client(websocket, {
                    "type":    "error",
                    "message": f"Unknown message type: '{msg_type}'"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"[WS ERROR] {e}")
        manager.disconnect(websocket)