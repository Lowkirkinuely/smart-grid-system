/**
 * SMART GRID SYSTEM - TESTING GUIDE
 * Complete parameter list for backend-frontend communication
 */


// 1. WEBSOCKET MESSAGES (Real-time data from Backend to Frontend)


/**
 * WELCOME MESSAGE (on connection)
 * Sent by backend when client connects
 */
interface WelcomeMessage {
  type: "welcome";
  timestamp: string; // ISO timestamp
  active_connections: number;
  recent_updates: any[]; // Last 5 updates
}

// Example:
// {
//   "type": "welcome",
//   "timestamp": "2025-03-14T15:30:00Z",
//   "active_connections": 3,
//   "recent_updates": [...]
// }


/**
 * ANALYZING MESSAGE (analysis started)
 * Sent when backend starts analyzing grid state
 */
interface AnalyzingMessage {
  type: "analyzing";
  stage: string; // "Running parallel AI analysis + optimization..."
  thread_id: string; // UUID for this analysis session
}

// Example:
// {
//   "type": "analyzing",
//   "stage": "Running parallel AI analysis + optimization...",
//   "thread_id": "550e8400-e29b-41d4-a716-446655440000"
// }


/**
 * PLANS MESSAGE (full grid state + analysis results)
 * Sent after analysis completes
 */
interface PlansMessage {
  type: "plans";
  timestamp: string; // ISO timestamp
  thread_id: string; // Same as in analyzing message
  grid_state: {
    demand: number; // MW
    supply: number; // MW
    temperature: number; // °C
    renewable_percentage: number; // %
    critical_load: number; // MW
  };
  plans: GridPlan[];
  recommended_plan: GridPlan; // Best plan based on risk
  ai_analysis: {
    risk_level: string; // "LOW", "MEDIUM", "HIGH", "CRITICAL"
    ml_risk_level: string; // "LOW", "MEDIUM", "HIGH"
    llm_risk_level: string; // "LOW", "MEDIUM", "HIGH"
    reasoning: string; // Explanation from LLM
    requires_human_approval: boolean;
  };
}

interface GridPlan {
  plan_id: string; // UUID
  name: string; // "PLAN_ALPHA", "PLAN_BRAVO", etc.
  description: string;
  supply_allocation: Record<string, number>; // Region -> MW
  estimated_loss_mw: number;
  cost_ranking: number;
  harm_score: number; // 0-10
  confidence: number; // 0-100 (%)
}

// Example:
// {
//   "type": "plans",
//   "timestamp": "2025-03-14T15:30:15Z",
//   "thread_id": "550e8400-e29b-41d4-a716-446655440000",
//   "grid_state": {
//     "demand": 520,
//     "supply": 480,
//     "temperature": 42.5,
//     "renewable_percentage": 59,
//     "critical_load": 180
//   },
//   "plans": [
//     {
//       "plan_id": "plan-001",
//       "name": "PLAN_ALPHA",
//       "description": "Balanced Distribution",
//       "supply_allocation": {"NR": 150, "SR": 180, "ER": 90, "WR": 60},
//       "estimated_loss_mw": 28,
//       "cost_ranking": 2,
//       "harm_score": 3,
//       "confidence": 92
//     },
//     ...
//   ],
//   "recommended_plan": {...},
//   "ai_analysis": {
//     "risk_level": "MEDIUM",
//     "ml_risk_level": "MEDIUM",
//     "llm_risk_level": "LOW",
//     "reasoning": "Current demand exceeds supply by 40MW...",
//     "requires_human_approval": true
//   }
// }


// ============================================================================
// 2. WEBSOCKET MESSAGES (Frontend to Backend)
// ============================================================================

/**
 * APPLY_PLAN MESSAGE (operator approves a plan)
 * Sent when user clicks "Execute Strategy"
 */
interface ApplyPlanMessage {
  type: "apply_plan";
  plan_id: string; // Which plan was selected
  thread_id: string; // Match the analysis thread
  note: string; // Optional operator note
}

// Example:
// {
//   "type": "apply_plan",
//   "plan_id": "plan-001",
//   "thread_id": "550e8400-e29b-41d4-a716-446655440000",
//   "note": "Executing PLAN_ALPHA - balanced distribution preferred"
// }


