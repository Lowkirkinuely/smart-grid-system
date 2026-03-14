# Smart Grid System

AI-powered, human-in-the-loop control room for the Indian grid. The backend fuses OR-Tools + LangGraph + ML with MongoDB persistence, the frontend is a Vite + React dashboard that subscribes to live updates, and the simulator feeds synthetic or real weather-driven grid telemetries into the REST/WebSocket stack.

## Repo layout
- `backend`: FastAPI service exposing `/grid-state`, `/status`, `/ws`, history endpoints, the optimizer, AI agents, and MongoDB persistence.
- `frontend`: Vite + React dashboard that hits `/status` for snapshots and connects to `/ws` for real-time updates, then surfaces the AI plan data.
- `Simulation`: Async CLI simulator that POSTs grid readings to the backend (`/grid-state`) so the dashboard always has something to visualize.
- `venv` / `node_modules` are ignored; use local virtual environments per component.

## Prerequisites
- Python 3.11+ (the backend and simulator share a `requirements.txt`).
- Node.js 20+ and npm/yarn/pnpm for the frontend.
- A MongoDB instance (local or managed) if you want history/audit trails; the backend can run without it but history endpoints will be empty.
- API keys: `GROQ_API_KEY` is required for the LangGraph LLM. Optional: `OPENWEATHER_API_KEY` unlocks live weather simulation.

## Backend setup
1. `cd backend` and create a venv: `python -m venv venv && source venv/bin/activate` (Windows users can use `venv\Scripts\activate`).
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and populate:
   - `GROQ_API_KEY`: your Groq LLM key (required). `localhost` requests will fail without it.
   - `MONGODB_URI` / `MONGODB_DB`: point to your MongoDB, defaults to `mongodb://localhost:27017` / `smart_grid`.
   - `OPENWEATHER_API_KEY`: optional, the simulator will fall back to mock weather if missing.
   - `BACKEND_URL`: `http://localhost:8000` by default, used when the simulator or other tools need the base URL.
4. Start the server: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`.

## Frontend setup
1. `cd frontend` and install the JS deps: `npm install` (or `yarn`, `pnpm`).
2. Copy `.env.example` to `.env` and adjust `VITE_BACKEND_URL` if your backend runs on a non-default host/port.
3. `npm run dev` to fire up the dashboard (defaults to `http://localhost:5173`).
4. The UI now uses `useGridData` to fetch `/status` for the latest snapshot and opens a WebSocket to `/ws` for live plan broadcasts, risk updates, and alerts.

## Running the simulator
1. `cd Simulation` (the simulator reuses the backend venv if desired).
2. `python simulator.py --mode escalate` to loop through a full day/night story. Other modes: `scenarios`, `weather`, `cities`, `random`, or drop `--mode` to run all scenarios once.
3. The simulator POSTs to `/grid-state` and prints the risk summary; every submission triggers the backend optimizer + AI pipeline.
4. If you set `OPENWEATHER_API_KEY` in the backend `.env`, the weather mode pulls real conditions instead of mocks.

## Integration flow
1. Startup order: backend → simulator → frontend. The simulator keeps the backend busy with telemetry so the dashboard always has meaningful data.
2. The dashboard’s `useGridData` hook reads `/status` for history, then binds to `/ws`. WebSocket messages carry the latest `grid_state`, `plans`, `ai_analysis`, and `recommended_plan`. Alerts/HITL events are also streamed.
3. The backend WebSocket broadcasts every time `/grid-state` receives data, so tying the simulator and frontend together simply requires the backend to be running and accessible to both.

## Quick checks
- Backend health: `http://localhost:8000/health`.
- Live data snapshot: `http://localhost:8000/status`.
- Plans history: `http://localhost:8000/history/grid` and `/history/analyses`.
- Frontend: visit `http://localhost:5173` and you should see grid-wide risk, plan cards, and logs as soon as the simulator posts a payload.

## Next steps
- Hook the sliders/buttons in `OperatorSidebar` and `PlanDrawer` to real control-plane endpoints once the operator intent APIs are available.
- Persist simulator scenarios or add real data sources (SCADA, PMUs) by posting to `/grid-state` with the same payload shape.
