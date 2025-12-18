from typing import TypedDict, Any, Optional

class AgentConfig(TypedDict):
    name: str
    model: str
    temperature: float

class Message(TypedDict):
    role: str
    content: str
    
class AgentContext(TypedDict):
    session_id: str
    messages: list[Message]
    metadata: Optional[dict[str, Any]]
