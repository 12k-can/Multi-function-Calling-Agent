"""
🧠 多轮对话记忆系统 (ConversationMemory)

为 Agent 提供基于历史对话的上下文记忆能力。

核心特性：
  1. 消息持久化 — 存储用户消息、助手回复、工具调用记录
  2. 上下文窗口 — 自动裁剪过长的历史，保持 Token 在合理范围内
  3. 摘要记忆 — 总结历史对话，提取关键信息长期保存
  4. 结构化管理 — 支持按会话分组，方便切换话题

设计理念：
  - 基于消息列表（类似 ChatML 格式），与 LLM API 天然兼容
  - 自动管理 Token 预算，无需手动裁剪
  - 可插拔存储后端（内存 / 文件 / 数据库）
"""

import json
import logging
import os
import time
import threading
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable


# ─── 消息模型 ────────────────────────────────────────────────────────────────


@dataclass
class Message:
    """
    单条对话消息。
    
    Attributes:
        role: 角色 (system, user, assistant, tool)
        content: 消息内容
        tool_call_id: 工具调用 ID（仅 tool 角色）
        tool_name: 工具名称（仅 tool 角色）
        timestamp: 消息时间戳
        metadata: 附加元数据
    """
    role: str  # system, user, assistant, tool
    content: str
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_openai_format(self) -> Dict[str, Any]:
        """转换为 OpenAI Chat Completion 消息格式。"""
        msg: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
            msg["name"] = self.tool_name
        return msg

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(**data)

    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message role={self.role} content='{content_preview}'>"


# ─── Token 估算 ──────────────────────────────────────────────────────────────


def estimate_tokens(text: str) -> int:
    """估算文本的 Token 数量（中英文混合近似）。"""
    # 简单估算：中文约 1.5 token/字，英文约 0.25 token/字符
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars * 0.4) + 2


# ═══════════════════════════════════════════════════════════════════════════════
# ConversationMemory
# ═══════════════════════════════════════════════════════════════════════════════


