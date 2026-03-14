"""AI agents with Groq LLM integration and timeout resilience."""

import os
import json
import logging
from typing import Any, Dict, Optional
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import SecretStr

from .schemas import AgentState, Recommendation
from .resilience import SafeAgent, _safe_run, DEFAULT_TIMEOUT, FALLBACK_CONFIDENCE

logger = logging.getLogger(__name__)

# Initialize Groq LLM
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


class IntakeAgent:
    @staticmethod
    def validate(state: AgentState) -> AgentState:
        input_data = state.input_data
        
        if input_data.demand < 0:
            logger.warning("Invalid demand value (negative)")
        if input_data.supply < 0:
            logger.warning("Invalid supply value (negative)")
        if input_data.temperature < -100 or input_data.temperature > 60:
            logger.warning(f"Unusual temperature: {input_data.temperature}°C")
        state.analysis["intake"] = {
            "demand": input_data.demand,
            "supply": input_data.supply,
            "temperature": input_data.temperature,
            "zones_count": len(input_data.zones),
            "protected_zones": [z.name for z in input_data.zones if z.protected],
        }
        
        logger.info(f"[INTAKE] Validated input | D: {input_data.demand}MW, S: {input_data.supply}MW, T: {input_data.temperature}°C")
        return state


class GridHealthAgent(SafeAgent):
    @staticmethod
    @_safe_run(timeout=DEFAULT_TIMEOUT, fallback=SafeAgent.get_fallback_response("health"))
    def analyze_with_llm(state: AgentState) -> AgentState:
        input_data = state.input_data
        demand = input_data.demand
        supply = input_data.supply
        
        if not GROQ_API_KEY:
            logger.warning("GROQ_API_KEY not set, using fallback analysis")
            return GridHealthAgent.analyze_fallback(state)
        
        try:
            llm = ChatGroq(
                model="mixtral-8x7b-32768",
                temperature=0,
                api_key=SecretStr(GROQ_API_KEY),
                timeout=DEFAULT_TIMEOUT,
            )
            
            prompt = f"""
Analyze grid health for overload risk:
- Current Demand: {demand} MW
- Available Supply: {supply} MW
- Load Percentage: {(demand/supply*100 if supply > 0 else 100):.1f}%

Provide JSON response with:
- overload (bool): True if demand > supply
- severity (str): low/medium/high
- confidence (float): 0.0-1.0
- recommendation (str): What action to take
"""
            
            response = llm.invoke([
                SystemMessage(content="You are an AI grid operator analyzing power system health."),
                HumanMessage(content=prompt),
            ])
            
            response_text = str(response.content) if hasattr(response, 'content') else str(response)
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_str = response_text[json_start:json_end]
            analysis_result = json.loads(json_str)
            state.overload = analysis_result.get("overload", demand > supply)
            state.health_confidence = analysis_result.get("confidence", FALLBACK_CONFIDENCE)
            state.analysis["grid_health"] = {
                "demand": demand,
                "supply": supply,
                "load_percentage": (demand / supply * 100) if supply > 0 else 100,
                "overload": state.overload,
                "severity": analysis_result.get("severity", "medium"),
                "llm_analysis": analysis_result.get("recommendation", "Monitor"),
            }
            
            if state.overload:
                state.recommendations.append(
                    Recommendation(
                        action=analysis_result.get("recommendation", f"Reduce load by {demand - supply} MW"),
                        priority="high",
                        affected_zones=["industrial_zones"]
                    )
                )
            
            logger.info(f"[HEALTH] LLM Analysis | Overload: {state.overload}, Confidence: {state.health_confidence:.2f}")
            return state
        
        except Exception as e:
            logger.error(f"[HEALTH] LLM call failed: {str(e)}, using fallback")
            return GridHealthAgent.analyze_fallback(state)
    
    @staticmethod
    def analyze_fallback(state: AgentState) -> AgentState:
        input_data = state.input_data
        demand = input_data.demand
        supply = input_data.supply
        
        state.overload = demand > supply
        state.health_confidence = FALLBACK_CONFIDENCE
        
        state.analysis["grid_health"] = {
            "demand": demand,
            "supply": supply,
            "load_percentage": (demand / supply * 100) if supply > 0 else 100,
            "overload": state.overload,
            "severity": "high" if state.overload else "low",
            "fallback": True,
        }
        
        if state.overload:
            overload_margin = demand - supply
            state.recommendations.append(
                Recommendation(
                    action=f"Reduce load by {overload_margin} MW",
                    priority="high",
                    affected_zones=["industrial_zones"]
                )
            )
        
        logger.info(f"[HEALTH] Fallback Analysis | Overload: {state.overload}")
        return state


