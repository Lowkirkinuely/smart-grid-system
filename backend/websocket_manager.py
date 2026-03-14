"""
WebSocket Manager for Real-Time Grid State Broadcasting.
Handles client connections and broadcasts grid analysis and optimization plans.
"""

from typing import Set, Dict, Any, List, Optional
import json
from datetime import datetime
from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""
    
    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Set[WebSocket] = set()
        self.broadcast_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    async def connect(self, websocket: WebSocket):
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
        """
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"✓ WebSocket client connected. Active connections: {len(self.active_connections)}")
        
        # Send welcome message with recent history
        await self._send_welcome(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """
        Remove a disconnected client.
        
        Args:
            websocket: The WebSocket connection to remove
        """
        self.active_connections.discard(websocket)
        print(f"✓ WebSocket client disconnected. Active connections: {len(self.active_connections)}")
    
    async def _send_welcome(self, websocket: WebSocket):
        """Send welcome message and recent history to new client."""
        try:
            welcome_message = {
                "type": "welcome",
                "timestamp": datetime.now().isoformat(),
                "active_connections": len(self.active_connections),
                "recent_updates": self.broadcast_history[-5:] if self.broadcast_history else [],
            }
            await websocket.send_json(welcome_message)
        except Exception as e:
            print(f"Error sending welcome message: {e}")
    
    async def broadcast_grid_state(self, grid_state: Dict[str, Any]):
        """
        Broadcast complete grid state to all connected clients.
        
        Message format:
        {
            "type": "grid_state",
            "timestamp": ISO timestamp,
            "demand": float,
            "supply": float,
            "temperature": float,
            "zones": [{"name": str, "protected": bool}],
            "risk_level": str,
            "analysis": dict,
            "optimization_plans": [strategy1, strategy2, strategy3]
        }
        
        Args:
            grid_state: Dictionary containing complete grid analysis
        """
        broadcast_data = {
            "type": "grid_state",
            "timestamp": datetime.now().isoformat(),
            **grid_state,
        }
        
        # Store in history
        self._add_to_history(broadcast_data)
        
        # Broadcast to all connected clients
        await self._broadcast(broadcast_data)
    
    async def broadcast_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "medium",
        data: Optional[Dict[str, Any]] = None,
    ):
        """
        Broadcast an alert to all connected clients.
        
        Args:
            alert_type: Type of alert (e.g., "overload", "critical_zone_at_risk")
            message: Human-readable alert message
            severity: "low", "medium", "high", "critical"
            data: Additional data for the alert
        """
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
        """
        Broadcast optimization strategies and selection.
        
        Args:
            strategies: List of 3 optimization strategies
            selected_strategy_id: Optional ID of recommended strategy
            reason: Optional reason for recommendation
        """
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
        """
        Broadcast system status update.
        
        Args:
            status: "healthy", "analyzing", "optimizing", "error"
            details: Optional additional details
        """
        status_msg = {
            "type": "status",
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details or {},
        }
        
        await self._broadcast(status_msg)
    
    async def _broadcast(self, message: Dict[str, Any]):
        """
        Send message to all connected clients.
        Handles disconnection gracefully.
        
        Args:
            message: Message dictionary to broadcast
        """
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to client: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)
    
    def _add_to_history(self, message: Dict[str, Any]):
        """
        Add message to broadcast history.
        Maintains max_history limit.
        
        Args:
            message: Message to add to history
        """
        self.broadcast_history.append(message)
        if len(self.broadcast_history) > self.max_history:
            self.broadcast_history.pop(0)
    
    def get_connection_count(self) -> int:
        """Get number of active connections."""
        return len(self.active_connections)
    
    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent broadcast messages."""
        return self.broadcast_history[-limit:]
    
    async def send_to_client(
        self, websocket: WebSocket, message: Dict[str, Any]
    ):
        """
        Send message to specific client.
        
        Args:
            websocket: Target WebSocket connection
            message: Message to send
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"Error sending to client: {e}")
            self.disconnect(websocket)


# Global connection manager instance
manager = ConnectionManager()
