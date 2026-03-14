"""
Resilience utilities for AI agents.
Includes timeout handling, fallbacks, and error recovery.
"""

import asyncio
import logging
from typing import Dict, Any, Callable, TypeVar, Optional
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Default timeout in seconds for LLM calls
DEFAULT_TIMEOUT = 15
FALLBACK_CONFIDENCE = 0.3


def _safe_run(timeout: int = DEFAULT_TIMEOUT, fallback: Optional[Dict[str, Any]] = None) -> Callable:
    """
    Decorator to wrap LLM calls with timeout and error handling.
    
    Provides:
    1. Hard timeout (15 seconds by default)
    2. Graceful degradation with fallback response
    3. Logging for debugging
    
    Args:
        timeout: Timeout in seconds
        fallback: Dictionary to return if call fails (default: Medium risk, 0.3 confidence)
    
    Returns:
        Decorated function that handles timeouts/errors
    """
    if fallback is None:
        fallback = {
            "risk_level": "medium",
            "confidence": FALLBACK_CONFIDENCE,
            "recommendations": [{"action": "Unable to complete analysis", "priority": "medium"}],
            "analysis": {"error": "Analysis timeout or failed", "fallback": True},
        }
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Dict[str, Any]:
            try:
                # Call async function with timeout
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=timeout
                    )
                else:
                    # For sync functions wrapped as async, run in executor
                    result = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, func, *args),
                        timeout=timeout
                    )
                return result
            except asyncio.TimeoutError:
                logger.warning(f"Function {func.__name__} timed out after {timeout}s, using fallback")
                return fallback
            except Exception as e:
                logger.error(f"Function {func.__name__} failed: {str(e)}, using fallback")
                return fallback
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Dict[str, Any]:
            try:
                result = func(*args, **kwargs)
                return result if result is not None else fallback
            except Exception as e:
                logger.error(f"Function {func.__name__} failed: {str(e)}, using fallback")
                return fallback
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class SafeAgent:
    """
    Base class for agents with built-in resilience.
    Provides timeout handling, fallback responses, and confidence tracking.
    """
    
    @staticmethod
    def get_fallback_response(agent_type: str) -> Dict[str, Any]:
        """
        Get a fallback response for a specific agent type.
        Used when LLM call fails or times out.
        """
        fallbacks = {
            "health": {
                "risk_level": "medium",
                "confidence": FALLBACK_CONFIDENCE,
                "analysis": {"error": "Health check failed", "fallback": True},
                "recommendations": [{"action": "Restore monitoring", "priority": "high"}],
            },
            "demand": {
                "risk_level": "low",
                "confidence": FALLBACK_CONFIDENCE,
                "analysis": {"error": "Demand prediction failed", "fallback": True},
                "recommendations": [{"action": "Monitor demand trends", "priority": "medium"}],
            },
            "disaster": {
                "risk_level": "medium",
                "confidence": FALLBACK_CONFIDENCE,
                "analysis": {"error": "Disaster check failed", "fallback": True},
                "recommendations": [{"action": "Perform manual disaster assessment", "priority": "high"}],
            },
        }
        return fallbacks.get(agent_type, fallbacks["health"])
    
    @staticmethod
    def calculate_avg_confidence(results: list) -> float:
        """
        Calculate average confidence score across multiple analysis results.
        """
        if not results:
            return 0.0
        
        confidences = [r.get("confidence", 0.5) for r in results]
        return sum(confidences) / len(confidences)
    
    @staticmethod
    def validate_result(result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate agent result has required fields.
        Add defaults if missing.
        """
        required_fields = {
            "risk_level": "medium",
            "confidence": FALLBACK_CONFIDENCE,
            "analysis": {},
            "recommendations": [],
        }
        
        for field, default in required_fields.items():
            if field not in result:
                result[field] = default
        
        return result
