from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Optional

from agentlab.types import Message
from agentlab.tools.registry import ToolRunner, ToolRegistry, ToolError

# 代码使用这个正则在 AI 返回的一大段废话（比如：“好的，这是你要的JSON：
# \njson\n{...}\n”）中，精准定位并抠出 {...} 这部分，以便后续用 json.loads 进行解析。
JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> Dict[str, Any]:
    """
    从模型输出里提取第一个 JSON 对象。
    允许模型输出前后带一些解释，但我们只抓 {...} 这一段。
    """
    m = JSON_RE.search(text.strip())
    if not m:
        raise ValueError(f"Cannot find JSON object in model output: {text[:200]!r}")
    return json.loads(m.group(0))


def _tools_summary(registry: ToolRegistry) -> str:
    """把工具列表总结成给模型看的说明（name/desc/schema 简化）。"""
    lines = []
    for t in registry.list():
        # schema 只展示 properties + required，避免太长
        props = t.input_schema.get("properties", {})
        req = t.input_schema.get("required", [])
        lines.append(
            f"- {t.name}: {t.description}\n"
            f"  args.properties={list(props.keys())}, required={req}, timeout={t.timeout_s}s, max_retries={t.retry.max_retries}"
        )
    return "\n".join(lines)


def build_react_system_prompt(registry: ToolRegistry) -> str:
    """
    ReAct 的“动作协议”：
    - 工具调用：{"type":"tool","tool_name":"calc","args":{...}}
    - 最终回答：{"type":"final","final":"..."}
    约束：只输出 JSON，不要多余文本（提升解析稳定性）
    """
    tools = _tools_summary(registry)
    return (
        "你是一个会使用工具的智能体。你必须严格按 JSON 输出，不要输出任何额外文本。\n"
        "当你需要外部计算/信息时，先输出工具调用 JSON：\n"
        '{"type":"tool","tool_name":"<tool>","args":{...}}\n'
        "当你已经得到最终答案时，输出：\n"
        '{"type":"final","final":"<你的最终回答>"}\n'
        "规则：\n"
        "1) 只能从工具列表里选择 tool_name。\n"
        "2) args 必须符合该工具的参数。\n"
        "3) 如果用户要求中文，请 final 用简体中文。\n"
        "4) 不要输出思考过程，不要输出 markdown，只输出 JSON。\n\n"
        f"可用工具列表：\n{tools}\n"
    )


async def run_react(
    *,
    session_id: str,
    llm: Any,                 # GeminiGenAIClient (implements generate/stream)
    registry: ToolRegistry,
    runner: ToolRunner,
    bus: Any,                 # EventBus
    token: Any,               # TaskManager token（有 checkpoint）
    user_prompt: str,
    user_system: Optional[str] = None,
    max_steps: int = 6,
) -> str:
    """
    最小 ReAct loop：
    - LLM 产出 action JSON
    - tool -> 执行 -> observation 回灌
    - final -> 返回答案
    """
    system_prompt = build_react_system_prompt(registry)
    if user_system:
        # 用户 system 作为附加要求（如“用中文回答”）
        system_prompt = system_prompt + "\n用户额外要求：\n" + user_system.strip()

    messages: List[Message] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    await bus.publish(session_id, {"type": "react_start", "max_steps": max_steps})

    for step in range(1, max_steps + 1):
        await token.checkpoint()
        await bus.publish(session_id, {"type": "react_step_start", "step": step})

        raw = await llm.generate(messages)
        await bus.publish(session_id, {"type": "react_model_raw", "step": step, "text": raw})

        # 把模型输出也加入上下文（assistant）
        messages.append({"role": "assistant", "content": raw})

        try:
            action = _extract_json(raw)
        except Exception as e:
            # 解析失败：发事件并终止
            await bus.publish(session_id, {"type": "react_parse_error", "step": step, "error": str(e)})
            raise

        atype = action.get("type")

        if atype == "tool":
            tool_name = action.get("tool_name")
            args = action.get("args", {})
            if not isinstance(tool_name, str):
                raise ValueError(f"tool_name must be string, got: {tool_name!r}")
            if not isinstance(args, dict):
                raise ValueError(f"args must be object, got: {args!r}")

            await bus.publish(session_id, {"type": "react_tool_selected", "step": step, "tool": tool_name, "args": args})

            # 执行工具（ToolRunner 内部会发 tool_start/tool_end/tool_error）
            await token.checkpoint()
            try:
                out = await runner.run(
                    session_id=session_id,
                    tool_name=tool_name,
                    args=args,
                    token=token,
                    bus=bus,
                )
            except ToolError as e:
                # 工具失败也作为 observation 回灌，让模型决定怎么办（或直接报错）
                obs = {"ok": False, "error": str(e)}
                await bus.publish(session_id, {"type": "react_observation", "step": step, "observation": obs})
                messages.append({"role": "user", "content": f"Observation: {json.dumps(obs, ensure_ascii=False)}"})
                continue

            obs = {"ok": True, "tool": tool_name, "output": out}
            await bus.publish(session_id, {"type": "react_observation", "step": step, "observation": obs})
            messages.append({"role": "user", "content": f"Observation: {json.dumps(obs, ensure_ascii=False)}"})
            continue

        if atype == "final":
            final_text = action.get("final", "")
            if not isinstance(final_text, str):
                raise ValueError("final must be string")
            await bus.publish(session_id, {"type": "react_done", "step": step})
            return final_text

        raise ValueError(f"Unknown action type: {atype!r}")

    # 超过步数仍未 final
    raise RuntimeError(f"ReAct exceeded max_steps={max_steps} without producing final answer.")
