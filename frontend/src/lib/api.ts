/**
 * API Service for backend communication
 */

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export interface GridState {
  demand: number;
  supply: number;
  temperature: number;
  renewable_percentage: number;
  critical_load: number;
}

export interface GridPlan {
  plan_id: string;
  name: string;
  description: string;
  supply_allocation: Record<string, number>;
  estimated_loss_mw: number;
  cost_ranking: number;
  harm_score: number;
  confidence: number;
}

export interface AiAnalysis {
  risk_level: string;
  ml_risk_level: string;
  llm_risk_level: string;
  reasoning: string;
  requires_human_approval: boolean;
}

export interface GridStateResponse {
  status: string;
  risk_level: string;
  ml_risk_level: string;
  llm_risk_level: string;
  reasoning: string;
  requires_human_approval: boolean;
  plans_generated: number;
  plans: GridPlan[];
  timestamp: string;
}

/**
 * Send grid state to backend for analysis
 */
export async function submitGridState(gridState: GridState): Promise<GridStateResponse> {
  const response = await fetch(`${BACKEND_URL}/grid-state`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(gridState),
  });

  if (!response.ok) {
    throw new Error(`Failed to submit grid state: ${response.statusText}`);
  }

  return response.json();
}

export default {
  BACKEND_URL,
  submitGridState,
};
