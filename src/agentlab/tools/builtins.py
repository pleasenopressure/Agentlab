import time
import math
import asyncio
from typing import Any, Dict

from agentlab.tools.registry import ToolRegistry, ToolSpec, RetryPolicy


def register_builtin_tools(reg: ToolRegistry) -> None:
    # 1) 计算器（sync）
    def calc(args: Dict[str, Any]) -> Dict[str, Any]:
        expr = str(args.get("expression", "")).strip()
        if not expr:
            raise ValueError("expression is required")

        # 安全起见：只允许数字/运算符/括号/空格/小数点
        allowed = set("0123456789+-*/(). %")
        if any(c not in allowed for c in expr):
            raise ValueError("expression contains illegal characters")

        # 简单 eval（仅数学表达式）
        val = eval(expr, {"__builtins__": {}}, {"math": math})
        return {"expression": expr, "value": val}

    reg.register(ToolSpec(
        name="calc",
        description="Evaluate a simple math expression (safe subset).",
        input_schema={"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]},
        func=calc,
        is_async=False,
        timeout_s=3.0,
        retry=RetryPolicy(max_retries=0),
    ))

    # 2) 等待（async）——用于演示取消/超时
    async def sleep_tool(args: Dict[str, Any]) -> Dict[str, Any]:
        seconds = float(args.get("seconds", 1))
        await asyncio.sleep(seconds)
        return {"slept": seconds}

    reg.register(ToolSpec(
        name="sleep",
        description="Sleep for N seconds (demo tool).",
        input_schema={"type": "object", "properties": {"seconds": {"type": "number"}}, "required": ["seconds"]},
        func=sleep_tool,
        is_async=True,
        timeout_s=5.0,
        retry=RetryPolicy(max_retries=0),
    ))

    # 3) 获取当前时间（sync）
    def now(args: Dict[str, Any]) -> Dict[str, Any]:
        _ = args
        return {"unix": time.time()}

    reg.register(ToolSpec(
        name="now",
        description="Get current unix timestamp.",
        input_schema={"type": "object", "properties": {}},
        func=now,
        is_async=False,
        timeout_s=2.0,
        retry=RetryPolicy(max_retries=0),
    ))
