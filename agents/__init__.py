import asyncio
from datetime import datetime


async def emit(queue: asyncio.Queue, type_: str, agent: str, message: str, data: dict = None):
    """Shared event emitter for all agents."""
    await queue.put({
        "type": type_,
        "agent": agent,
        "message": message,
        "data": data or {},
        "timestamp": datetime.utcnow().isoformat()
    })
