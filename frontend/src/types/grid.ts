export type ConnectionState = "connecting" | "open" | "closed";

export interface GridZone {
  name: string;
  demand: number;
  protected?: boolean;
}

export interface GridStatePayload {
  demand: number;
  supply: number;
  temperature: number;
  zones: GridZone[];
}

export interface GridPlan {
  plan_id: number;
  label: string;
  cuts: string[];
  power_saved: number;
  deficit_mw: number;
  deficit_covered: boolean;
  note: string;
}

export interface AiAnalysis {
  risk_level?: string;
  ml_risk_level?: string;
  llm_risk_level?: string;
  requires_human_approval?: boolean;
  recommendations?: string[];
  avg_confidence?: number;
  ml_confidence?: number;
  anomaly_detected?: boolean;
  anomaly_score?: number;
  ml_llm_disagreement?: boolean;
  time_to_act_minutes?: number;
  agent_errors?: Record<string, string>;
}

export interface GridAlert {
  alert_type: string;
  severity: string;
  message: string;
  timestamp: string;
  data?: Record<string, unknown>;
}

export interface StatusSnapshot {
  grid_state?: GridStatePayload;
  plans?: GridPlan[];
  ai_analysis?: AiAnalysis;
  thread_id?: string;
  paused_threads?: string[];
  timestamp?: string;
}
