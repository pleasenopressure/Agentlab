import asyncio
from fastapi import FastAPI, WebSocket, Body
from sse_starlette.sse import EventSourceResponse

from agentlab.config import settings
from agentlab.runtime.task_manager import TaskManager

from agentlab.runtime.events import EventBus
from agentlab.api_schemas import ChatRequest
from agentlab.models.gemini_genai import GeminiGenAIClient
from agentlab.tools.registry import ToolRegistry, ToolRunner, ToolError
from agentlab.tools.builtins import register_builtin_tools
from agentlab.orchestration.react_loop import run_react

app = FastAPI(title="AgentLab", version="0.1.0")
# ✅ 新增：一个空的任务管理器对象，用于任务的启动和取消
tm = TaskManager()
# ✅ 新增：一个空的事件总线对象，用于事件的发布和订阅
bus = EventBus()
# ✅ 新增：一个空的工具注册中心对象
tool_reg = ToolRegistry()
# ✅ 新增：在工具注册中心注册一些内置工具
register_builtin_tools(tool_reg)
# ✅ 新增：一个空的工具运行器对象，用于工具的运行
tool_runner = ToolRunner(tool_reg)


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
    await bus.publish(session_id, {"type": "cancel_called"})
    r = tm.cancel(session_id)
    return {"result": r}

@app.get("/session/{session_id}/status")
def status(session_id: str):
    return tm.get_status(session_id)

@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
                "timeout_s": t.timeout_s,
                "max_retries": t.retry.max_retries,
            }
            for t in tool_reg.list()
        ]
    }

@app.post("/session/{session_id}/tool/{tool_name}")
async def call_tool(session_id: str, tool_name: str, args: dict = Body(default={})):
    async def job(token):
        try:
            out = await tool_runner.run(
                session_id=session_id,
                tool_name=tool_name,
                args=args,
                token=token,
                bus=bus,
            )
            await bus.publish(session_id, {"type": "tool_call_done", "tool": tool_name, "output": out})
        except ToolError as e:
            await bus.publish(session_id, {"type": "tool_call_failed", "tool": tool_name, "error": str(e)})
            raise

    r = tm.start(session_id, job)
    return {"result": r}
@app.post("/session/{session_id}/react_chat")
async def react_chat(session_id: str, req: ChatRequest):
    async def job(token):
        await bus.publish(session_id, {"type": "react_user_input", "prompt": req.prompt, "system": req.system})
        await bus.publish(session_id, {"type": "run_start", "kind": "react_chat"})
        try:
            client = GeminiGenAIClient()

            final_text = await run_react(
                session_id=session_id,
                llm=client,
                registry=tool_reg,
                runner=tool_runner,
                bus=bus,
                token=token,
                user_prompt=req.prompt,
                user_system=req.system,
                max_steps=6,
            )

            # 把最终答案也通过事件流发出去（给 UI/终端显示）
            await bus.publish(session_id, {"type": "final", "text": final_text})
            await bus.publish(session_id, {"type": "run_done", "kind": "react_chat"})

        except asyncio.CancelledError:
            await bus.publish(session_id, {"type": "cancelled", "kind": "react_chat"})
            raise
        except Exception as e:
            await bus.publish(session_id, {"type": "error", "kind": "react_chat", "error": str(e)})
            raise

    r = tm.start(session_id, job)
    return {"result": r}
