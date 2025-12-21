from __future__ import annotations
import asyncio
import time
import random
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

JsonDict = Dict[str, Any]
ToolFunc = Callable[[JsonDict], Any]  # 支持 sync；async 用 is_async 标识


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 2
    base_delay_s: float = 0.4
    max_delay_s: float = 3.0
    jitter_s: float = 0.2


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: JsonDict  # 简化版 JSON Schema
    func: Callable[..., Any]  # func(args) 或 async func(args)
    is_async: bool = False
    timeout_s: float = 10.0
    retry: RetryPolicy = RetryPolicy()


class ToolError(RuntimeError):
    def __init__(self, tool_name: str, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(f"[{tool_name}] {message}")
        self.tool_name = tool_name
        self.cause = cause


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name]

    def list(self) -> list[ToolSpec]:
        return sorted(self._tools.values(), key=lambda t: t.name)


class ToolRunner:
    """
    负责“治理”工具执行：timeout / retry / sync->thread / 取消检查 / 事件上报
    token: 你 TaskManager 的 cancel token（需支持 await token.checkpoint()）
    bus:   你的 EventBus，用于 SSE 推送 tool_start/tool_end/tool_error
    """
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def _call_func(self, spec: ToolSpec, args: JsonDict) -> Any:
        if spec.is_async:
            return await spec.func(args)  # type: ignore[misc]
        # sync 工具放线程池，避免阻塞 event loop
        return await asyncio.to_thread(spec.func, args)

    async def run(
        self,
        *,
        session_id: str,
        tool_name: str,
        args: JsonDict,
        token: Any,
        bus: Any,
    ) -> JsonDict:
        spec = self.registry.get(tool_name)

        await bus.publish(session_id, {
            "type": "tool_start",
            "tool": spec.name,
            "args": args,
            "timeout_s": spec.timeout_s,
            "max_retries": spec.retry.max_retries,
        })

        attempt = 0
        start = time.time()
        last_err: Exception | None = None

        while True:
            # ✅ 取消点：每次尝试前都检查
            await token.checkpoint()

            try:
                attempt += 1
                t0 = time.time()

                # ✅ timeout：超时直接抛 TimeoutError
                result = await asyncio.wait_for(self._call_func(spec, args), timeout=spec.timeout_s)

                dur_ms = int((time.time() - t0) * 1000)
                await bus.publish(session_id, {
                    "type": "tool_end",
                    "tool": spec.name,
                    "attempt": attempt,
                    "duration_ms": dur_ms,
                    "ok": True,
                })
                return {"ok": True, "tool": spec.name, "result": result, "attempt": attempt}

            except asyncio.CancelledError:
                await bus.publish(session_id, {"type": "tool_cancelled", "tool": spec.name, "attempt": attempt})
                raise

            except Exception as e:
                last_err = e
                await bus.publish(session_id, {
                    "type": "tool_error",
                    "tool": spec.name,
                    "attempt": attempt,
                    "error": repr(e),
                })

                if attempt > spec.retry.max_retries:
                    total_ms = int((time.time() - start) * 1000)
                    raise ToolError(spec.name, f"failed after {attempt} attempts ({total_ms}ms)", cause=e)

                # ✅ retry：指数退避 + jitter
                delay = min(spec.retry.base_delay_s * (2 ** (attempt - 1)), spec.retry.max_delay_s)
                delay += random.uniform(0, spec.retry.jitter_s)
                await asyncio.sleep(delay)
