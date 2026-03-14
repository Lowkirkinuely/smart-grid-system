"""WebSocket Manager for Real-Time Grid State Broadcasting."""

import json
import logging
from typing import Set, Dict, Any, List, Optional
from datetime import datetime
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections and broadcasts.
    Uses set() for O(1) connection lookup and removal.
    Maintains broadcast history for reconnecting clients.
    """

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.broadcast_history:  List[Dict[str, Any]] = []
        self.max_history = 100

    # ── Connection lifecycle ───────────────────────────────────────────────────

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"[WS] Client connected. Active: {len(self.active_connections)}")
        await self._send_welcome(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"[WS] Client disconnected. Active: {len(self.active_connections)}")

    async def _send_welcome(self, websocket: WebSocket):
        """Send welcome message with recent history to newly connected client."""
        try:
            await websocket.send_json({
                "type":               "welcome",
                "timestamp":          datetime.now().isoformat(),
                "active_connections": len(self.active_connections),
                "recent_updates":     self.broadcast_history[-5:] if self.broadcast_history else []
            })
        except Exception as e:
            logger.warning(f"[WS] Welcome send failed: {e}")

    # ── Core broadcast ─────────────────────────────────────────────────────────

    async def broadcast(self, message: dict):
        """Broadcast to all active connections. Auto-removes dead connections."""
        dead = set()
        for ws in self.active_connections:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws)
        if dead:
            logger.warning(f"[WS] Removed {len(dead)} dead connection(s)")

    async def send_to_client(self, websocket: WebSocket, message: dict):
        """Send message to a single client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"[WS] send_to_client failed: {e}")
            self.disconnect(websocket)

    # ── Typed broadcast methods ────────────────────────────────────────────────

    async def broadcast_alert(
        self,
        alert_type: str,
        message:    str,
        severity:   str = "medium",
        data:       Optional[Dict[str, Any]] = None
    ):
        """Broadcast a structured alert — used for HITL pause notifications."""
        alert = {
            "type":       "alert",
            "alert_type": alert_type,
            "severity":   severity,
            "message":    message,
            "timestamp":  datetime.now().isoformat(),
            "data":       data or {}
        }
        self._add_to_history(alert)
        await self.broadcast(alert)

    async def broadcast_status(
        self,
        status:  str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Broadcast a status update — used for pipeline stage notifications."""
        msg = {
            "type":      "status",
            "status":    status,
            "timestamp": datetime.now().isoformat(),
            "details":   details or {}
        }
        await self.broadcast(msg)

    async def broadcast_optimization_update(
        self,
        strategies:           List[Dict[str, Any]],
        selected_strategy_id: Optional[int] = None,
        reason:               Optional[str]  = None
    ):
        """Broadcast new optimization plans."""
        msg = {
            "type":                   "optimization_update",
            "timestamp":              datetime.now().isoformat(),
            "strategies":             strategies,
            "selected_strategy_id":   selected_strategy_id,
            "recommendation_reason":  reason
        }
        self._add_to_history(msg)
        await self.broadcast(msg)

    # ── Heartbeat ──────────────────────────────────────────────────────────────

    async def heartbeat(self, websocket: WebSocket) -> bool:
        """Ping a connection. Returns False and disconnects if stale."""
        try:
            await websocket.send_text(json.dumps({"type": "ping"}))
            return True
        except Exception:
            self.disconnect(websocket)
            return False

    # ── History & stats ────────────────────────────────────────────────────────

    def _add_to_history(self, message: dict):
        self.broadcast_history.append(message)
        if len(self.broadcast_history) > self.max_history:
            self.broadcast_history.pop(0)

    def get_connection_count(self) -> int:
        return len(self.active_connections)

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.broadcast_history[-limit:]


manager = ConnectionManager()