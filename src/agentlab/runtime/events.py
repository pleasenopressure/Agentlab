import asyncio
import logging
from typing import Any, AsyncIterator, Dict

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[dict]] = {}

    def get_queue(self, session_id: str) -> asyncio.Queue[dict]:
        self._queues.setdefault(session_id, asyncio.Queue())
        return self._queues[session_id]

    def _attach_trace(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """给事件附加 trace_id/span_id（如果当前有活跃 span）。永远返回 dict。"""
        try:
            span = trace.get_current_span()
            ctx = span.get_span_context()
            if ctx and ctx.is_valid:
                e = dict(event)  # 不修改原 dict
                e["trace_id"] = f"{ctx.trace_id:032x}"
                e["span_id"] = f"{ctx.span_id:016x}"
                return e
        except Exception as ex:
            # 观测逻辑绝不能影响业务：只记录，不要再抛
            logger.exception("Failed to attach trace: %s", ex)
            try:
                s = trace.get_current_span()
                s.record_exception(ex)
                s.set_status(Status(StatusCode.ERROR, str(ex)))
            except Exception:
                pass

        # ✅ ctx 无效 或 没有 span：原样返回
        return event

    async def publish(self, session_id: str, event: Dict[str, Any]) -> None:
        """发布事件，会自动附加 trace_id/span_id。"""
        q = self.get_queue(session_id)
        ev = self._attach_trace(event)

        logger.info("Publishing event session=%s type=%s", session_id, ev.get("type"))
        await q.put(ev)
        logger.info("queue size after put session=%s size=%d", session_id, q.qsize())

    async def subscribe(self, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        q = self.get_queue(session_id)
        while True:
            ev = await q.get()
            logger.info("consumed by subscriber session=%s type=%s", session_id, getattr(ev, "get", lambda *_: None)("type"))
            yield ev