class DemandAgent(SafeAgent):
    @staticmethod
    @_safe_run(timeout=DEFAULT_TIMEOUT, fallback=SafeAgent.get_fallback_response("demand"))
    def analyze_with_llm(state: AgentState) -> AgentState:
        temperature = state.input_data.temperature
        demand = state.input_data.demand
        
        if not GROQ_API_KEY:
            logger.warning("GROQ_API_KEY not set, using fallback analysis")
            return DemandAgent.analyze_fallback(state)
        
        try:
            llm = ChatGroq(
                model="mixtral-8x7b-32768",
                temperature=0,
                api_key=SecretStr(GROQ_API_KEY),
                timeout=DEFAULT_TIMEOUT,
            )
            
            prompt = f"""
Predict demand spike for grid:
- Current Temperature: {temperature}°C
- Current Demand: {demand} MW

Analyze demand spike risk and provide JSON:
- demand_spike (bool): Will demand spike occur?
- spike_severity (float): 0.0-2.0 multiplier
- spike_reason (str): Why (if any)
- confidence (float): 0.0-1.0
- prediction (str): Predicted demand change
"""
            
            response = llm.invoke([
                SystemMessage(content="You are a grid demand forecasting AI."),
                HumanMessage(content=prompt),
            ])
            
            response_text = str(response.content) if hasattr(response, 'content') else str(response)
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_str = response_text[json_start:json_end]
            analysis_result = json.loads(json_str)
            
            state.demand_spike = analysis_result.get("demand_spike", temperature > 35 or temperature < 5)
            state.demand_confidence = analysis_result.get("confidence", FALLBACK_CONFIDENCE)
            
            state.analysis["demand"] = {
                "current_temperature": temperature,
                "demand_spike": state.demand_spike,
                "spike_severity": analysis_result.get("spike_severity", 0.5),
                "spike_reason": analysis_result.get("spike_reason", "normal"),
                "llm_prediction": analysis_result.get("prediction", "Stable"),
            }
            
            if state.demand_spike:
                predicted_increase = int(demand * analysis_result.get("spike_severity", 0.5) * 0.1)
                state.recommendations.append(
                    Recommendation(
                        action=analysis_result.get("prediction", f"Prepare for {predicted_increase} MW increase"),
                        priority="medium",
                        affected_zones=["residential_zones"]
                    )
                )
            
            logger.info(f"[DEMAND] LLM Analysis | Spike: {state.demand_spike}, Confidence: {state.demand_confidence:.2f}")
            return state
        
        except Exception as e:
            logger.error(f"[DEMAND] LLM call failed: {str(e)}, using fallback")
            return DemandAgent.analyze_fallback(state)
    
    @staticmethod
    def analyze_fallback(state: AgentState) -> AgentState:
        temperature = state.input_data.temperature
        demand = state.input_data.demand
        
        state.demand_spike = temperature > 35 or temperature < 5
        state.demand_confidence = FALLBACK_CONFIDENCE
        
        if temperature > 35:
            spike_severity = min((temperature - 35) / 5, 2)
            spike_reason = "high_temperature"
        elif temperature < 5:
            spike_severity = min((5 - temperature) / 5, 1.5)
            spike_reason = "low_temperature"
        else:
            spike_severity = 0
            spike_reason = "normal"
        
        state.analysis["demand"] = {
            "current_temperature": temperature,
            "demand_spike": state.demand_spike,
            "spike_severity": spike_severity,
            "spike_reason": spike_reason,
            "fallback": True,
        }
        
        if state.demand_spike:
            predicted_increase = int(demand * spike_severity * 0.1)
            state.recommendations.append(
                Recommendation(
                    action=f"Prepare for demand increase due to {spike_reason.replace('_', ' ')}",
                    priority="medium",
                    affected_zones=["residential_zones"]
                )
            )
        
        logger.info(f"[DEMAND] Fallback Analysis | Spike: {state.demand_spike}")
        return state


