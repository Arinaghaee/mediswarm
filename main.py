import asyncio
import json
import logging
import os
import uuid
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

# ---------------------------------------------------------------------------
# Logging — configure once here; every agent uses getLogger(__name__)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
# Quiet noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("Bio").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)

logger = logging.getLogger("main")

from agents.orchestrator import run_swarm  # noqa: E402 (after load_dotenv + logging setup)

app = FastAPI(title="MediSwarm API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, dict] = {}


@app.post("/api/query")
async def start_query(body: dict):
    """Start a new swarm research session."""
    session_id = body.get("session_id", str(uuid.uuid4()))
    query = body.get("query", "").strip()

    if not query:
        logger.warning("Received /api/query with empty query body")
        return {"error": "query is required"}, 400

    logger.info("New session started | session_id=%s | query=%r", session_id, query)

    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(run_swarm(query, session_id, queue))
    sessions[session_id] = {
        "status": "running",
        "result": None,
        "queue": queue,
        "task": task,
        "events": [],
        "query": query,
        "created_at": datetime.utcnow().isoformat(),
    }
    return {"session_id": session_id, "status": "started"}


@app.post("/api/stop/{session_id}")
async def stop_session(session_id: str):
    """Cancel a running swarm session."""
    s = sessions.get(session_id)
    if not s:
        return {"error": "session not found"}
    task: asyncio.Task = s.get("task")
    if task and not task.done():
        task.cancel()
        logger.info("Session cancelled by user | session_id=%s", session_id)
    s["status"] = "cancelled"
    # Push a terminal event so the SSE generator closes cleanly
    await s["queue"].put({"type": "error", "agent": "system",
                          "message": "Stopped by user.", "data": {}})
    return {"session_id": session_id, "status": "cancelled"}


@app.get("/api/stream/{session_id}")
async def stream_events(session_id: str):
    """Server-Sent Events endpoint — streams agent events in real-time."""
    if session_id not in sessions:
        logger.warning("SSE requested for unknown session_id=%s", session_id)

        async def _not_found():
            yield f'data: {json.dumps({"type": "error", "message": "Session not found"})}\n\n'

        return StreamingResponse(
            _not_found(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    logger.info("SSE stream opened | session_id=%s", session_id)

    async def event_generator():
        queue: asyncio.Queue = sessions[session_id]["queue"]
        event_count = 0
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=120.0)
            except asyncio.TimeoutError:
                logger.error("SSE stream timed out | session_id=%s after %d events",
                             session_id, event_count)
                yield f'data: {json.dumps({"type": "error", "message": "Stream timeout"})}\n\n'
                break

            sessions[session_id]["events"].append(event)
            event_count += 1
            logger.debug("SSE event #%d | session=%s | type=%s | agent=%s | msg=%r",
                         event_count, session_id, event["type"], event.get("agent"), event["message"])
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(0)

            if event["type"] in ("swarm_complete", "error"):
                logger.info("SSE stream closing | session_id=%s | final_type=%s | total_events=%d",
                            session_id, event["type"], event_count)
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/result/{session_id}")
async def get_result(session_id: str):
    """Return the final clinical brief once the swarm is complete."""
    s = sessions.get(session_id)
    if not s:
        logger.warning("Result requested for unknown session_id=%s", session_id)
        return {"error": "session not found", "status": 404}
    if s["status"] == "running":
        logger.debug("Result polled but still running | session_id=%s", session_id)
        return {"status": "running", "message": "Swarm still in progress"}
    logger.info("Result served | session_id=%s | status=%s", session_id, s["status"])
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
