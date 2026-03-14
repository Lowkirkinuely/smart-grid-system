import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  AiAnalysis,
  ConnectionState,
  GridAlert,
  GridPlan,
  GridStatePayload,
  StatusSnapshot,
} from "../types/grid";

const BACKEND_BASE = (import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000").replace(/\/+$/, "");

const buildWebSocketUrl = (backendUrl: string) => {
  if (!backendUrl) return "";
  if (backendUrl.startsWith("https")) {
    return backendUrl.replace(/^https/, "wss");
  }
  return backendUrl.replace(/^http/, "ws");
};

const formatAlert = (payload: any): GridAlert => ({
  alert_type: payload.alert_type ?? payload.type ?? "unknown",
  severity: payload.severity ?? "medium",
  message: payload.message ?? "Alert triggered",
  timestamp: payload.timestamp ?? new Date().toISOString(),
  data: payload.data,
});

export function useGridData() {
  const [gridState, setGridState] = useState<GridStatePayload | null>(null);
  const [plans, setPlans] = useState<GridPlan[]>([]);
  const [aiAnalysis, setAiAnalysis] = useState<AiAnalysis | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [recommendedPlanId, setRecommendedPlanId] = useState<number | null>(null);
  const [alerts, setAlerts] = useState<GridAlert[]>([]);
  const [statusStage, setStatusStage] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const backendUrl = BACKEND_BASE;
  const websocketUrl = buildWebSocketUrl(backendUrl);

  const snapshotKey = useMemo(() => `${backendUrl}/status`, [backendUrl]);

  useEffect(() => {
    let isActive = true;

    const fetchStatus = async () => {
      try {
        const response = await fetch(snapshotKey);
        if (!response.ok) {
          throw new Error("Backend status invalid");
        }
        const payload: StatusSnapshot = await response.json();
        if (!isActive) return;
        if (payload.grid_state) {
          setGridState(payload.grid_state);
        }
        if (payload.plans) {
          setPlans(payload.plans);
        }
        if (payload.ai_analysis) {
          setAiAnalysis(payload.ai_analysis);
        }
        setThreadId(payload.thread_id ?? null);
        if (payload.timestamp) {
          setLastUpdated(payload.timestamp);
        }
      } catch (err) {
        if (!isActive) return;
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    fetchStatus();

    if (typeof WebSocket === "undefined" || !websocketUrl) {
      setConnectionState("closed");
      return () => {
        isActive = false;
      };
    }

    const socket = new WebSocket(`${websocketUrl}/ws`);
    wsRef.current = socket;

    const handleMessage = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data);
        const timestamp = payload.timestamp ?? new Date().toISOString();
        if (payload.type === "plans") {
          setGridState(payload.grid_state ?? null);
          setPlans(payload.plans ?? []);
          setAiAnalysis(payload.ai_analysis ?? null);
          setThreadId(payload.thread_id ?? null);
          setRecommendedPlanId(payload.recommended_plan ?? null);
          setLastUpdated(timestamp);
        } else if (payload.type === "alert") {
          setAlerts((prev) => [formatAlert(payload), ...prev].slice(0, 6));
          setStatusStage(`Alert · ${payload.message ?? payload.alert_type}`);
        } else if (payload.type === "status") {
          setStatusStage(payload.status ?? payload.details?.stage ?? null);
          setLastUpdated(timestamp);
        } else if (payload.type === "plan_applied" || payload.type === "plans_rejected") {
          setStatusStage(payload.message ?? null);
          setLastUpdated(timestamp);
        }
      } catch (err) {
        console.error("Failed to parse message", err);
      }
    };

    socket.addEventListener("open", () => {
      if (!isActive) return;
      setConnectionState("open");
    });
    socket.addEventListener("close", () => {
      if (!isActive) return;
      setConnectionState("closed");
    });
    socket.addEventListener("error", () => {
      if (!isActive) return;
      setError("Real-time connection interrupted");
      setConnectionState("closed");
    });
    socket.addEventListener("message", handleMessage);

    return () => {
      isActive = false;
      socket.removeEventListener("message", handleMessage);
      socket.close();
    };
  }, [snapshotKey, websocketUrl]);

  const sendWebSocketMessage = useCallback(
    (payload: Record<string, unknown>) => {
      const socket = wsRef.current;
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        setError("Real-time connection not ready yet");
        return false;
      }
      socket.send(JSON.stringify({ ...payload, thread_id: threadId }));
      return true;
    },
    [threadId]
  );

  const applyPlan = useCallback(
    (planId: number, note = "Operator approved plan") => {
      if (!threadId) {
        setError("No active thread to apply the plan");
        return;
      }
      const success = sendWebSocketMessage({ type: "apply_plan", plan_id: planId, note });
      if (success) {
        setStatusStage(`Plan ${planId} submitted`);
      }
    },
    [sendWebSocketMessage, threadId]
  );

  const rejectPlans = useCallback(
    (reason = "Operator override") => {
      if (!threadId) {
        setError("No active thread to reject");
        return;
      }
      const success = sendWebSocketMessage({ type: "reject_plans", reason });
      if (success) {
        setStatusStage("Plans rejected");
      }
    },
    [sendWebSocketMessage, threadId]
  );

  const sendManualOverride = useCallback(
    (action: string) => {
      const success = sendWebSocketMessage({ type: "manual_override", action });
      if (success) {
        setStatusStage(`Manual override: ${action}`);
      }
    },
    [sendWebSocketMessage]
  );

  return {
    backendUrl,
    gridState,
    plans,
    aiAnalysis,
    threadId,
    recommendedPlanId,
    alerts,
    statusStage,
    lastUpdated,
    connectionState,
    loading,
    error,
    applyPlan,
    rejectPlans,
    sendManualOverride,
  };
}
