import os
import uuid
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

load_dotenv()

if not os.getenv("GROQ_API_KEY"):
    raise RuntimeError("GROQ_API_KEY is missing from .env file!")

from websocket_manager import manager
from optimizer import optimize_power
from ai_agents.graph import run_analysis, resume_with_human_decision
from ml.model import ml_model

app = FastAPI(title="Smart Grid — Human-in-the-Loop Backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class Zone(BaseModel):
    name:      str
    demand:    float
    protected: bool = False

class GridState(BaseModel):
    demand:      float
    supply:      float
    temperature: float
    zones:       List[Zone]

latest_grid_state  = {}
latest_plans       = []
latest_ai_analysis = {}
current_thread_id  = None
paused_threads: set = set()
state_lock = asyncio.Lock()

@app.get("/")
def health():
    return {
        "status":         "Smart Grid Backend Running ✅",
        "ml_samples":     len(ml_model.history_y),
        "ml_trained":     ml_model.is_trained,
        "paused_threads": list(paused_threads)
    }

@app.post("/grid-state")
async def receive_grid_state(state: GridState):
    global latest_grid_state, latest_plans, latest_ai_analysis, current_thread_id

    grid_dict = state.dict()
    thread_id = str(uuid.uuid4())

    plans = await asyncio.to_thread(optimize_power, grid_dict)

    try:
        ai_analysis = await asyncio.to_thread(run_analysis, grid_dict, thread_id)
    except Exception as e:
        print(f"[AI ERROR] {e}")
        ai_analysis = {
            "risk_level": "unknown", "risk_reason": "AI analysis unavailable",
            "recommendations": ["Manual assessment required"],
            "requires_human_approval": False, "avg_confidence": 0.0,
            "ml_risk_level": "unknown", "llm_risk_level": "unknown",
            "ml_llm_disagreement": False, "anomaly_detected": False,
            "agent_errors": {"pipeline": str(e)}
        }

    requires_approval = ai_analysis.get("requires_human_approval", False)

    async with state_lock:
        latest_grid_state  = grid_dict
        latest_plans       = plans
        latest_ai_analysis = ai_analysis
        current_thread_id  = thread_id
        if requires_approval:
            paused_threads.add(thread_id)

    await manager.broadcast({
        "type": "plans", "thread_id": thread_id,
        "grid_state": grid_dict, "plans": plans,
        "ai_analysis": ai_analysis,
        "requires_human_approval": requires_approval
    })

    return {
        "status": "ok", "plans_generated": len(plans),
        "risk_level": ai_analysis.get("risk_level"),
        "ml_risk_level": ai_analysis.get("ml_risk_level"),
        "llm_risk_level": ai_analysis.get("llm_risk_level"),
        "ml_llm_disagreement": ai_analysis.get("ml_llm_disagreement", False),
        "anomaly_detected": ai_analysis.get("anomaly_detected", False),
        "thread_id": thread_id,
        "requires_human_approval": requires_approval
    }

@app.get("/status")
async def get_status():
    async with state_lock:
        return {
            "grid_state": latest_grid_state, "plans": latest_plans,
            "ai_analysis": latest_ai_analysis, "thread_id": current_thread_id,
            "paused_threads": list(paused_threads),
            "ml_samples": len(ml_model.history_y), "ml_trained": ml_model.is_trained
        }

@app.get("/ml/stats")
def get_ml_stats():
    return {
        "training_samples": len(ml_model.history_y),
        "is_trained": ml_model.is_trained,
        "patterns_learned": len(ml_model.history_y) >= 50,
        "label_distribution": {
            "low": ml_model.history_y.count(0), "medium": ml_model.history_y.count(1),
            "high": ml_model.history_y.count(2), "critical": ml_model.history_y.count(3)
        }
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        async with state_lock:
            snapshot = (latest_grid_state, current_thread_id, latest_plans,
                        latest_ai_analysis) if latest_grid_state else None

        if snapshot:
            gs, tid, plans, ai = snapshot
            await websocket.send_json({
                "type": "plans", "thread_id": tid, "grid_state": gs,
                "plans": plans, "ai_analysis": ai,
                "requires_human_approval": ai.get("requires_human_approval", False)
            })

        while True:
            data     = await websocket.receive_json()
            msg_type = data.get("type")

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
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Thread '{thread_id}' not paused. Paused: {list(paused_threads)}"
                    })
                    continue

                print(f"\n\033[92m[HITL] ✅ Plan {plan_id} approved | Thread: {thread_id}\033[0m")
                print(f"\033[92m[HITL]    Note: {note}\033[0m\n")

                try:
                    await asyncio.to_thread(resume_with_human_decision, thread_id, {
                        "decision": "approve", "plan_id": plan_id, "note": note
                    })
                except Exception as e:
                    await websocket.send_json({"type": "error", "message": f"Resume failed: {str(e)}"})
                    continue

                try:
                    confirmed_risk = ai_copy.get("risk_level", "unknown")
                    if confirmed_risk != "unknown":
                        await asyncio.to_thread(ml_model.update, grid_copy, confirmed_risk)
                        print(f"\033[35m[ML] Updated | risk: {confirmed_risk} | samples: {len(ml_model.history_y)}\033[0m")
                except Exception as e:
                    print(f"[ML] Update failed: {e}")

                await manager.broadcast({
                    "type": "plan_applied", "plan_id": plan_id, "thread_id": thread_id,
                    "operator_note": note, "ml_samples": len(ml_model.history_y),
                    "message": f"✅ Operator applied Plan {plan_id}: {note}"
                })

            elif msg_type == "reject_plans":
                reason    = data.get("reason", "Operator override")
                thread_id = data.get("thread_id")

                async with state_lock:
                    is_valid = thread_id and thread_id in paused_threads
                    if is_valid:
                        paused_threads.discard(thread_id)
                        grid_copy = dict(latest_grid_state)

                if not is_valid:
                    await websocket.send_json({"type": "error", "message": f"Thread '{thread_id}' not paused."})
                    continue

                print(f"\n\033[91m[HITL] ❌ Plans REJECTED | Thread: {thread_id} | Reason: {reason}\033[0m\n")

                try:
                    await asyncio.to_thread(resume_with_human_decision, thread_id, {
                        "decision": "reject", "reason": reason
                    })
                except Exception as e:
                    await websocket.send_json({"type": "error", "message": f"Resume failed: {str(e)}"})
                    continue

                try:
                    rejected_risk = data.get("confirmed_risk")
                    if rejected_risk and rejected_risk != "unknown":
                        await asyncio.to_thread(ml_model.update, grid_copy, rejected_risk)
                        print(f"\033[35m[ML] Updated from rejection | risk: {rejected_risk}\033[0m")
                except Exception as e:
                    print(f"[ML] Update from rejection failed: {e}")

                await manager.broadcast({
                    "type": "plans_rejected", "reason": reason,
                    "message": f"❌ All plans rejected: {reason}"
                })

            elif msg_type == "manual_override":
                action = data.get("action")
                print(f"\n\033[93m[HITL] 🔧 Manual override: {action}\033[0m\n")
                await manager.broadcast({
                    "type": "override_applied", "action": action,
                    "message": f"🔧 Manual override: {action}"
                })

            elif msg_type == "pong":
                pass

            else:
                await websocket.send_json({"type": "error", "message": f"Unknown type: '{msg_type}'"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WS ERROR] {e}")
        manager.disconnect(websocket)