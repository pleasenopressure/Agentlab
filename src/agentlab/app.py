import asyncio
from fastapi import FastAPI

from agentlab.config import settings
from agentlab.runtime.task_manager import TaskManager

app = FastAPI(title="AgentLab", version="0.1.0")
tm = TaskManager()

@app.get("/")
def root():
    return {"name": "AgentLab", "env": settings.APP_ENV, "hint": "Try /health /docs"}

@app.get("/health")
def health():
    return {"ok": True, "env": settings.APP_ENV}

@app.post("/session/{session_id}/start_demo")
async def start_demo(session_id: str):
    """
    启动一个长任务：每 0.1s 跑一次，总共 300 次。
    真实 agent 以后就是：每步调用 LLM / tool / memory。
    """
    async def job(token):
        for i in range(300):
            await token.checkpoint()
            # 这里模拟“工作中”
            await asyncio.sleep(0.1)

    r = tm.start(session_id, job)
    return {"result": r}

@app.post("/session/{session_id}/cancel")
def cancel(session_id: str):
    r = tm.cancel(session_id)
    return {"result": r}

@app.get("/session/{session_id}/status")
def status(session_id: str):
    return tm.get_status(session_id)
