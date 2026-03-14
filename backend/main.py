from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import asyncio

from websocket_manager import manager
from optimizer import optimize_power

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class Zone(BaseModel):
    name: str
    demand: float
    protected: bool = False

class GridState(BaseModel):
    demand: float
    supply: float
    temperature: float
    zones: List[Zone]

# --- Latest grid state store ---
latest_grid_state = {}

# --- POST endpoint: receives data from SUM (simulator) ---
@app.post("/grid-state")
async def receive_grid_state(state: GridState):
    global latest_grid_state
    latest_grid_state = state.dict()

    # Run optimizer
    plans = optimize_power(latest_grid_state)

    # Broadcast to all connected frontend clients
    await manager.broadcast({
        "type": "plans",
        "grid_state": latest_grid_state,
        "plans": plans
    })

    return {"status": "ok", "plans_generated": len(plans)}

# --- WebSocket: frontend connects here ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send current state immediately on connect
        if latest_grid_state:
            plans = optimize_power(latest_grid_state)
            await websocket.send_json({
                "type": "plans",
                "grid_state": latest_grid_state,
                "plans": plans
            })
        while True:
            # Keep connection alive, listen for operator commands
            data = await websocket.receive_json()
            if data.get("type") == "apply_plan":
                await manager.broadcast({
                    "type": "plan_applied",
                    "plan_id": data.get("plan_id"),
                    "message": f"Operator applied Plan {data.get('plan_id')}"
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- Health check ---
@app.get("/")
def health():
    return {"status": "Smart Grid Backend Running"}