class DisasterAgent(SafeAgent):
    @staticmethod
    @_safe_run(timeout=DEFAULT_TIMEOUT, fallback=SafeAgent.get_fallback_response("disaster"))
    def analyze_with_llm(state: AgentState) -> AgentState:
        """Uses LLM for sophisticated weather risk assessment."""
        temperature = state.input_data.temperature
        
        if not GROQ_API_KEY:
            logger.warning("GROQ_API_KEY not set, using fallback analysis")
            return DisasterAgent.analyze_fallback(state)
        
        try:
            llm = ChatGroq(
                model="mixtral-8x7b-32768",
                temperature=0,
                api_key=SecretStr(GROQ_API_KEY),
                timeout=DEFAULT_TIMEOUT,
            )
            
            prompt = f"""
Assess disaster risk for grid emergency:
- Current Temperature: {temperature}°C

Evaluate and provide JSON:
- disaster_risk (bool): Is there extreme weather risk?
- disaster_type (str): heatwave/extreme_cold/normal
- severity (str): low/medium/high/critical
- confidence (float): 0.0-1.0
- emergency_action (str): What emergency action needed?
"""
            
            response = llm.invoke([
                SystemMessage(content="You are a grid emergency response AI."),
                HumanMessage(content=prompt),
            ])
            
            response_text = str(response.content) if hasattr(response, 'content') else str(response)
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_str = response_text[json_start:json_end]
            analysis_result = json.loads(json_str)
            
            state.disaster_risk = analysis_result.get("disaster_risk", temperature > 40 or temperature < -10)
            state.disaster_confidence = analysis_result.get("confidence", FALLBACK_CONFIDENCE)
            
            state.analysis["disaster"] = {
                "temperature": temperature,
                "disaster_risk": state.disaster_risk,
                "disaster_type": analysis_result.get("disaster_type", "normal"),
                "severity": analysis_result.get("severity", "low"),
                "llm_action": analysis_result.get("emergency_action", "Monitor"),
            }
            
            if state.disaster_risk:
                state.recommendations.append(
                    Recommendation(
                        action=analysis_result.get("emergency_action", "Activate emergency protocols"),
                        priority="high",
                        affected_zones=["all"]
                    )
                )
            
            logger.info(f"[DISASTER] LLM Analysis | Risk: {state.disaster_risk}, Confidence: {state.disaster_confidence:.2f}")
            return state
        
        except Exception as e:
            logger.error(f"[DISASTER] LLM call failed: {str(e)}, using fallback")
            return DisasterAgent.analyze_fallback(state)
    
    @staticmethod
    def analyze_fallback(state: AgentState) -> AgentState:
        temperature = state.input_data.temperature
        
        state.disaster_risk = temperature > 40 or temperature < -10
        state.disaster_confidence = FALLBACK_CONFIDENCE
        
        if temperature > 40:
            disaster_type = "heatwave"
            severity = "high"
        elif temperature < -10:
            disaster_type = "extreme_cold"
            severity = "high"
        else:
            disaster_type = "normal"
            severity = "low"
        
        state.analysis["disaster"] = {
            "temperature": temperature,
            "disaster_risk": state.disaster_risk,
            "disaster_type": disaster_type,
            "severity": severity,
            "fallback": True,
        }
        
        if state.disaster_risk:
            state.recommendations.append(
                Recommendation(
                    action=f"Activate emergency protocols for {disaster_type}",
                    priority="high",
                    affected_zones=["all"]
                )
            )
        
        logger.info(f"[DISASTER] Fallback Analysis | Risk: {state.disaster_risk}")
        return state


class PriorityAgent(SafeAgent):
    @staticmethod
    def consolidate(state: AgentState) -> AgentState:
        zones = state.input_data.zones
        overload = state.overload
        demand_spike = state.demand_spike
        disaster_risk = state.disaster_risk
        protected_zones = [zone.name for zone in zones if zone.protected]
        critical_risk = overload or demand_spike or disaster_risk
        
        if critical_risk:
            state.protected_zones_at_risk = protected_zones
            
            if protected_zones:
                state.recommendations.append(
                    Recommendation(
                        action=f"PRIORITY: Protect critical zones - {', '.join(protected_zones)}. "
                                "Use load rotation on non-critical zones if needed.",
                        priority="critical",
                        affected_zones=protected_zones
                    )
                )

        state.analysis["priority"] = {
            "protected_zones": protected_zones,
            "critical_risk": critical_risk,
            "zones_at_risk": state.protected_zones_at_risk,
            "consolidated_from": ["grid_health", "demand", "disaster"],
        }
        
        logger.info(f"[PRIORITY] Consolidated | Protected: {protected_zones}, Risk: {critical_risk}")
        return state


class RiskAssessmentAgent(SafeAgent):
    """Final risk assessment with average confidence calculation."""
    
    @staticmethod
    def assess(state: AgentState) -> AgentState:
        """
        Consolidate all analysis to determine overall risk level.
        Calculate average confidence across all agents.
        Risk levels: low, medium, high, critical.
        """
        overload = state.overload
        demand_spike = state.demand_spike
        disaster_risk = state.disaster_risk
        protected_at_risk = len(state.protected_zones_at_risk) > 0
        
        # Calculate average confidence
        confidences = [
            state.health_confidence,
            state.demand_confidence,
            state.disaster_confidence,
        ]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        # Determine risk level based on factors
        if protected_at_risk and (overload or disaster_risk):
            risk_level = "critical"
        elif disaster_risk or (overload and demand_spike):
            risk_level = "high"
        elif overload or demand_spike or disaster_risk:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        state.risk_level = risk_level
        
        # Store final assessment
        state.analysis["risk_assessment"] = {
            "overall_risk_level": risk_level,
            "average_confidence": avg_confidence,
            "factors": {
                "overload": overload,
                "demand_spike": demand_spike,
                "disaster_risk": disaster_risk,
                "protected_zones_at_risk": protected_at_risk,
            },
            "agent_confidences": {
                "health": state.health_confidence,
                "demand": state.demand_confidence,
                "disaster": state.disaster_confidence,
            }
        }
        
        logger.info(f"[ASSESSMENT] Final Risk: {risk_level}, Confidence: {avg_confidence:.2f}")
        return state
