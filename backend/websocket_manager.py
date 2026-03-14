"""WebSocket Manager for Real-Time Grid State Broadcasting."""

from typing import Set, Dict, Any, List, Optional
import json
from datetime import datetime
from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.broadcast_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"WebSocket client connected. Active: {len(self.active_connections)}")
        await self._send_welcome(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f"WebSocket client disconnected. Active: {len(self.active_connections)}")
    
    async def _send_welcome(self, websocket: WebSocket):
        try:
            welcome_message = {
                "type": "welcome",
                "timestamp": datetime.now().isoformat(),
                "active_connections": len(self.active_connections),
                "recent_updates": self.broadcast_history[-5:] if self.broadcast_history else [],
            }
            await websocket.send_json(welcome_message)
        except Exception as e:
            print(f"Error sending welcome: {e}")
    
    async def broadcast_grid_state(self, grid_state: Dict[str, Any]):
        broadcast_data = {
            "type": "grid_state",
            "timestamp": datetime.now().isoformat(),
            **grid_state,
        }
        self._add_to_history(broadcast_data)
        await self._broadcast(broadcast_data)
    
    async def broadcast_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "medium",
        data: Optional[Dict[str, Any]] = None,
    ):
        alert = {
            "type": "alert",
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "data": data or {},
        }
        self._add_to_history(alert)
        await self._broadcast(alert)
    
    async def broadcast_optimization_update(
        self,
        strategies: List[Dict[str, Any]],
        selected_strategy_id: Optional[int] = None,
        reason: Optional[str] = None,
    ):
        update = {
            "type": "optimization_update",
            "timestamp": datetime.now().isoformat(),
            "strategies": strategies,
            "selected_strategy_id": selected_strategy_id,
            "recommendation_reason": reason,
        }
        self._add_to_history(update)
        await self._broadcast(update)
    
    async def broadcast_status(self, status: str, details: Optional[Dict[str, Any]] = None):
        status_msg = {
            "type": "status",
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details or {},
        }
        await self._broadcast(status_msg)
    
    async def _broadcast(self, message: Dict[str, Any]):
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Broadcast error: {e}")
                disconnected.add(connection)
        for connection in disconnected:
            self.disconnect(connection)
    
    def _add_to_history(self, message: Dict[str, Any]):
        self.broadcast_history.append(message)
        if len(self.broadcast_history) > self.max_history:
            self.broadcast_history.pop(0)
    
    def get_connection_count(self) -> int:
        return len(self.active_connections)
    
    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.broadcast_history[-limit:]
    
    async def send_to_client(self, websocket: WebSocket, message: Dict[str, Any]):
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"Send error: {e}")
            self.disconnect(websocket)


manager = ConnectionManager()
