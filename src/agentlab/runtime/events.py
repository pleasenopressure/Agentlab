import asyncio
from typing import Any, AsyncIterator, Dict

class EventBus:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[dict]] = {}

    def get_queue(self, session_id: str) -> asyncio.Queue[dict]:
        self._queues.setdefault(session_id, asyncio.Queue())
        return self._queues[session_id]

    def _attach_trace(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """给事件附加 trace_id/span_id（如果当前有活跃 span）。"""
        try:
            span = trace.get_current_span()
            ctx = span.get_span_context()
            if ctx and ctx.is_valid:
                # ⚠️ 不要改原始 dict，返回一个 copy 更安全
                e = dict(event)
                e["trace_id"] = f"{ctx.trace_id:032x}"
                e["span_id"] = f"{ctx.span_id:016x}"
                return e
        except Exception as e:
            print(f"Failed to attach trace: {e}")
            return event

    async def publish(self, session_id: str, event: Dict[str, Any]) -> None:
        """发布事件，会自动附加 trace_id/span_id。"""
        print(f"Publishing event: {event}")
        await self.get_queue(session_id).put(self._attach_trace(event))
        print("queue size after put:", self.get_queue(session_id).qsize())
    
    async def subscribe(self, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        q = self.get_queue(session_id)
        while True:
            yield await q.get()
            print("consumed by subscriber:", session_id, ev)  # ✅

