import asyncio
import json
import os
import uuid
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from agents.orchestrator import run_swarm  # noqa: E402 (after load_dotenv)

app = FastAPI(title="MediSwarm API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store (fine for hackathon)
sessions: dict[str, dict] = {}


@app.post("/api/query")
async def start_query(body: dict, background_tasks: BackgroundTasks):
    """Start a new swarm research session."""
    session_id = body.get("session_id", str(uuid.uuid4()))
    query = body.get("query", "").strip()

    if not query:
        return {"error": "query is required"}, 400

    queue: asyncio.Queue = asyncio.Queue()
    sessions[session_id] = {
        "status": "running",
        "result": None,
        "queue": queue,
        "events": [],
        "query": query,
        "created_at": datetime.utcnow().isoformat()
    }
    background_tasks.add_task(run_swarm, query, session_id, queue)
    return {"session_id": session_id, "status": "started"}


@app.get("/api/stream/{session_id}")
async def stream_events(session_id: str):
    """Server-Sent Events endpoint — streams agent events in real-time."""
    if session_id not in sessions:
        async def _not_found():
            yield f'data: {json.dumps({"type": "error", "message": "Session not found"})}\n\n'
        return StreamingResponse(_not_found(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    async def event_generator():
        queue: asyncio.Queue = sessions[session_id]["queue"]
        while True:
            try:
                # Use timeout so the connection doesn't hang forever if something goes wrong
                event = await asyncio.wait_for(queue.get(), timeout=120.0)
            except asyncio.TimeoutError:
                yield f'data: {json.dumps({"type": "error", "message": "Stream timeout"})}\n\n'
                break

            sessions[session_id]["events"].append(event)
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(0)  # yield control to event loop

            if event["type"] in ("swarm_complete", "error"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.get("/api/result/{session_id}")
async def get_result(session_id: str):
    """Return the final clinical brief once the swarm is complete."""
    s = sessions.get(session_id)
    if not s:
        return {"error": "session not found", "status": 404}
    if s["status"] == "running":
        return {"status": "running", "message": "Swarm still in progress"}
    return s["result"]


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# Serve built React app (production / Cloud Run)
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
