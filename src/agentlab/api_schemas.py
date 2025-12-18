from pydantic import BaseModel

class ChatRequest(BaseModel):
    prompt: str
    system: str | None = None
