import asyncio
import os
from typing import AsyncIterator, List, Optional

from google import genai
from google.genai import types

from agentlab.models.base import LLMClient
from agentlab.types import Message


class GeminiGenAIClient(LLMClient):
    """
    Google GenAI SDK (Gemini Developer API):
    - 非流式：client.models.generate_content(...)
    - 流式： client.models.generate_content_stream(...)  -> for chunk in response: chunk.text
    参考官方示例。:contentReference[oaicite:2]{index=2}
    """
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        # client = genai.Client() 会自动读取 GEMINI_API_KEY / GOOGLE_API_KEY 等环境变量。:contentReference[oaicite:3]{index=3}
        self.client = genai.Client(api_key=api_key) if api_key else genai.Client()
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def _to_contents_and_config(self, messages: List[Message]):
        # 1) system -> system_instruction（推荐走 config）
        system_texts = [m.get("content", "") for m in messages if m.get("role") == "system" and m.get("content")]
        system_instruction = "\n".join(system_texts).strip() if system_texts else None

        # 2) user/assistant -> contents（assistant 映射到 model）
        contents: list[types.Content] = []
        for m in messages:
            role = m.get("role")
            text = (m.get("content") or "").strip()
            if not text or role == "system":
                continue
            # 将 assistant 改名为 model
            if role == "assistant":
                role = "model"
            if role not in ("user", "model"):
                # Day3 先只做文本对话；tool/function 我们 Day5/Week2 再接
                continue
            # 把简单的字符串包装成 types.Content 对象。注意这里还有一个 parts 层级。Gemini 是多模态模型。
            # 一条消息（Content）可以包含多个部分（Parts），比如一段文字 + 一张图片 + 一段视频。
            # 虽然这里我们只发文本，但仍必须按照 Content -> Parts -> Text 的层级结构来通过 types.Part.from_text(text) 进行构造。
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))

        config = types.GenerateContentConfig(system_instruction=system_instruction) if system_instruction else None
        return contents, config

    async def generate(self, messages: List[Message]) -> str:
        contents, config = self._to_contents_and_config(messages)

        def _call() -> str:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            return resp.text or ""

        return await asyncio.to_thread(_call)

    async def stream(self, messages: List[Message]) -> AsyncIterator[str]:
        contents, config = self._to_contents_and_config(messages)

        q: asyncio.Queue[Optional[str]] = asyncio.Queue()

        def _producer(max_retries: int = 4, base_delay: float = 0.6):
            attempt = 0
            while True:
                try:
                    resp_stream = self.client.models.generate_content_stream(
                        model=self.model,
                        contents=contents,
                        config=config,
                    )
                    for chunk in resp_stream:
                        txt = getattr(chunk, "text", None)
                        if txt:
                            q.put_nowait(("token", txt))
                    q.put_nowait(("done", None))
                    return

                except genai_errors.ServerError as e:
                    # 503 过载：退避重试
                    msg = str(e)
                    if "503" in msg and attempt < max_retries:
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 0.25)
                        time.sleep(delay)
                        attempt += 1
                        continue
                    q.put_nowait(("error", f"Gemini stream failed: {e!r}"))
                    return

                except Exception as e:
                    q.put_nowait(("error", f"Gemini stream failed: {e!r}"))
                    return

        prod_future = asyncio.get_running_loop().run_in_executor(None, _producer)

        try:
            while True:
                kind, payload = await q.get()
                if kind == "token" and payload is not None:
                    yield payload
                elif kind == "done":
                    break
                else:
                    raise RuntimeError(payload or "Unknown streaming error")
        finally:
            # 回收后台 future
            await prod_future
