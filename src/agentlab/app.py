import asyncio
from fastapi import FastAPI, WebSocket
from sse_starlette.sse import EventSourceResponse

from agentlab.config import settings
from agentlab.runtime.task_manager import TaskManager

from agentlab.runtime.events import EventBus
from agentlab.api_schemas import ChatRequest
from agentlab.models.gemini_genai import GeminiGenAIClient

app = FastAPI(title="AgentLab", version="0.1.0")
tm = TaskManager()
bus = EventBus()

@app.get("/")
def root():
    return {"name": "AgentLab", "env": settings.APP_ENV, "hint": "Try /health /docs"}

@app.get("/health")
def health():
    return {"ok": True, "env": settings.APP_ENV}

# ✅ 新增：SSE 事件订阅（Day4 核心）
@app.get("/session/{session_id}/events")
async def sse_events(session_id: str):
    async def gen():
        async for ev in bus.subscribe(session_id):
            yield {"event": "runtime", "data": ev}
    return EventSourceResponse(gen())

# ✅ 可选：WebSocket 推事件（你如果之后做 Studio 更方便）
@app.websocket("/ws/{session_id}")
async def ws(session_id: str, ws: WebSocket):
    await ws.accept()
    q = bus.get_queue(session_id)
    while True:
        ev = await q.get()
        await ws.send_json(ev)

@app.post("/session/{session_id}/start_demo")
async def start_demo(session_id: str):
    """
    启动一个长任务：每 0.1s 跑一次，总共 300 次。
    真实 agent 以后就是：每步调用 LLM / tool / memory。
    """
    async def job(token):
        await bus.publish(session_id, {"type": "run_start", "kind": "demo"})
        try:
            for i in range(300):
                await token.checkpoint()  # ✅ 仍然走你 TaskManager 的取消机制
                await asyncio.sleep(0.1)
                # ✅ 每步发一个事件
                await bus.publish(session_id, {"type": "demo_tick", "i": i})
            await bus.publish(session_id, {"type": "run_done", "kind": "demo"})
        except asyncio.CancelledError:
            await bus.publish(session_id, {"type": "cancelled", "kind": "demo"})
            raise
        except Exception as e:
            await bus.publish(session_id, {"type": "error", "kind": "demo", "error": str(e)})
            raise

    r = tm.start(session_id, job)
    return {"result": r}

# ✅ 新增：真正的 Gemini 流式 chat（Day4 重点）
@app.post("/session/{session_id}/chat")
async def chat(session_id: str, req: ChatRequest):
    async def job(token):
        await bus.publish(session_id, {"type": "run_start", "kind": "chat"})
        client = GeminiGenAIClient()

        messages = []
        if req.system:
            messages.append({"role": "system", "content": req.system})
        messages.append({"role": "user", "content": req.prompt})

        try:
            await bus.publish(session_id, {"type": "llm_start", "model": client.model})

            async for chunk in client.stream(messages):
                await token.checkpoint()  # ✅ 关键：每次输出前检查是否取消
                await bus.publish(session_id, {"type": "llm_delta", "text": chunk})

            await bus.publish(session_id, {"type": "llm_done"})
            await bus.publish(session_id, {"type": "run_done", "kind": "chat"})

        except asyncio.CancelledError:
            await bus.publish(session_id, {"type": "cancelled", "kind": "chat"})
            raise
        except Exception as e:
            await bus.publish(session_id, {"type": "error", "kind": "chat", "error": str(e)})
            raise

    r = tm.start(session_id, job)
    return {"result": r}

@app.post("/session/{session_id}/cancel")
async def cancel(session_id: str):
    # 先告诉前端：已请求取消（UI 可立刻变 stop 状态）
    await bus.publish(session_id, {"type": "cancel_requested"})
    r = tm.cancel(session_id)
    return {"result": r}

@app.get("/session/{session_id}/status")
def status(session_id: str):
    return tm.get_status(session_id)
