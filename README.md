# Smart Grid Health

## How to Run

```bash
pip install -r requirements.txt
export GROQ_API_KEY="your_groq_key_here"

python -m uvicorn backend.main:app --reload
# API: http://localhost:8000
```

## Backend

- Parallel agent execution (Grid Health, Demand, Disaster)
- HITL approval workflow for high/critical risk
- State persistence via SQLite (thread resumability)
- Groq LLM with 15-second timeout & fallback
- Confidence scoring (per-agent + average)
- 6 REST endpoints for workflow control

## Test Results

**11/11 Passing** (~7 seconds)

| Test Category | Count | Status |
|---|---|---|
| Low Risk (auto-approve) | 2 | Pass |
| High Risk (HITL pause) | 2 | Pass |
| Approval Endpoint | 2 | Pass |
| Rejection Endpoint | 2 | Pass |
| Paused Workflows List | 1 | Pass |
| Parallel Performance | 1 | Pass |
| Thread Persistence | 1 | Pass |

