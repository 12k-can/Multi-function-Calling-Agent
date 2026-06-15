"""
🤖 工具调用型 Agent 系统

一个基于 Function Calling 的多功能 AI 助手框架。
支持：工具注册、参数解析、错误重试、结果返回、多轮记忆。

核心组件：
- core.Agent          — 主引擎，协调对话与工具调用
- tools.registry      — 工具注册中心
- memory.ConversationMemory — 多轮对话记忆
- retry.RetryHandler  — 智能错误重试机制
"""

from .core import Agent, AgentConfig
from .memory import ConversationMemory
from .retry import RetryHandler

__all__ = ["Agent", "AgentConfig", "ConversationMemory", "RetryHandler"]
__version__ = "1.0.0"
