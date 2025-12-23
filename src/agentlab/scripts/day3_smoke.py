import asyncio
import agentlab.config  # noqa: F401
from agentlab.models.mock_client import MockLLMClient
from agentlab.models.gemini_genai import GeminiGenAIClient
import logging
logger = logging.getLogger(__name__)
messages = [
    {"role": "system", "content": "You are a helpful assistant. Answer in Chinese."},
    {"role": "user", "content": "用一句话解释什么是 multi-agent 系统。"},
]

async def main():
    logger.info("== mock stream ==")
    mock = MockLLMClient()
    async for ch in mock.stream(messages):
        logger.info(ch, end="", flush=True)
    logger.info("\n")

    logger.info("== gemini generate ==")
    g = GeminiGenAIClient()
    logger.info(await g.generate(messages))

    logger.info("\n== gemini stream ==")
    async for ch in g.stream(messages):
        logger.info(ch, end="", flush=True)
    logger.info("\n")

asyncio.run(main())
