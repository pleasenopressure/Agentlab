import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Optional

from .cancel import CancellationToken

@dataclass
class TaskRecord:
    task: asyncio.Task
    token: CancellationToken
    status: str  # running/done/cancelled/error
    error: Optional[str] = None

class TaskManager:
    """
    每个 session_id 对应一个后台任务：
    - start(): 启动并注册
    - cancel(): 取消任务
    - get_status(): 查询状态
    - 自动清理：任务结束后可以选择 remove
    """
    def __init__(self):
        self._tasks: Dict[str, TaskRecord] = {}

    def start(self, session_id: str, coro_factory: Callable[[CancellationToken], Awaitable[None]]) -> str:
        # 如果已有运行中的任务，先拒绝或先取消再重启（这里选择拒绝，更安全）
        if session_id in self._tasks and self._tasks[session_id].status == "running":
            return "already_running"
        # 准备取消令牌
        token = CancellationToken()
        #  随时捕捉token.cancel()的信号
        async def runner():
            try:
                await coro_factory(token)
                self._tasks[session_id].status = "done"
            except asyncio.CancelledError:
                self._tasks[session_id].status = "cancelled"
                raise
            except Exception as e:
                self._tasks[session_id].status = "error"
                self._tasks[session_id].error = str(e)

        task = asyncio.create_task(runner(), name=f"session:{session_id}")
        self._tasks[session_id] = TaskRecord(task=task, token=token, status="running")

        # 任务结束后自动清理引用（避免内存泄露）
        # Python 的 lambda 本质上是一个匿名函数（没有名字的函数），其标准语法是： lambda 参数列表: 表达式
        # 对应到这里：
        # 参数列表：_t
        # 表达式：self._cleanup(session_id)

        # 为什么要加个 _t？
        # 这是因为 task.add_done_callback 的硬性规定。
        # add_done_callback 在任务完成时调用回调函数时，一定会把该任务对象（Task/Future）作为第一个参数传进去。
        # 如果我们写 lambda: self._cleanup(...)（不带参数），代码运行时会由 asyncio 抛出 TypeError，因为它尝试传参，但你的函数不接收参数。
        # 使用下划线开头（如 _t 或 _）是 Python 里的惯例，表示“我知道这里有个参数传进来，但我不需要用它，我只想占个位”。


        task.add_done_callback(lambda _t: self._cleanup(session_id))
        return "started"

    def cancel(self, session_id: str) -> str:
        rec = self._tasks.get(session_id)
        if not rec:
            return "not_found"

        # 双保险：token + task.cancel
        rec.token.cancel()
        rec.task.cancel()
        return "cancelling"

    def get_status(self, session_id: str) -> Dict:
        rec = self._tasks.get(session_id)
        if not rec:
            return {"exists": False}
        return {"exists": True, "status": rec.status, "error": rec.error}

    def _cleanup(self, session_id: str) -> None:
        # 如果你希望保留历史状态，可不删除；Day2 建议删除，避免堆积
        # 如果你想保留最后状态用于 /status 查询，可以延迟删除或另存 session_store
        # 这里做：结束后保留 60 秒再删（简化：先不延迟，直接删）
        # 你也可以改成：只删 task/token，保留 status 到 session_store
        pass
