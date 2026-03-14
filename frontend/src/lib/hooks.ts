/**
 * React Hook for managing grid state and WebSocket connection
 */

import { useState, useEffect, useCallback, useRef } from "react";
import WebSocketService, { WebSocketMessage } from "./websocket";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const WS_URL = (BACKEND_URL.replace("http", "ws")) + "/ws";

export interface GridUIState {
  demand: number;
  supply: number;
  temperature: number;
  riskLevel: string;
  mlRiskLevel: string;
  llmRiskLevel: string;
  plans: any[];
  aiAnalysis: any;
  requiresHumanApproval: boolean;
  threadId: string;
  isLoading: boolean;
  error: string | null;
  isConnected: boolean;
  agentLogs: Array<{ time: string; agent: string; message: string }>;
  executedDemand?: number;  // Track demand after plan execution
}

const initialState: GridUIState = {
  demand: 0,
  supply: 0,
  temperature: 0,
  riskLevel: "UNKNOWN",
  mlRiskLevel: "?",
  llmRiskLevel: "?",
  plans: [],
  aiAnalysis: {},
  requiresHumanApproval: false,
  threadId: "",
  isLoading: false,
  error: null,
  isConnected: false,
  agentLogs: [],
  executedDemand: undefined,
};

export function useGridState() {
  const [state, setState] = useState<GridUIState>(initialState);
  const wsRef = useRef<WebSocketService | null>(null);

  // Initialize WebSocket on mount
  useEffect(() => {
    const ws = new WebSocketService(WS_URL);

    // Subscribe to different message types
    ws.on("welcome", (message: WebSocketMessage) => {
      console.log("[Grid Hook] Welcome received:", message);
      setState((prev) => ({
        ...prev,
        isConnected: true,
      }));
    });

    ws.on("plans", (message: WebSocketMessage) => {
      console.log("[Grid Hook] Plans received message:", message);
      console.log("[Grid Hook] Number of plans:", message.plans?.length || 0);
      
      setState((prev) => {
        const incomingDemand = message.grid_state?.demand || 0;
        
        // Always use the incoming demand from backend - it's the current grid state
        const newState = {
          ...prev,
          demand: incomingDemand,
          supply: message.grid_state?.supply || prev.supply,
          temperature: message.grid_state?.temperature || prev.temperature,
          plans: message.plans || [],
          riskLevel: message.ai_analysis?.risk_level || "UNKNOWN",
          mlRiskLevel: message.ai_analysis?.ml_risk_level || "?",
          llmRiskLevel: message.ai_analysis?.llm_risk_level || "?",
          aiAnalysis: message.ai_analysis || {},
          requiresHumanApproval: message.requires_human_approval || false,
          threadId: message.thread_id || "no-thread",
          isLoading: false,
          // Don't preserve executed demand when new plans arrive - reset it
          executedDemand: undefined,
        };
        console.log("[Grid Hook] State updated with new plans:", newState.plans.length, "plans | Demand:", newState.demand, "MW");
        return newState;
      });
    });

    ws.on("analyzing", (message: WebSocketMessage) => {
      console.log("[Grid Hook] Analyzing:", message);
      setState((prev) => ({
        ...prev,
        isLoading: true,
      }));
    });

    ws.on("grid_update", (message: WebSocketMessage) => {
      console.log("[Grid Hook] Grid state updated after plan execution:", message);
      const gridState = message.grid_state;
      if (gridState) {
        setState((prev) => ({
          ...prev,
          demand: gridState.demand || prev.demand,
          supply: gridState.supply || prev.supply,
          temperature: gridState.temperature || prev.temperature,
          executedDemand: gridState.demand,  // Save the executed demand to preserve it
        }));
        console.log("[Grid Hook] Topbar metrics locked after execution:", {
          demand: gridState.demand,
          supply: gridState.supply,
          temperature: gridState.temperature,
          executedDemand: gridState.demand
        });
      }
    });

    ws.on("agent_activity", (message: WebSocketMessage) => {
      console.log("[Grid Hook] Agent activity:", message);
      const now = new Date();
      const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
      
      setState((prev) => {
        const newLog = {
          time: timeStr,
          agent: message.agent_name || "AGENT",
          message: message.activity || ""
        };
        // Keep last 20 logs
        const updatedLogs = [newLog, ...prev.agentLogs].slice(0, 20);
        return {
          ...prev,
          agentLogs: updatedLogs
        };
      });
    });

    // Connect to WebSocket
    ws.connect()
      .then(() => {
        console.log("[Grid Hook] WebSocket connected");
      })
      .catch((error) => {
        console.error("[Grid Hook] Failed to connect:", error);
        setState((prev) => ({
          ...prev,
          error: "Failed to connect to backend",
          isConnected: false,
        }));
      });

    wsRef.current = ws;

    // Cleanup on unmount
    return () => {
      ws.close();
    };
  }, []);

  // Send message through WebSocket
  const sendMessage = useCallback((message: any) => {
    if (wsRef.current) {
      wsRef.current.send(message);
    } else {
      console.warn("[Grid Hook] WebSocket not initialized");
    }
  }, []);

  // Apply a plan
  const applyPlan = useCallback(
    (planId: string, note: string = "") => {
      sendMessage({
        type: "apply_plan",
        plan_id: planId,
        thread_id: state.threadId,
        note,
      });
    },
    [state.threadId, sendMessage]
  );

  return {
    gridState: state,
    sendMessage,
    applyPlan,
  };
}
