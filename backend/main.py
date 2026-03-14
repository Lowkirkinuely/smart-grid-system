import os
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

load_dotenv()

from websocket_manager import manager
from optimizer import optimize_power
from ai_agents.graph import run_analysis, resume_with_human_decision

app = FastAPI(title="Smart Grid — Human-in-the-Loop Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ─────────────────────────────────────────────────────────────────────

class Zone(BaseModel):
    name:      str
    demand:    float
    protected: bool = False

class GridState(BaseModel):
    demand:      float
    supply:      float
    temperature: float
    zones:       List[Zone]

# ── In-memory state ────────────────────────────────────────────────────────────

latest_grid_state  = {}
latest_plans       = []
latest_ai_analysis = {}
current_thread_id  = None
paused_threads: set = set()   # threads actually paused at LangGraph interrupt

# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/")
def health():
    return {"status": "Smart Grid Backend Running ✅"}


@app.post("/grid-state")
async def receive_grid_state(state: GridState):
    global latest_grid_state, latest_plans, latest_ai_analysis, current_thread_id

    latest_grid_state = state.dict()
    thread_id         = str(uuid.uuid4())
    current_thread_id = thread_id

    # OR-Tools — fast, synchronous
    plans        = optimize_power(latest_grid_state)
    latest_plans = plans

    # LangGraph multi-agent pipeline
    try:
        ai_analysis        = run_analysis(latest_grid_state, thread_id)
        latest_ai_analysis = ai_analysis
    except Exception as e:
        print(f"[AI ERROR] {e}")
        ai_analysis = {
            "risk_level":              "unknown",
            "risk_reason":             "AI analysis unavailable",
            "recommendations":         ["Manual assessment required"],
            "requires_human_approval": False,
            "avg_confidence":          0.0,
            "agent_errors":            {"pipeline": str(e)}
        }
        latest_ai_analysis = ai_analysis

    requires_approval = ai_analysis.get("risk_level") in ["high", "critical"]

    # Register thread as paused only if HITL gate was triggered
    if requires_approval:
        paused_threads.add(thread_id)

    await manager.broadcast({
        "type":                    "plans",
        "thread_id":               thread_id,
        "grid_state":              latest_grid_state,
        "plans":                   plans,
        "ai_analysis":             ai_analysis,
        "requires_human_approval": requires_approval
    })

    return {
        "status":                  "ok",
        "plans_generated":         len(plans),
        "risk_level":              ai_analysis.get("risk_level"),
        "thread_id":               thread_id,
        "requires_human_approval": requires_approval
    }


@app.get("/status")
def get_status():
    return {
        "grid_state":      latest_grid_state,
        "plans":           latest_plans,
        "ai_analysis":     latest_ai_analysis,
        "thread_id":       current_thread_id,
        "paused_threads":  list(paused_threads)
    }


# ── WebSocket ──────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send current state immediately on connect
        if latest_grid_state:
            await websocket.send_json({
                "type":                    "plans",
                "thread_id":               current_thread_id,
                "grid_state":              latest_grid_state,
                "plans":                   latest_plans,
                "ai_analysis":             latest_ai_analysis,
                "requires_human_approval": latest_ai_analysis.get("requires_human_approval", False)
            })

        while True:
            data     = await websocket.receive_json()
            msg_type = data.get("type")

            # ── HITL: Operator approves a plan ───────────────────────────────
            if msg_type == "apply_plan":
                plan_id   = data.get("plan_id")
                note      = data.get("note", "No note provided")
                thread_id = data.get("thread_id")

                # Validate thread is actually paused at interrupt
                if not thread_id or thread_id not in paused_threads:
                    await websocket.send_json({
                        "type":    "error",
                        "message": (
                            f"Thread '{thread_id}' is not paused or does not exist. "
                            f"Currently paused: {list(paused_threads)}"
                        )
                    })
                    continue

                print(f"\n\033[92m[HITL] ✅ Operator approved Plan {plan_id} | Thread: {thread_id}\033[0m")
                print(f"\033[92m[HITL]    Note: {note}\033[0m\n")

                try:
                    resume_with_human_decision(thread_id, {
                        "decision": "approve",
                        "plan_id":  plan_id,
                        "note":     note
                    })
                    paused_threads.discard(thread_id)
                except Exception as e:
                    await websocket.send_json({
                        "type":    "error",
                        "message": f"Failed to resume thread {thread_id}: {str(e)}"
                    })
                    continue

                await manager.broadcast({
                    "type":          "plan_applied",
                    "plan_id":       plan_id,
                    "thread_id":     thread_id,
                    "operator_note": note,
                    "message":       f"✅ Operator applied Plan {plan_id}: {note}"
                })

            # ── HITL: Operator rejects all plans ─────────────────────────────
            elif msg_type == "reject_plans":
                reason    = data.get("reason", "Operator override")
                thread_id = data.get("thread_id")

                if not thread_id or thread_id not in paused_threads:
                    await websocket.send_json({
                        "type":    "error",
                        "message": f"Thread '{thread_id}' is not paused."
                    })
                    continue

                print(f"\n\033[91m[HITL] ❌ Operator REJECTED all plans | Thread: {thread_id}\033[0m")
                print(f"\033[91m[HITL]    Reason: {reason}\033[0m\n")

                try:
                    resume_with_human_decision(thread_id, {
                        "decision": "reject",
                        "reason":   reason
                    })
                    paused_threads.discard(thread_id)
                except Exception as e:
                    await websocket.send_json({
                        "type":    "error",
                        "message": f"Failed to resume thread {thread_id}: {str(e)}"
                    })
                    continue

                await manager.broadcast({
                    "type":    "plans_rejected",
                    "reason":  reason,
                    "message": f"❌ All plans rejected: {reason}"
                })

            # ── Manual override ───────────────────────────────────────────────
            elif msg_type == "manual_override":
                action = data.get("action")
                print(f"\n\033[93m[HITL] 🔧 Manual override: {action}\033[0m\n")
                await manager.broadcast({
                    "type":    "override_applied",
                    "action":  action,
                    "message": f"🔧 Manual override applied: {action}"
                })

            # ── Heartbeat response ────────────────────────────────────────────
            elif msg_type == "pong":
                pass   # client acknowledged ping, connection is alive

            # ── Unknown message type ──────────────────────────────────────────
            else:
                await websocket.send_json({
                    "type":    "error",
                    "message": f"Unknown message type: '{msg_type}'"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WS ERROR] {e}")
        manager.disconnect(websocket)