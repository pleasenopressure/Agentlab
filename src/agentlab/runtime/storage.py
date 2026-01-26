import json
import os
import logging
from typing import List
from agentlab.types import Message

logger = logging.getLogger(__name__)

class FileSessionStore:
    def __init__(self, base_dir: str = "sessions"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def _get_path(self, session_id: str) -> str:
        # 安全起见，防止路径遍历攻击，最好做个校验，这里简化处理
        return os.path.join(self.base_dir, f"{session_id}.json")

    def load(self, session_id: str) -> List[Message]:
        """加载会话历史，如果不存在返回空列表"""
        path = self._get_path(session_id)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return []

    def save(self, session_id: str, messages: List[Message]) -> None:
        """保存会话历史（覆盖写入）"""
        path = self._get_path(session_id)
        try:
            # 临时文件写入 + rename 原子操作，防止写到一半断电文件损坏
            temp_path = f"{path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, path)
        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}")