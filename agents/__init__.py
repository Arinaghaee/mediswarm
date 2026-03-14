import asyncio
import os
from datetime import datetime

import google.genai as genai


def get_genai_client() -> genai.Client:
    """
    Returns a Vertex AI genai client using Application Default Credentials.
    Reads GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_REGION from the environment.
    """
    return genai.Client(
        vertexai=True,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT", "new-gemini-nexus"),
        location=os.environ.get("GOOGLE_CLOUD_REGION", "us-central1"),
    )


async def emit(queue: asyncio.Queue, type_: str, agent: str, message: str, data: dict = None):
    """Shared event emitter for all agents."""
    await queue.put({
        "type": type_,
        "agent": agent,
        "message": message,
        "data": data or {},
        "timestamp": datetime.utcnow().isoformat()
    })
