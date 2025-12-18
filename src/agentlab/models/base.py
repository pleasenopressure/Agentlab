from abc import ABC, abstractmethod
from typing import AsyncIterator, List
from agentlab.types import Message

class LLMClient(ABC):
    @abstractmethod
    async def generate(self, messages: List[Message]) -> str: ...

    @abstractmethod
    async def stream(self, messages: List[Message]) -> AsyncIterator[str]: ...
