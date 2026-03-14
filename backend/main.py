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
    name: str
    demand: float
    protected: bool = False

class GridState(BaseModel):
    demand: float
    supply: float
    temperature: float
    zones: List[Zone]

# ── In-memory state ────────────────────────────────────────────────────────────

latest_grid_state   = {}
latest_plans        = []
latest_ai_analysis  = {}
current_thread_id   = None   # active LangGraph thread — needed to resume HITL

# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/")
def health():
    return {"status": "Smart Grid Backend Running ✅"}


@app.post("/grid-state")
async def receive_grid_state(state: GridState):
    global latest_grid_state, latest_plans, latest_ai_analysis, current_thread_id

    latest_grid_state = state.dict()
    thread_id = str(uuid.uuid4())
    current_thread_id = thread_id

    # OR-Tools optimization — fast
    plans = optimize_power(latest_grid_state)
    latest_plans = plans

    # LangGraph multi-agent pipeline
    try:
        ai_analysis = run_analysis(latest_grid_state, thread_id)
        latest_ai_analysis = ai_analysis
    except Exception as e:
        print(f"[AI ERROR] {e}")
        ai_analysis = {
            "risk_level": "unknown",
            "risk_reason": "AI analysis unavailable",
            "recommendations": ["Manual assessment required"],
            "requires_human_approval": False,
            "avg_confidence": 0
        }
        latest_ai_analysis = ai_analysis

    requires_approval = ai_analysis.get("risk_level") in ["high", "critical"]

    await manager.broadcast({
        "type": "plans",
        "thread_id": thread_id,
        "grid_state": latest_grid_state,
        "plans": plans,
        "ai_analysis": ai_analysis,
        "requires_human_approval": requires_approval
    })

    return {
        "status": "ok",
        "plans_generated": len(plans),
        "risk_level": ai_analysis.get("risk_level"),
        "thread_id": thread_id,
        "requires_human_approval": requires_approval
    }


@app.get("/status")
def get_status():
    return {
        "grid_state": latest_grid_state,
        "plans": latest_plans,
        "ai_analysis": latest_ai_analysis,
        "thread_id": current_thread_id
    }


# ── WebSocket ──────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send current state immediately on connect
        if latest_grid_state:
            await websocket.send_json({
                "type": "plans",
                "thread_id": current_thread_id,
                "grid_state": latest_grid_state,
                "plans": latest_plans,
                "ai_analysis": latest_ai_analysis,
                "requires_human_approval": latest_ai_analysis.get("requires_human_approval", False)
            })

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            # ── HITL: Operator approves a plan ───────────────────────────────
            if msg_type == "apply_plan":
                plan_id  = data.get("plan_id")
                note     = data.get("note", "No note provided")
                thread_id = data.get("thread_id") or current_thread_id

                print(f"\n\033[92m[HITL] ✅ Operator approved Plan {plan_id} | Thread: {thread_id}\033[0m")
                print(f"\033[92m[HITL]    Note: {note}\033[0m\n")

                # Resume the paused LangGraph thread
                try:
                    resume_with_human_decision(thread_id, {
                        "decision": "approve",
                        "plan_id": plan_id,
                        "note": note
                    })
                except Exception as e:
                    print(f"[HITL] Resume note: {e}")

                await manager.broadcast({
                    "type": "plan_applied",
                    "plan_id": plan_id,
                    "thread_id": thread_id,
                    "operator_note": note,
                    "message": f"✅ Operator applied Plan {plan_id}: {note}"
                })

            # ── HITL: Operator rejects all plans ─────────────────────────────
            elif msg_type == "reject_plans":
                reason    = data.get("reason", "Operator override")
                thread_id = data.get("thread_id") or current_thread_id

                print(f"\n\033[91m[HITL] ❌ Operator REJECTED all plans | Thread: {thread_id}\033[0m")
                print(f"\033[91m[HITL]    Reason: {reason}\033[0m\n")

                try:
                    resume_with_human_decision(thread_id, {
                        "decision": "reject",
                        "reason": reason
                    })
                except Exception as e:
                    print(f"[HITL] Resume note: {e}")

                await manager.broadcast({
                    "type": "plans_rejected",
                    "reason": reason,
                    "message": f"❌ All plans rejected: {reason}"
                })

            # ── Manual override ───────────────────────────────────────────────
            elif msg_type == "manual_override":
                action = data.get("action")
                print(f"\n\033[93m[HITL] 🔧 Manual override: {action}\033[0m\n")
                await manager.broadcast({
                    "type": "override_applied",
                    "action": action,
                    "message": f"🔧 Manual override: {action}"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)