class ConversationMemory:
    """
    多轮对话记忆。
    
    管理消息列表，提供自动裁剪、摘要提取、持久化功能。
    
    使用示例:
        memory = ConversationMemory(max_tokens=4000)
        memory.add_user_message("北京的天气怎么样？")
        memory.add_assistant_message("我来查一下。")
        # 获取用于 LLM 的消息列表
        messages = memory.get_messages()
    """

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        reserve_tokens: int = 1024,
        storage_path: Optional[str] = None,
    ):
        """
        初始化对话记忆。
        
        Args:
            system_prompt: 系统提示词。
            max_tokens: 最大 Token 预算（超出时自动裁剪历史）。
            reserve_tokens: 为后续对话保留的 Token 数（从 max_tokens 中扣除）。
            storage_path: 持久化文件路径（可选）。
        """
        self._messages: List[Message] = []
        self._max_tokens = max_tokens
        self._reserve_tokens = reserve_tokens
        self._storage_path = storage_path
        self._lock = threading.Lock()
        self._summary: Optional[str] = None
        self._session_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")

        if system_prompt:
            self.add_system_message(system_prompt)

        # 加载持久化数据
        if storage_path:
            self._load()

    # ── 属性 ─────────────────────────────────────────────────────────────────

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def token_count(self) -> int:
        return sum(estimate_tokens(m.content) for m in self._messages)

    @property
    def summary(self) -> Optional[str]:
        return self._summary

    # ── 添加消息 ─────────────────────────────────────────────────────────────

    def add_system_message(self, content: str) -> None:
        """添加系统消息。"""
        with self._lock:
            self._messages.append(Message(role="system", content=content))

    def add_user_message(self, content: str) -> None:
        """添加用户消息。"""
        with self._lock:
            self._messages.append(Message(role="user", content=content))
            self._trim_history()

    def add_assistant_message(self, content: str) -> None:
        """添加助手回复消息。"""
        with self._lock:
            self._messages.append(Message(role="assistant", content=content))
            self._save()

    def add_tool_message(
        self,
        content: str,
        tool_call_id: str,
        tool_name: str,
    ) -> None:
        """添加工具调用结果消息。"""
        with self._lock:
            self._messages.append(Message(
                role="tool",
                content=content,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
            ))
            self._save()

    def add_message(self, message: Message) -> None:
        """添加任意消息对象。"""
        with self._lock:
            self._messages.append(message)
            self._trim_history()
            self._save()

    # ── 获取消息 ─────────────────────────────────────────────────────────────

    def get_messages(
        self,
        include_system: bool = True,
        include_tool: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        获取格式化的消息列表（适用于 LLM API）。
        
        Args:
            include_system: 是否包含系统消息。
            include_tool: 是否包含工具消息。
        
        Returns:
            消息字典列表，格式兼容 OpenAI API。
        """
        with self._lock:
            messages = []
            for msg in self._messages:
                if not include_system and msg.role == "system":
                    continue
                if not include_tool and msg.role == "tool":
                    continue
                messages.append(msg.to_openai_format())
            return messages

    def get_raw_messages(self) -> List[Message]:
        """获取原始消息对象列表。"""
        with self._lock:
            return list(self._messages)

    def get_recent_messages(self, n: int = 5) -> List[Dict[str, Any]]:
        """获取最近 n 条消息。"""
        with self._lock:
            recent = self._messages[-n:] if n > 0 else []
            return [m.to_openai_format() for m in recent]

    # ── 历史管理 ─────────────────────────────────────────────────────────────

    def _trim_history(self) -> None:
        """
        自动裁剪历史消息。
        
        策略：
          1. 系统消息始终保留
          2. 保留最近的用户-助手对话
          3. 如果仍超出预算，生成摘要
        """
        available_tokens = self._max_tokens - self._reserve_tokens
        current_tokens = self.token_count

        if current_tokens <= available_tokens:
            return

        # 需要裁剪
        system_msgs = [m for m in self._messages if m.role == "system"]
        non_system = [m for m in self._messages if m.role != "system"]

        # 从最早的非系统消息开始移除，直到预算充足
        while non_system and self.token_count > available_tokens:
            removed = non_system.pop(0)
            self._messages.remove(removed)

        # 如果仍然超出，对系统消息也裁剪
        while self._messages and self.token_count > available_tokens:
            removed = self._messages.pop(0)
            if removed.role == "system" and not system_msgs:
                # 至少保留一条系统消息
                break

    def clear(self) -> None:
        """清空对话历史（保留系统消息）。"""
        with self._lock:
            system_msgs = [m for m in self._messages if m.role == "system"]
            self._messages = system_msgs
            self._summary = None
            self._save()

    def reset_session(self) -> None:
        """重置会话（清空所有消息）。"""
        with self._lock:
            self._messages = []
            self._summary = None
            self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._save()

    # ── 摘要记忆 ─────────────────────────────────────────────────────────────

    def update_summary(self, summary_func: Optional[Callable[[str], str]] = None) -> str:
        """
        生成或更新对话摘要。
        
        Args:
            summary_func: 摘要生成函数（接收对话文本，返回摘要）。
                         为 None 时使用内置的简单摘要。
        
        Returns:
            生成的摘要文本。
        """
        if summary_func:
            # 使用外部摘要函数（如 LLM 调用）
            conversation_text = self._get_conversation_text()
            self._summary = summary_func(conversation_text)
        else:
            # 内置简单摘要
            self._summary = self._simple_summarize()

        return self._summary or ""

    def _simple_summarize(self) -> str:
        """内置的简单摘要提取。"""
        total_msgs = len(self._messages)
        user_msgs = sum(1 for m in self._messages if m.role == "user")
        tool_calls = sum(1 for m in self._messages if m.role == "tool")

        # 提取关键信息（工具调用和重要回复）
        key_points = []
        for msg in self._messages[-20:]:  # 只看最近 20 条
            if msg.role == "tool" and msg.tool_name:
                key_points.append(f"调用了工具: {msg.tool_name}")
            if msg.role == "assistant" and len(msg.content) > 10:
                # 提取可能的结论
                lines = msg.content.strip().split("\n")
                for line in lines:
                    line = line.strip()
                    if any(kw in line for kw in ["结果", "答案", "结论", "因此", "所以"]):
                        key_points.append(line[:80])
                        break

        summary_parts = [
            f"会话 {self._session_id} 摘要",
            f"共 {total_msgs} 条消息（用户 {user_msgs} 条）",
        ]
        if key_points:
            summary_parts.append("关键信息:")
            summary_parts.extend(f"  • {kp}" for kp in key_points[-5:])

        return "\n".join(summary_parts)

    def _get_conversation_text(self) -> str:
        """将对话历史转换为纯文本（用于摘要生成）。"""
        parts = []
        for msg in self._messages:
            if msg.role == "system":
                continue
            if msg.role == "tool":
                parts.append(f"[工具 {msg.tool_name}]: {msg.content[:200]}")
            else:
                parts.append(f"[{msg.role}]: {msg.content[:200]}")
        return "\n\n".join(parts)

    def get_summary_context(self) -> Optional[str]:
        """
        获取摘要上下文。
        
        当对话历史被裁剪后，摘要可作为系统提示的一部分保留关键信息。
        """
        if self._summary:
            return (
                "以下是对前面对话的摘要：\n"
                f"{self._summary}\n"
                "（注意：历史消息已被裁剪以节省空间，以上是保留的关键信息）"
            )
        return None

    # ── 持久化 ───────────────────────────────────────────────────────────────

    def _save(self) -> None:
        """保存到磁盘。"""
        if not self._storage_path:
            return
        try:
            data = {
                "session_id": self._session_id,
                "summary": self._summary,
                "messages": [m.to_dict() for m in self._messages],
            }
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger = logging.getLogger("agent.memory")
            logger.warning(f"记忆持久化失败: {e}")

    def _load(self) -> None:
        """从磁盘加载。"""
        if not self._storage_path or not os.path.exists(self._storage_path):
            return
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._session_id = data.get("session_id", self._session_id)
            self._summary = data.get("summary")
            for msg_data in data.get("messages", []):
                self._messages.append(Message.from_dict(msg_data))
        except Exception as e:
            logger = logging.getLogger("agent.memory")
            logger.warning(f"记忆加载失败: {e}")

    # ── 对话上下文构建 ───────────────────────────────────────────────────────

    def build_context(self, user_message: str) -> List[Dict[str, Any]]:
        """
        构建完整的 LLM 上下文（系统提示 + 摘要 + 历史 + 当前消息）。
        
        Args:
            user_message: 当前用户消息。
        
        Returns:
            OpenAI 格式的消息列表。
        """
        messages = self.get_messages()

        # 如果有摘要且历史被裁剪过，将摘要注入
        summary = self.get_summary_context()
        if summary and len(self._messages) > 5:
            # 插入到系统消息之后
            insert_idx = 0
            for i, m in enumerate(messages):
                if m["role"] == "system":
                    insert_idx = i + 1
            messages.insert(insert_idx, {"role": "system", "content": summary})

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        return messages

    # ── 展示 ─────────────────────────────────────────────────────────────────

    def print_history(self, max_messages: int = 20) -> str:
        """打印对话历史。"""
        lines = [
            f"🧠 对话历史 (会话: {self._session_id})",
            "=" * 50,
        ]
        for msg in self._messages[-max_messages:]:
            role_icon = {
                "system": "⚙️",
                "user": "👤",
                "assistant": "🤖",
                "tool": "🔧",
            }.get(msg.role, "📝")
            content = msg.content[:150].replace("\n", " ")
            if msg.role == "tool":
                lines.append(f"  {role_icon} [{msg.tool_name}] {content}")
            else:
                lines.append(f"  {role_icon} [{msg.role}] {content}")
            lines.append("")

        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._messages)

    def __repr__(self) -> str:
        return (
            f"<ConversationMemory session={self._session_id} "
            f"messages={len(self._messages)} "
            f"tokens={self.token_count}/{self._max_tokens}>"
        )


# (imports are at the top of the file)
