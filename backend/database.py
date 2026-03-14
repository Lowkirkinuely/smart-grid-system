"""
MongoDB async client for Smart Grid system.
Stores grid state history, AI analysis logs, and human decisions.
Uses Motor (async MongoDB driver) so it never blocks the FastAPI event loop.
"""

import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB  = os.getenv("MONGODB_DB", "smart_grid")


class Database:
    """
    Async MongoDB client wrapper.
    Collections:
        grid_states     — every grid reading received from simulator
        analyses        — every AI pipeline result
        human_decisions — every operator approval/rejection
        ml_history      — ML model training sample count over time
    """

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db     = None

    async def connect(self):
        """Connect to MongoDB. Called on FastAPI startup."""
        try:
            self.client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
            self.db     = self.client[MONGODB_DB]

            # Verify connection
            await self.client.admin.command("ping")
            logger.info(f"[DB] Connected to MongoDB | DB: {MONGODB_DB}")

            # Create indexes for common queries
            await self.db.grid_states.create_index("timestamp")
            await self.db.analyses.create_index("thread_id", unique=True)
            await self.db.analyses.create_index("timestamp")
            await self.db.human_decisions.create_index("thread_id")
            await self.db.human_decisions.create_index("timestamp")

            logger.info("[DB] Indexes created")

        except Exception as e:
            logger.error(f"[DB] Connection failed: {e}")
            logger.warning("[DB] Running without MongoDB — data will not persist")
            self.client = None
            self.db     = None

    async def disconnect(self):
        """Disconnect. Called on FastAPI shutdown."""
        if self.client:
            self.client.close()
            logger.info("[DB] Disconnected from MongoDB")

    @property
    def is_connected(self) -> bool:
        return self.db is not None

    # ── Grid state history ─────────────────────────────────────────────────────

    async def save_grid_state(self, grid_state: dict, thread_id: str) -> Optional[str]:
        """Save every grid reading from the simulator."""
        if not self.is_connected:
            return None
        try:
            doc = {
                "thread_id": thread_id,
                "timestamp": datetime.utcnow(),
                **grid_state
            }
            result = await self.db.grid_states.insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            logger.warning(f"[DB] save_grid_state failed: {e}")
            return None

    async def get_grid_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch last N grid readings."""
        if not self.is_connected:
            return []
        try:
            cursor = self.db.grid_states.find(
                {}, {"_id": 0}
            ).sort("timestamp", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.warning(f"[DB] get_grid_history failed: {e}")
            return []

    # ── AI analysis logs ───────────────────────────────────────────────────────

    async def save_analysis(self, thread_id: str, ai_analysis: dict, plans: list) -> Optional[str]:
        """Save every AI pipeline result with its thread_id."""
        if not self.is_connected:
            return None
        try:
            doc = {
                "thread_id":  thread_id,
                "timestamp":  datetime.utcnow(),
                "ai_analysis": ai_analysis,
                "plans":      plans,
                "risk_level": ai_analysis.get("risk_level"),
                "ml_risk":    ai_analysis.get("ml_risk_level"),
                "llm_risk":   ai_analysis.get("llm_risk_level"),
                "confidence": ai_analysis.get("avg_confidence"),
                "required_hitl": ai_analysis.get("requires_human_approval", False)
            }
            result = await self.db.analyses.insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            logger.warning(f"[DB] save_analysis failed: {e}")
            return None

    async def get_analysis_by_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Fetch analysis for a specific thread."""
        if not self.is_connected:
            return None
        try:
            doc = await self.db.analyses.find_one({"thread_id": thread_id}, {"_id": 0})
            return doc
        except Exception as e:
            logger.warning(f"[DB] get_analysis_by_thread failed: {e}")
            return None

    async def get_recent_analyses(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch last N analyses."""
        if not self.is_connected:
            return []
        try:
            cursor = self.db.analyses.find(
                {}, {"_id": 0, "ai_analysis": 0, "plans": 0}  # exclude heavy fields
            ).sort("timestamp", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.warning(f"[DB] get_recent_analyses failed: {e}")
            return []

    # ── Human decisions ────────────────────────────────────────────────────────

    async def save_human_decision(
        self,
        thread_id:      str,
        decision_type:  str,   # "approve" or "reject"
        plan_id:        Optional[int],
        note:           str,
        risk_level:     str,
        confirmed_risk: Optional[str] = None
    ) -> Optional[str]:
        """
        Save every operator decision — the audit trail.
        This is the ground truth for ML training and accountability.
        """
        if not self.is_connected:
            return None
        try:
            doc = {
                "thread_id":      thread_id,
                "timestamp":      datetime.utcnow(),
                "decision_type":  decision_type,
                "plan_id":        plan_id,
                "note":           note,
                "risk_level":     risk_level,
                "confirmed_risk": confirmed_risk or risk_level,
            }
            result = await self.db.human_decisions.insert_one(doc)
            logger.info(f"[DB] Human decision saved | thread: {thread_id} | type: {decision_type}")
            return str(result.inserted_id)
        except Exception as e:
            logger.warning(f"[DB] save_human_decision failed: {e}")
            return None

    async def get_decision_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch last N human decisions — full audit log."""
        if not self.is_connected:
            return []
        try:
            cursor = self.db.human_decisions.find(
                {}, {"_id": 0}
            ).sort("timestamp", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.warning(f"[DB] get_decision_history failed: {e}")
            return []

    async def get_decision_stats(self) -> Dict[str, Any]:
        """Aggregate stats on human decisions — for dashboard."""
        if not self.is_connected:
            return {}
        try:
            total      = await self.db.human_decisions.count_documents({})
            approvals  = await self.db.human_decisions.count_documents({"decision_type": "approve"})
            rejections = await self.db.human_decisions.count_documents({"decision_type": "reject"})

            # Risk level distribution
            pipeline = [
                {"$group": {"_id": "$risk_level", "count": {"$sum": 1}}}
            ]
            risk_cursor = self.db.human_decisions.aggregate(pipeline)
            risk_dist   = {doc["_id"]: doc["count"] async for doc in risk_cursor}

            return {
                "total_decisions": total,
                "approvals":       approvals,
                "rejections":      rejections,
                "approval_rate":   round(approvals / total, 2) if total > 0 else 0,
                "risk_distribution": risk_dist
            }
        except Exception as e:
            logger.warning(f"[DB] get_decision_stats failed: {e}")
            return {}

    # ── ML training history ────────────────────────────────────────────────────

    async def save_ml_update(self, sample_count: int, confirmed_risk: str) -> None:
        """Track ML model training progress over time."""
        if not self.is_connected:
            return
        try:
            await self.db.ml_history.insert_one({
                "timestamp":      datetime.utcnow(),
                "sample_count":   sample_count,
                "confirmed_risk": confirmed_risk
            })
        except Exception as e:
            logger.warning(f"[DB] save_ml_update failed: {e}")


# Module-level singleton
db = Database()