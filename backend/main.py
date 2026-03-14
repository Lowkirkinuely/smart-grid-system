import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

load_dotenv()

from websocket_manager import manager
from optimizer import optimize_power
from ai_agents.graph import run_analysis

app = FastAPI(title="Smart Grid Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ────────────────────────────────────────────────────────────────────

class Zone(BaseModel):
    name: str
    demand: float
    protected: bool = False

class GridState(BaseModel):
    demand: float
    supply: float
    temperature: float
    zones: List[Zone]

# ── In-memory state ───────────────────────────────────────────────────────────

latest_grid_state = {}
latest_plans = []
latest_ai_analysis = {}
pending_human_approval = None   # HITL: holds plan waiting for operator approval

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def health():
    return {"status": "Smart Grid Backend Running"}


@app.post("/grid-state")
async def receive_grid_state(state: GridState):
    """Receives grid data from SUM (simulator), runs AI + optimizer, broadcasts to dashboard."""
    global latest_grid_state, latest_plans, latest_ai_analysis, pending_human_approval

    latest_grid_state = state.dict()

    # Run optimizer (fast — OR-Tools)
    plans = optimize_power(latest_grid_state)
    latest_plans = plans

    # Run AI agent pipeline (LangGraph — 4 agents → synthesize)
    try:
        ai_analysis = run_analysis(latest_grid_state)
        latest_ai_analysis = ai_analysis
    except Exception as e:
        print(f"[AI] Analysis failed: {e}")
        ai_analysis = {
            "risk_level": "unknown",
            "risk_reason": "AI analysis unavailable",
            "recommendations": ["Manual assessment required"],
            "demand_trend": "unknown",
            "protected_zones_safe": True
        }
        latest_ai_analysis = ai_analysis

    # HITL: if risk is high/critical, flag for human approval before any action
    if ai_analysis.get("risk_level") in ["high", "critical"]:
        pending_human_approval = {
            "plans": plans,
            "ai_analysis": ai_analysis,
            "grid_state": latest_grid_state,
            "requires_approval": True
        }

    # Broadcast everything to dashboard
    await manager.broadcast({
        "type": "plans",
        "grid_state": latest_grid_state,
        "plans": plans,
        "ai_analysis": ai_analysis,
        "requires_human_approval": ai_analysis.get("risk_level") in ["high", "critical"]
    })

    return {
        "status": "ok",
        "plans_generated": len(plans),
        "risk_level": ai_analysis.get("risk_level")
    }


@app.get("/status")
def get_status():
    """Dashboard can poll this to get current state."""
    return {
        "grid_state": latest_grid_state,
        "plans": latest_plans,
        "ai_analysis": latest_ai_analysis,
        "pending_approval": pending_human_approval is not None
    }


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send current state on connect
        if latest_grid_state:
            await websocket.send_json({
                "type": "plans",
                "grid_state": latest_grid_state,
                "plans": latest_plans,
                "ai_analysis": latest_ai_analysis,
                "requires_human_approval": latest_ai_analysis.get("risk_level") in ["high", "critical"]
            })

        while True:
            data = await websocket.receive_json()

            # ── HUMAN-IN-THE-LOOP: Operator approves a plan ──────────────────
            if data.get("type") == "apply_plan":
                plan_id = data.get("plan_id")
                operator_note = data.get("note", "No note provided")

                # Log the human decision (visible in LangSmith if tracing on)
                print(f"[HITL] Operator approved Plan {plan_id}. Note: {operator_note}")

                # Clear pending approval
                global pending_human_approval
                pending_human_approval = None

                # Broadcast approval confirmation to all clients
                await manager.broadcast({
                    "type": "plan_applied",
                    "plan_id": plan_id,
                    "operator_note": operator_note,
                    "message": f"Operator applied Plan {plan_id}: {operator_note}"
                })

            # ── Operator rejects all plans ────────────────────────────────────
            elif data.get("type") == "reject_plans":
                print(f"[HITL] Operator rejected all plans. Reason: {data.get('reason')}")
                pending_human_approval = None
                await manager.broadcast({
                    "type": "plans_rejected",
                    "reason": data.get("reason", "Operator override")
                })

            # ── Operator manually overrides grid state ────────────────────────
            elif data.get("type") == "manual_override":
                print(f"[HITL] Manual override by operator: {data.get('action')}")
                await manager.broadcast({
                    "type": "override_applied",
                    "action": data.get("action"),
                    "message": "Manual override applied by operator"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)

## LangSmith — What It Does For You