/**
 * OPERATOR_INTENT MESSAGE (human preferences)
 * Sent when operator commits preferences via sidebar
 */
interface OperatorIntentMessage {
  type: "operator_intent";
  hospital_protection: number; // 0-100 (%)
  industrial_shedding: number; // 0-100 (%)
  residential_rotation: number; // 0-100 (%)
  timestamp: string; // ISO timestamp
}

// Example:
// {
//   "type": "operator_intent",
//   "hospital_protection": 95,
//   "industrial_shedding": 40,
//   "residential_rotation": 25,
//   "timestamp": "2025-03-14T15:30:20Z"
// }


// ============================================================================
// 3. HTTP ENDPOINTS (REST API)
// ============================================================================

/**
 * POST /grid-state
 * Submit grid state for analysis
 * 
 * Request Body:
 */
interface GridStateRequest {
  demand: number;
  supply: number;
  temperature: number;
  renewable_percentage: number;
  critical_load: number;
}

/**
 * Response:
 */
interface GridStateResponse {
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

// Example POST /grid-state Request:
// {
//   "demand": 520,
//   "supply": 480,
//   "temperature": 42.5,
//   "renewable_percentage": 59,
//   "critical_load": 180
// }

// Example Response:
// {
//   "status": "analysis_complete",
//   "risk_level": "MEDIUM",
//   "ml_risk_level": "MEDIUM",
//   "llm_risk_level": "LOW",
//   "reasoning": "...",
//   "requires_human_approval": true,
//   "plans_generated": 3,
//   "plans": [...],
//   "timestamp": "2025-03-14T15:30:15Z"
// }


// ============================================================================
// 4. ENVIRONMENT VARIABLES
// ============================================================================

/**
 * Frontend (.env.local)
 */
const FRONTEND_ENV = {
  VITE_BACKEND_URL: "http://localhost:8000", // Backend base URL
};

/**
 * Backend (.env)
 */
const BACKEND_ENV = {
  GROQ_API_KEY: "gsk_...", // LLM API key
  OPENWEATHER_API_KEY: "fcc...", // Weather API
  WEATHER_CITY: "London",
  BACKEND_URL: "http://localhost:8000",
  BACKEND_PORT: 8000,
  SIMULATION_INTERVAL: 5, // seconds
  GRID_BASE_SUPPLY: 500, // MW
  HEATWAVE_THRESHOLD: 40, // °C
  EXTREME_COLD_THRESHOLD: -10, // °C
};


// ============================================================================
// 5. DATA FLOW DIAGRAM
// ============================================================================

/*
Frontend (React)                          Backend (FastAPI)
─────────────────────────────────────────────────────────────

[GlobalHeader]
  └─ Real-time metrics
     │
     ├─ gridState.demand ◄──────── WebSocket ◄──── /grid-state response
     ├─ gridState.supply
     ├─ gridState.temperature
     └─ gridState.isConnected

[PlanDrawer]
  └─ Optimization plans
     │
     ├─ gridState.plans ◄────────── WebSocket ◄──── AI Analysis
     ├─ gridState.aiAnalysis
     └─ gridState.requiresHumanApproval
                │
                └─ applyPlan() ───────────► WebSocket ───────► apply_plan handler
                    (plan_id, thread_id, note)

[OperatorSidebar]
  └─ Human preferences
     │
     └─ sendMessage() ──────────────► WebSocket ───────► operator_intent handler
         (hospital_protection, industrial_shedding, etc.)
*/

export default {
  // Message types
  MESSAGE_TYPES: {
    WELCOME: "welcome",
    ANALYZING: "analyzing",
    PLANS: "plans",
    APPLY_PLAN: "apply_plan",
    OPERATOR_INTENT: "operator_intent",
  },

  // Risk levels
  RISK_LEVELS: ["LOW", "MEDIUM", "HIGH", "CRITICAL"],

  // Regions
  REGIONS: ["NR", "SR", "ER", "WR", "NER"],

  // API Endpoints
  ENDPOINTS: {
    GRID_STATE: "/grid-state",
    APPLY_PLAN: "/apply-plan",
    WS: "/ws",
  },
};
