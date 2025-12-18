import asyncio
from typing import AsyncIterator, List
from agentlab.models.base import LLMClient
from agentlab.types import Message
import os

class MockLLMClient(LLMClient):
    def __init__(self, delay_s: float = 0.02) -> None:
        self.delay_s = delay_s

    async def generate(self, messages: List[Message]) -> str:
        last = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        return f"[mock] you said: {last}"

    async def stream(self, messages: List[Message]) -> AsyncIterator[str]:
        text = await self.generate(messages)
        for ch in text:
            await asyncio.sleep(self.delay_s)
            yield ch
