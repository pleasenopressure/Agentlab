import asyncio
from typing import Any, AsyncIterator, Dict

class EventBus:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[dict]] = {}

    def get_queue(self, session_id: str) -> asyncio.Queue[dict]:
        self._queues.setdefault(session_id, asyncio.Queue())
        return self._queues[session_id]

    async def publish(self, session_id: str, event: Dict[str, Any]) -> None:
        await self.get_queue(session_id).put(event)

    async def subscribe(self, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        q = self.get_queue(session_id)
        while True:
            yield await q.get()
