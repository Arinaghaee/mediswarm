# SPEC: Backend (FastAPI + SSE + ADK Runner)

## File: `main.py`

Build a FastAPI application with these endpoints:

### Endpoints

**POST `/api/query`**
- Accepts: `{ "query": "string", "session_id": "string" }`
- Starts an async background task running the agent swarm
- Returns: `{ "session_id": "string", "status": "started" }`

**GET `/api/stream/{session_id}`**
- Server-Sent Events endpoint
- Streams agent events in real-time as they happen
- Each SSE event is JSON with this shape:
```json
{
  "type": "agent_start" | "agent_thinking" | "agent_done" | "agent_failed" | "swarm_complete" | "error",
  "agent": "orchestrator" | "literature_scout" | "pdf_indexer" | "risk_analyst" | "synthesizer" | "safety_guard" | "report_builder",
  "message": "Human readable status message",
  "data": {},
  "timestamp": "ISO8601"
}
```

**GET `/api/health`**
- Returns `{ "status": "ok", "version": "1.0.0" }`

**GET `/api/result/{session_id}`**
- Returns the final clinical brief once swarm is complete
- Returns 404 if session not found, 202 if still running

### SSE Event Sequence (emit these in order)
```
agent_start     → orchestrator: "Planning research strategy..."
agent_thinking  → orchestrator: "Identified 4 sub-tasks, delegating to agents"
agent_start     → literature_scout: "Searching PubMed..."
agent_start     → pdf_indexer: "Preparing document indexer..."
agent_start     → risk_analyst: "Loading risk factor models..."
agent_start     → synthesizer: "Standing by for evidence..."
agent_thinking  → literature_scout: "Found 23 papers, filtering by relevance..."
agent_done      → literature_scout: "Retrieved 8 high-relevance papers"
agent_thinking  → pdf_indexer: "Chunking 3 full-text PDFs..."
agent_done      → pdf_indexer: "Indexed 147 chunks"
agent_thinking  → risk_analyst: "Extracting risk factors from literature..."
agent_done      → risk_analyst: "Ranked 12 risk factors by evidence strength"
agent_thinking  → synthesizer: "Merging findings across sources..."
agent_done      → synthesizer: "Evidence synthesis complete"
agent_start     → safety_guard: "Validating citations and claims..."
agent_done      → safety_guard: "All 8 citations verified"
agent_start     → report_builder: "Generating clinical brief..."
agent_done      → report_builder: "Clinical brief ready"
swarm_complete  → "Research complete"
```

### Session State Store
Use a simple in-memory dict (fine for hackathon):
```python
sessions: dict[str, dict] = {}
# Shape: { session_id: { "status": "running"|"complete"|"failed", "result": {...}, "events": [...] } }
```

### Implementation Notes
- Use `asyncio.Queue` per session to pipe events from agents to SSE stream
- Set CORS to allow `*` for hackathon
- Include `asyncio.sleep(0)` yields in SSE loop to prevent blocking
- SSE format: `data: {json}\n\n`
- Set SSE headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`

### Full main.py structure:
```python
import asyncio, json, uuid
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from agents.orchestrator import run_swarm

app = FastAPI(title="MediSwarm API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

sessions: dict[str, dict] = {}

@app.post("/api/query")
async def start_query(body: dict, background_tasks: BackgroundTasks):
    session_id = body.get("session_id", str(uuid.uuid4()))
    queue = asyncio.Queue()
    sessions[session_id] = {"status": "running", "result": None, "queue": queue, "events": []}
    background_tasks.add_task(run_swarm, body["query"], session_id, queue)
    return {"session_id": session_id, "status": "started"}

@app.get("/api/stream/{session_id}")
async def stream_events(session_id: str):
    async def event_generator():
        queue = sessions[session_id]["queue"]
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event["type"] in ("swarm_complete", "error"):
                break
    return StreamingResponse(event_generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/api/result/{session_id}")
async def get_result(session_id: str):
    s = sessions.get(session_id)
    if not s: return {"error": "not found"}, 404
    if s["status"] == "running": return {"status": "running"}, 202
    return s["result"]

@app.get("/api/health")
async def health(): return {"status": "ok", "version": "1.0.0"}
```

## File: `requirements.txt`

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
google-adk==0.5.0
google-generativeai==0.8.0
biopython==1.84
pypdf==4.3.1
sentence-transformers==3.0.1
httpx==0.27.0
python-dotenv==1.0.1
pydantic==2.8.0
google-cloud-storage==2.18.0
google-cloud-aiplatform==1.65.0
```
