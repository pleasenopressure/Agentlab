import asyncio
import agentlab.config  # noqa: F401
from agentlab.models.mock_client import MockLLMClient
from agentlab.models.gemini_genai import GeminiGenAIClient

messages = [
    {"role": "system", "content": "You are a helpful assistant. Answer in Chinese."},
    {"role": "user", "content": "用一句话解释什么是 multi-agent 系统。"},
]

async def main():
    print("== mock stream ==")
    mock = MockLLMClient()
    async for ch in mock.stream(messages):
        print(ch, end="", flush=True)
    print("\n")

    print("== gemini generate ==")
    g = GeminiGenAIClient()
    print(await g.generate(messages))

    print("\n== gemini stream ==")
    async for ch in g.stream(messages):
        print(ch, end="", flush=True)
    print()

asyncio.run(main())
