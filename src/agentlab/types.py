from typing import TypedDict, Any, Optional
Role = Literal["system", "user", "assistant", "tool"]

class AgentConfig(TypedDict):
    name: str
    model: str
    temperature: float


class Message(TypedDict, total=False):
    role: Role
    content: str
    name: str
    tool_call_id: str
    meta: dict[str, Any]
    
class AgentContext(TypedDict):
    session_id: str
    messages: list[Message]
    metadata: Optional[dict[str, Any]]
