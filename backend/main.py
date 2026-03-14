"""
Smart Grid — Human-in-the-Loop Backend
FastAPI server with AI agents, OR-Tools optimization, HITL WebSocket.
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

logger = logging.getLogger(__name__)

# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Smart Grid — Human-in-the-Loop Backend",
    description="AI multi-agent analysis + OR-Tools optimization + HITL WebSocket",
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
    type:      Optional[str] = None  # "hospital", "residential", "industrial", etc.

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

# ── Startup event ──────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    print("\n" + "="*65)
    print("  Smart Grid — Human-in-the-Loop Backend  v2.0.0")
    print("="*65)
    print("  Endpoints:")
    print("    GET    /health            Health check + ML stats")
    print("    POST   /grid-state        Analyze + optimize grid")
    print("    GET    /status            Current state snapshot")
    print("    GET    /ml/stats          ML model learning progress")
    print("    GET    /workflow-info     LangGraph pipeline structure")
    print("    GET    /strategies-info   Optimizer plan descriptions")
    print("    GET    /ws-stats          WebSocket statistics")
    print("    WS     /ws                Real-time operator dashboard")
    print("="*65 + "\n")
    logger.info("[STARTUP] Smart Grid backend ready")

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
        paused_threads=list(paused_threads)
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
    
    # Broadcast initial agent activity messages
    await manager.broadcast_agent_activity("GRID", "Data intake and validation started", "running")
    await manager.broadcast_agent_activity("ML", "Pattern analysis and anomaly detection initiated", "running")

    # OR-Tools — offloaded to thread so event loop stays free
    plans = await asyncio.to_thread(optimize_power, grid_dict)
    await manager.broadcast_agent_activity("OPTIMIZER", "OR-Tools optimization completed with 3 plan candidates", "complete")

    # Recommended plan based on risk (filled after AI analysis)
    try:
        ai_analysis = await asyncio.to_thread(run_analysis, grid_dict, thread_id)
        await manager.broadcast_agent_activity("RISK", "Multi-agent analysis complete - risk assessment ready", "complete")
    except GraphInterrupt:
        # Graph paused at HITL interrupt — this is expected for high/critical risk
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
            print(f"\n\033[93m[GRID-STATE] Thread PAUSED for human review:\033[0m")
            print(f"  thread_id: {thread_id}")
            print(f"  risk_level: {ai_analysis.get('risk_level', 'unknown')}")
            print(f"  requires_approval: {requires_approval}")
            print(f"  paused_threads: {list(paused_threads)}\n")
        else:
            print(f"\033[92m[GRID-STATE] Analysis complete (no approval needed):\033[0m")
            print(f"  thread_id: {thread_id}")
            print(f"  risk_level: {ai_analysis.get('risk_level', 'low')}\n")

    # Broadcast HITL alert if needed
    if requires_approval:
        await manager.broadcast_alert(
            alert_type="hitl_required",
            message=f"Human approval required — Risk: {ai_analysis.get('risk_level', 'unknown').upper()}",
            severity="critical" if ai_analysis.get("risk_level") == "critical" else "high",
            data={
                "thread_id":            thread_id,
                "risk_level":           ai_analysis.get("risk_level"),
                "time_to_act_minutes":  ai_analysis.get("time_to_act_minutes"),
                "ml_llm_disagreement":  ai_analysis.get("ml_llm_disagreement", False)
            }
        )

    # Main broadcast
    await manager.broadcast({
        "type":                    "plans",
        "thread_id":               thread_id,
        "timestamp":               datetime.now().isoformat(),
        "grid_state":              grid_dict,
        "plans":                   format_plans_for_broadcast(plans, grid_dict),
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
    """LangGraph pipeline structure — useful for demo."""
    graph = get_graph_structure()
    return {
        "workflow":         "Smart Grid AI Multi-Agent Pipeline",
        "architecture":     "Parallel fan-out/fan-in with HITL interrupt",
        "version":          "2.0.0",
        "features":         graph.get("key_features", []),
        "nodes":            graph.get("nodes", []),
        "parallel_groups":  graph.get("parallel_groups", []),
        "edges":            graph.get("edges", []),
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
    """Optimizer plan descriptions — useful for dashboard help text."""
    return {
        "strategies": [
            {
                "plan_id":     1,
                "label":       "Minimum Disruption (Optimal)",
                "description": "Mathematically least disruptive cut — OR-Tools optimal",
                "use_case":    "When minimizing total MW cut is the priority",
                "recommended_for": ["low", "medium"]
            },
            {
                "plan_id":     2,
                "label":       "Industrial Priority Cut",
                "description": "Cuts industrial zones first — minimizes residential impact",
                "use_case":    "Heatwaves — protect residential cooling",
                "recommended_for": ["high", "critical"]
            },
            {
                "plan_id":     3,
                "label":       "Residential Rotation",
                "description": "Distributes cuts across residential — protects industry",
                "use_case":    "When industrial continuity is critical",
                "recommended_for": ["medium"]
            }
        ]
    }


@app.get("/ws-stats")
def websocket_stats():
    return {
        "active_connections":    manager.get_connection_count(),
        "broadcast_history_size": len(manager.broadcast_history),
        "recent_messages":       manager.get_recent_history(5),
        "paused_threads":        list(paused_threads)
    }


# ── WebSocket ──────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send welcome message immediately on connect
        async with state_lock:
            paused_count = len(paused_threads)
        
        await websocket.send_json({
            "type": "welcome",
            "timestamp": datetime.now().isoformat(),
            "active_connections": len(manager.active_connections),
            "paused_threads": paused_count,
            "message": "Connected. Submit grid state via /grid-state endpoint to analyze."
        })

        while True:
            data     = await websocket.receive_json()
            msg_type = data.get("type")

            # ── HITL: Operator approves a plan ───────────────────────────────
            if msg_type == "apply_plan":
                plan_id   = data.get("plan_id")
                note      = data.get("note", "No note provided")
                thread_id = data.get("thread_id")
                
                print(f"\n\033[36m{'='*60}\033[0m")
                print(f"\033[36m[HITL-APPLY] Received apply_plan request\033[0m")
                print(f"  plan_id: {plan_id} (type: {type(plan_id)})")
                print(f"  thread_id: {thread_id}")
                print(f"  note: {note}")
                print(f"  Full data received: {data}")
                print(f"\033[36m{'='*60}\033[0m\n")

                async with state_lock:
                    is_valid = thread_id and thread_id in paused_threads
                    print(f"  is_valid (thread in paused_threads): {is_valid}")
                    print(f"  paused_threads: {list(paused_threads)}")
                    if is_valid:
                        paused_threads.discard(thread_id)
                        grid_copy = dict(latest_grid_state)
                        ai_copy   = dict(latest_ai_analysis)

                if not is_valid:
                    error_msg = f"Thread '{thread_id}' not in paused threads. Paused threads: {list(paused_threads)}"
                    print(f"  ❌ REJECTED: {error_msg}\n")
                    await manager.send_to_client(websocket, {
                        "type":    "error",
                        "message": error_msg
                    })
                    continue
                    
                print(f"  ✅ ACCEPTED: Thread removed from paused_threads\n")

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

                # Online learning — update ML with confirmed risk
                try:
                    confirmed_risk = ai_copy.get("risk_level", "unknown")
                    if confirmed_risk != "unknown":
                        await asyncio.to_thread(ml_model.update, grid_copy, confirmed_risk)
                        logger.info(f"[ML] Updated | risk: {confirmed_risk} | samples: {len(ml_model.history_y)}")
                        print(f"\033[35m[ML] Updated | risk: {confirmed_risk} | samples: {len(ml_model.history_y)}\033[0m")
                except Exception as e:
                    logger.warning(f"[ML] Update failed: {e}")

                await manager.broadcast({
                    "type":          "plan_applied",
                    "plan_id":       plan_id,
                    "thread_id":     thread_id,
                    "operator_note": note,
                    "ml_samples":    len(ml_model.history_y),
                    "timestamp":     datetime.now().isoformat(),
                    "message":       f"✅ Operator applied Plan {plan_id}: {note}"
                })
                
                # Calculate and broadcast updated grid state with load cuts applied
                print(f"\033[36m[HITL] Calculating post-execution grid state...\033[0m")
                
                try:
                    # Get the selected plan to calculate cuts
                    if latest_plans and plan_id <= len(latest_plans):
                        selected_plan = latest_plans[plan_id - 1]
                        cuts_list = selected_plan.get("cuts", [])
                        
                        print(f"  Plan {plan_id} cuts: {cuts_list}")
                        print(f"  Cuts type: {type(cuts_list)}")
                        if cuts_list and len(cuts_list) > 0:
                            print(f"  First cut: {cuts_list[0]} (type: {type(cuts_list[0])})")
                        
                        # Calculate power saved from cuts
                        # Cuts can be either strings (zone names) or objects with power_mw
                        total_power_saved = 0
                        
                        if cuts_list and isinstance(cuts_list[0], dict):
                            # Cuts are detailed objects with power_mw
                            total_power_saved = sum([cut.get("power_mw", 0) for cut in cuts_list])
                        else:
                            # Cuts are zone names - look up demand from grid
                            zones_by_name = {z["name"]: z for z in grid_copy.get("zones", [])}
                            for zone_name in cuts_list:
                                if zone_name in zones_by_name:
                                    total_power_saved += zones_by_name[zone_name].get("demand", 0)
                        
                        print(f"  Total power saved: {total_power_saved:.2f}MW")
                        
                        # Update grid state: reduce demand by power cuts
                        updated_grid = dict(grid_copy)
                        original_demand = updated_grid.get("demand", 0)
                        updated_grid["demand"] = max(0, original_demand - total_power_saved)
                        updated_grid["deficit_mw"] = max(0, updated_grid["demand"] - updated_grid.get("supply", 0))
                        
                        # Broadcast updated grid state
                        await manager.broadcast_grid_state_update(
                            updated_grid,
                            f"Plan {plan_id} executed: {total_power_saved:.1f}MW load cut applied"
                        )
                        
                        print(f"\033[36m[HITL] Grid state update broadcasted:\033[0m")
                        print(f"  Original demand: {original_demand:.1f}MW")
                        print(f"  Power cut: {total_power_saved:.1f}MW")
                        print(f"  New demand: {updated_grid['demand']:.1f}MW")
                        print(f"  Supply: {updated_grid.get('supply', 0):.1f}MW")
                        print(f"  New deficit: {updated_grid['deficit_mw']:.1f}MW\n")
                        
                        # Broadcast agent activity
                        await manager.broadcast_agent_activity(
                            "OPERATOR",
                            f"Approved {selected_plan.get('label', 'Plan')}: {note}",
                            "complete"
                        )
                        print(f"\033[36m[HITL] Agent activity broadcasted\033[0m\n")
                    else:
                        print(f"\033[91m[HITL] ERROR: Could not find plan {plan_id} in latest_plans\033[0m")
                        await manager.send_to_client(websocket, {
                            "type": "error",
                            "message": f"Plan {plan_id} not found in latest plans"
                        })
                except Exception as e:
                    print(f"\033[91m[HITL] ERROR during grid state calculation: {e}\033[0m")
                    import traceback
                    traceback.print_exc()
                    logger.error(f"[HITL] Grid update failed: {e}")
                    await manager.send_to_client(websocket, {
                        "type": "error",
                        "message": f"Grid state update failed: {str(e)}"
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

                # Learn from rejection if operator provides confirmed risk
                try:
                    rejected_risk = data.get("confirmed_risk")
                    if rejected_risk and rejected_risk != "unknown":
                        await asyncio.to_thread(ml_model.update, grid_copy, rejected_risk)
                        logger.info(f"[ML] Updated from rejection | risk: {rejected_risk}")
                        print(f"\033[35m[ML] Updated from rejection | risk: {rejected_risk}\033[0m")
                except Exception as e:
                    logger.warning(f"[ML] Update from rejection failed: {e}")

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