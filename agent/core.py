"""
🤖 核心 Agent 引擎 (Agent)

协调 LLM 与工具调用，实现完整的 Function Calling 流程：

  用户输入 → 构建上下文 → LLM 推理 → 工具调用 → 结果返回 → LLM 总结 → 输出

核心特性：
  - 支持 OpenAI Function Calling API 和本地模拟模式
  - 自动工具选择与参数注入
  - 智能错误重试（与 RetryHandler 集成）
  - 多轮对话记忆（与 ConversationMemory 集成）
  - 可扩展的工具注册中心
"""

import json
import logging
import time
import traceback
import uuid
from typing import Any, Dict, List, Optional, Callable, Union, Generator

from .tools.registry import ToolRegistry, ToolNotFoundError
from .memory import ConversationMemory, Message
from .retry import RetryHandler, RetryConfig

logger = logging.getLogger("agent.core")


# ═══════════════════════════════════════════════════════════════════════════════
# Agent 配置
# ═══════════════════════════════════════════════════════════════════════════════


class AgentConfig:
    """
    Agent 配置。
    
    Attributes:
        model: LLM 模型名称。
        api_key: API 密钥。
        api_base: API 基础 URL。
        max_tokens: 最大 Token 数。
        temperature: 温度参数。
        max_tool_rounds: 单轮用户输入允许的最大工具调用轮次。
        use_local_mode: 是否使用本地模拟模式（无需 API key）。
        memory_max_tokens: 记忆系统的 Token 预算。
        tool_retry_count: 工具调用的最大重试次数。
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        max_tool_rounds: int = 10,
        use_local_mode: bool = True,
        memory_max_tokens: int = 4096,
        tool_retry_count: int = 2,
    ):
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_tool_rounds = max_tool_rounds
        self.use_local_mode = use_local_mode
        self.memory_max_tokens = memory_max_tokens
        self.tool_retry_count = tool_retry_count

    def __repr__(self) -> str:
        mode = "本地模式" if self.use_local_mode else f"API模式({self.model})"
        return f"<AgentConfig mode={mode} tools_retry={self.tool_retry_count}>"


# ─── 默认系统提示词 ──────────────────────────────────────────────────────────

DEFAULT_SYSTEM_PROMPT = """你是 AI Agent，一个智能助手，可以通过调用各种工具来完成用户的任务。

## 核心能力
1. **工具调用** — 当用户提出需求时，判断是否需要使用工具，选择合适的工具并传入正确的参数
2. **信息整合** — 将工具返回的结果以清晰、友好的方式呈现给用户
3. **多轮对话** — 记住对话上下文，连续完成任务
4. **主动询问** — 当信息不充分时，主动向用户确认

## 使用规则
- 当需要查询实时信息或执行计算时，优先使用工具
- 每次调用工具后，根据工具返回的结果给用户完整的回答
- 如果工具调用失败，尝试换一种方式或告知用户
- 对于简单的问候和闲聊，直接回复即可

## 可用工具
在对话中你会看到可用工具列表。选择合适的工具来完成任务。"""


# ═══════════════════════════════════════════════════════════════════════════════
# Agent
# ═══════════════════════════════════════════════════════════════════════════════


class Agent:
    """
    工具调用型 Agent 主引擎。
    
    协调 LLM、工具系统、记忆系统、重试机制，完成端到端的功能调用流程。
    
    使用示例:
        agent = Agent()
        agent.register_builtin_tools()
        
        # 单轮执行
        result = agent.execute("北京的天气怎么样？")
        print(result)
        
        # 多轮对话（自动记忆上下文）
        result1 = agent.execute("帮我算 2+3")
        result2 = agent.execute("再乘以 4")  # 自动引用上一步结果
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        registry: Optional[ToolRegistry] = None,
        memory: Optional[ConversationMemory] = None,
        system_prompt: Optional[str] = None,
    ):
        """
        初始化 Agent。
        
        Args:
            config: Agent 配置，默认使用本地模式。
            registry: 工具注册中心，默认新建。
            memory: 对话记忆，默认新建。
            system_prompt: 系统提示词，使用默认值。
        """
        self.config = config or AgentConfig()
        self.registry = registry or ToolRegistry()
        self.memory = memory or ConversationMemory(
            system_prompt=system_prompt or DEFAULT_SYSTEM_PROMPT,
            max_tokens=self.config.memory_max_tokens,
        )
        self._last_tool_results: List[Dict[str, Any]] = []
        self._tool_loop_active: bool = False  # 当前 execute 循环中是否刚执行过工具

    # ── 工具注册 ─────────────────────────────────────────────────────────────

    def register_builtin_tools(self, workspace_dir: str = ".") -> int:
        """
        注册所有内置工具。
        
        Args:
            workspace_dir: 文件工具的工作目录。
        
        Returns:
            注册的工具数量。
        """
        from .tools.weather import register_weather_tools
        from .tools.math_tools import register_math_tools
        from .tools.translation import register_translation_tools
        from .tools.file_tools import register_file_tools
        from .tools.database import register_database_tools

        register_weather_tools(self.registry)
        register_math_tools(self.registry)
        register_translation_tools(self.registry)
        register_file_tools(self.registry, workspace_dir=workspace_dir)
        register_database_tools(self.registry)

        count = len(self.registry)
        logger.info(f"已注册 {count} 个内置工具")
        return count

    def register_tool(
        self,
        func: Optional[Callable] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Any:
        """
        注册自定义工具（装饰器或直接调用）。
        
        使用示例:
            @agent.register_tool(name="my_tool", description="...")
            def my_tool(param1: str) -> str:
                ...
        """
        if func:
            self.registry.register_tool(func, name=name, description=description)
            return func
        # 返回装饰器
        return self.registry.register(name=name, description=description)

    # ── 核心执行流程 ─────────────────────────────────────────────────────────

    def execute(
        self,
        user_message: str,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        执行一次完整的 Agent 推理流程。
        
        流程:
          1. 用户输入 → 2. 构建上下文 → 3. LLM 推理 → 
          4. 工具调用 → 5. 结果返回 → 6. LLM 总结 → 7. 输出
        
        Args:
            user_message: 用户输入的消息。
            verbose: 是否返回详细过程信息。
        
        Returns:
            {
                "response": str,          # 最终回复
                "tool_calls": [...],       # 工具调用记录
                "rounds": int,             # 推理轮次
                "error": str | None,       # 错误信息
            }
        """
        self._last_tool_results = []

        # 1. 保存用户消息到记忆
        self.memory.add_user_message(user_message)

        # 2. 构建上下文
        messages = self.memory.build_context(user_message)

        # 3. 获取工具 schema
        tools = self.registry.get_all_schemas() if self.registry.list_tools() else None

        # 4. 主循环
        tool_calls_log = []
        rounds = 0
        final_response = ""
        final_error = None
        self._tool_loop_active = False

        try:
            while rounds < self.config.max_tool_rounds:
                rounds += 1

                # ── 调用 LLM ──
                llm_response = self._call_llm(
                    messages=messages,
                    tools=tools,
                )

                if llm_response is None:
                    final_error = "LLM 调用失败"
                    break

                assistant_content = llm_response.get("content", "")
                tool_calls = llm_response.get("tool_calls", [])

                # 如果没有工具调用 → 结束
                if not tool_calls:
                    final_response = assistant_content or "好的，已处理完成。"
                    # 保存到记忆
                    self.memory.add_assistant_message(final_response)
                    self._tool_loop_active = False
                    break

                # ── 有工具调用 → 执行工具 ──
                self._tool_loop_active = True
                # 先添加助手消息（含工具调用请求）
                self.memory.add_assistant_message(assistant_content or "")

                for tc in tool_calls:
                    tool_name = tc.get("name", "")
                    tool_args = tc.get("arguments", {})
                    tool_call_id = tc.get("id", str(uuid.uuid4()))

                    # 执行工具（带重试）
                    tool_result = self.registry.call_tool(
                        name=tool_name,
                        arguments=tool_args,
                        max_retries=self.config.tool_retry_count,
                    )

                    # 记录
                    tool_calls_log.append({
                        "round": rounds,
                        "tool": tool_name,
                        "arguments": tool_args,
                        "success": tool_result["success"],
                        "error": tool_result["error"],
                    })

                    # 格式化结果
                    if tool_result["success"]:
                        formatted_result = str(tool_result["result"])
                    else:
                        formatted_result = f"工具执行失败: {tool_result['error']}"

                    # 添加工具结果到记忆和消息列表
                    self.memory.add_tool_message(
                        content=formatted_result,
                        tool_call_id=tool_call_id,
                        tool_name=tool_name,
                    )

                    # 将工具结果追加到当前 LLM 上下文
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": formatted_result,
                    })

                    self._last_tool_results.append(tool_result)

                # 继续下一轮（LLM 根据工具结果生成最终回复或调用更多工具）
                continue

            # ── 如果超出最大轮次 ──
            if rounds >= self.config.max_tool_rounds and not final_response:
                final_response = f"已执行 {rounds} 轮工具调用，任务可能未完全完成。如需继续，请告知。"
                self.memory.add_assistant_message(final_response)

        except Exception as e:
            final_error = f"Agent 执行异常: {type(e).__name__}: {e}"
            logger.error(final_error)
            final_response = f"抱歉，执行过程中出现错误：{e}"
            self.memory.add_assistant_message(final_response)

        # ── 整理结果 ──
        result = {
            "response": final_response,
            "tool_calls": tool_calls_log,
            "rounds": rounds,
            "error": final_error,
        }

        if verbose:
            result["memory_summary"] = self.memory.summary if self.memory.summary else None
            result["message_count"] = self.memory.message_count

        return result

    # ── LLM 调用 ─────────────────────────────────────────────────────────────

    def _call_llm(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        调用 LLM。
        
        支持两种模式：
          - API 模式：使用 OpenAI API
          - 本地模式：使用规则引擎模拟 Function Calling
        """
        if self.config.use_local_mode:
            return self._local_llm_call(messages, tools)
        else:
            return self._api_llm_call(messages, tools)

    def _api_llm_call(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
    ) -> Optional[Dict[str, Any]]:
        """使用 OpenAI API 调用 LLM。"""
        try:
            from openai import OpenAI

            client_kwargs = {"api_key": self.config.api_key}
            if self.config.api_base:
                client_kwargs["base_url"] = self.config.api_base

            client = OpenAI(**client_kwargs)

            kwargs = {
                "model": self.config.model,
                "messages": messages,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            msg = choice.message

            result: Dict[str, Any] = {
                "content": msg.content or "",
                "tool_calls": [],
            }

            if msg.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments),
                    }
                    for tc in msg.tool_calls
                ]

            return result

        except Exception as e:
            logger.error(f"API LLM 调用失败: {e}")
            # 如果 API 失败，回退到本地模式
            logger.info("回退到本地模式...")
            return self._local_llm_call(messages, tools)

    def _local_llm_call(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        本地 LLM 调用（模拟 Function Calling）。
        
        处理策略：
          1. 如果当前 execute 循环中刚执行过工具调用（_tool_loop_active=True），
             则生成最终回复而非再次调用工具。
          2. 否则对用户输入进行意图识别，选择合适的工具。
        """
        # ── 检查是否刚执行过工具调用 ──
        if self._tool_loop_active:
            return self._generate_tool_summary(messages)

        # ── 提取最后一条用户消息 ──
        user_msg = ""
        for m in reversed(messages):
            if m["role"] == "user":
                user_msg = m["content"]
                break

        if not user_msg:
            return {"content": "您好！请问有什么可以帮您的？", "tool_calls": []}

        # 检查是否为问候/闲聊（精确匹配，避免误触发）
        greetings = ["你好", "您好", "hello", "hi", "hey", "早上好", "晚上好", "下午好"]
        user_msg_lower = user_msg.lower().strip()
        is_greeting = user_msg_lower in greetings or \
                      any(user_msg_lower == g or user_msg_lower.startswith(g + "！") or 
                          user_msg_lower.startswith(g + "，") or user_msg_lower.startswith(g + ",")
                          for g in greetings)
        if is_greeting:
            return {
                "content": "你好！我是 AI Agent，可以帮你完成以下任务：\n\n"
                           "🌤 **查天气** — 告诉我城市名\n"
                           "🔢 **算数学** — 输入表达式或方程\n"
                           "🌐 **翻译** — 提供文本和语言\n"
                           "📄 **生成文件** — 告诉我内容和格式\n"
                           "🗄 **查数据库** — 执行 SQL 查询\n"
                           "📊 **生成报告** — 提供数据和标题\n\n"
                           "有什么需要帮忙的吗？",
                "tool_calls": [],
            }

        if not tools:
            return {
                "content": self._generate_direct_reply(user_msg),
                "tool_calls": [],
            }

        # ── 意图识别与工具选择 ──
        tool_decisions = self._detect_intent(user_msg, tools)

        if not tool_decisions:
            return {
                "content": self._generate_direct_reply(user_msg),
                "tool_calls": [],
            }

        return {
            "content": f"我来处理你的请求。将调用 {len(tool_decisions)} 个工具...",
            "tool_calls": tool_decisions,
        }

    def _generate_tool_summary(
        self,
        messages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        根据工具执行结果生成最终回复。
        
        提取最近一次工具调用的结果，整理为友好的回复文本。
        """
        # 收集最近的所有工具结果
        tool_results = []
        for m in reversed(messages):
            if m["role"] == "tool":
                tool_results.append(m["content"])
            if m["role"] == "user":
                break

        tool_results.reverse()

        if not tool_results:
            return {
                "content": "好的，已经处理完成。还有什么需要帮忙的吗？",
                "tool_calls": [],
            }

        # 整合所有结果
        combined = "\n\n".join(tool_results)

        # 尝试提取结构化信息，生成更友好的回复
        lines = combined.split("\n")

        # 检测是否是天气结果
        if any("天气" in line for line in lines[:3]):
            return {
                "content": f"查询完成！以下是你需要的天气信息：\n\n{combined}\n\n还有其他城市需要查询吗？",
                "tool_calls": [],
            }

        # 检测是否是数学结果
        if any(line.strip().startswith("=") for line in lines):
            result_val = ""
            for line in lines:
                if line.strip().startswith("="):
                    result_val = line.strip()
                    break
            return {
                "content": f"计算结果：\n\n{result_val}\n\n还需要计算其他内容吗？",
                "tool_calls": [],
            }

        # 检测是否是单位换算结果
        if any("=" in line and ("公里" in line or "英里" in line or "米" in line) for line in lines[:3]):
            return {
                "content": f"换算结果如下：\n\n{combined}\n\n还需要其他单位换算吗？",
                "tool_calls": [],
            }

        # 检测是否是翻译结果
        if any("翻译" in line or "Translation" in line for line in lines[:3]):
            return {
                "content": f"{combined}\n\n还有其他需要翻译的内容吗？",
                "tool_calls": [],
            }

        # 检测是否是数据库结果
        if any("查询结果" in line or "表" in line for line in lines[:5]):
            return {
                "content": f"数据库查询完成：\n\n{combined}\n\n需要执行其他查询吗？",
                "tool_calls": [],
            }

        # 检测是否是文件结果
        if any("文件" in line or "报告" in line or "CSV" in line for line in lines[:3]):
            return {
                "content": f"操作成功！\n\n{combined}\n\n还需要生成其他文件吗？",
                "tool_calls": [],
            }

        # 默认回复
        return {
            "content": f"处理完成，以下是结果：\n\n{combined}\n\n还有其他需要帮忙的吗？",
            "tool_calls": [],
        }

    def _detect_intent(
        self,
        user_msg: str,
        tools: List[Dict],
    ) -> List[Dict[str, Any]]:
        """
        检测用户意图并选择工具。
        
        通过关键词匹配和规则判断用户想要调用哪个工具。
        当多个工具匹配时，通过优先级和互斥规则去重。
        """
        msg_lower = user_msg.lower()
        candidates = []

        for tool_schema in tools:
            func_info = tool_schema.get("function", {})
            name = func_info.get("name", "")
            desc = func_info.get("description", "")
            params = func_info.get("parameters", {})

            match_score = self._match_tool_intent(msg_lower, name, desc)

            if match_score > 0:
                args = self._extract_arguments(user_msg, params)
                if args is not None:
                    candidates.append({
                        "id": str(uuid.uuid4()),
                        "name": name,
                        "arguments": args,
                        "score": match_score,
                    })

        # ── 互斥规则处理 ──
        # 规则：如果 convert_units 和 calculate 都匹配，只保留 convert_units
        candidate_names = {c["name"] for c in candidates}
        if "convert_units" in candidate_names and "calculate" in candidate_names:
            candidates = [c for c in candidates if c["name"] != "calculate"]

        # 规则：如果 translate 匹配，不允许同时匹配天气
        if "translate" in candidate_names and "get_weather" in candidate_names:
            candidates = [c for c in candidates if c["name"] != "get_weather"]

        # 按分数降序排列，只取最高分的工具（避免多个同类工具同时调用）
        if candidates:
            max_score = max(c["score"] for c in candidates)
            candidates = [c for c in candidates if c["score"] >= max_score * 0.8]

        # 移除 score 字段，保持返回格式一致
        for c in candidates:
            del c["score"]

        return candidates

    def _match_tool_intent(self, msg: str, tool_name: str, tool_desc: str) -> float:
        """
        计算用户消息与工具的匹配度。
        
        Returns:
            匹配分数 (0-1)，>0 表示匹配。
        """
        score = 0.0

        # 关键词映射
        intent_keywords = {
            "get_weather": ["天气", "温度", "下雨", "刮风", "气温", "weather", "temperature", "rain", "℃", "°c"],
            "get_weather_forecast": ["预报", "未来几天", "天气预测", "forecast"],
            "calculate": ["计算", "等于", "加", "减", "乘", "除", "平方", "开方",
                          "算一下", "+", "-", "*", "/", "**", "%",
                          "calculate", "sqrt", "sin", "cos", "tan", "log",
                          "等于多少"],
            "solve_equation": ["解方程", "求解", "方程", "方程式", "solve", "equation"],
            "convert_units": ["换算", "单位转换", "convert", "等于多少", "换成", "转成"],
            "translate": ["翻译", "translate", "用中文说", "用英文说", "翻成", "译成"],
            "detect_language": ["检测语言", "这是什么语言", "language"],
            "create_text_file": ["创建文件", "生成文件", "写文件", "保存为", "create file",
                                 "生成一个", "写一个"],
            "generate_report": ["生成报告", "报告", "报表", "report", "总结报告"],
            "generate_csv": ["csv", "表格数据", "生成csv", "导出csv"],
            "execute_sql": ["查询", "查一下", "sql", "数据库", "select", "数据", "员工", "哪些", "是谁"],
            "show_tables": ["有什么表", "有哪些表", "表结构", "数据库结构", "show tables"],
            "create_sample_data": ["示例数据", "测试数据", "创建数据", "sample data"],
        }

        keywords = intent_keywords.get(tool_name, [])
        for kw in keywords:
            if kw in msg:
                score += 1.0 / len(keywords)

        # 如果描述中有匹配词也加分
        desc_keywords = tool_desc.split("、") if "、" in tool_desc else tool_desc.split()
        for dkw in desc_keywords:
            if dkw[:2] in msg:
                score += 0.1

        # 翻译工具特殊处理：如果消息中含非中文字符且含"翻译"
        if tool_name == "translate":
            if "翻译" in msg:
                score = max(score, 0.6)
            has_foreign = any(ord(c) > 127 for c in msg)
            if has_foreign and ("中文" in msg or "英语" in msg):
                score = max(score, 0.7)

        return score

    def _extract_arguments(
        self,
        user_msg: str,
        param_schema: Dict,
    ) -> Optional[Dict[str, Any]]:
        """
        从用户消息中提取工具参数。
        
        使用规则 + 简单模式匹配提取参数值。
        """
        args = {}
        properties = param_schema.get("properties", {})
        required = param_schema.get("required", [])

        for param_name, param_info in properties.items():
            value = self._extract_param_value(user_msg, param_name, param_info)
            if value is not None:
                args[param_name] = value

        # 检查必需参数
        for req in required:
            if req not in args:
                return None  # 缺少必需参数，放弃此次工具调用

        return args

    def _extract_param_value(
        self,
        msg: str,
        param_name: str,
        param_info: Dict,
    ) -> Any:
        """
        从消息中提取单个参数值。
        
        针对不同参数名使用不同提取策略。
        """
        param_type = param_info.get("type", "string")

        # ── 城市参数 ──
        if param_name == "city":
            # 优先尝试直接匹配已知城市
            from .tools.weather import _CITY_WEATHER
            matched_city = None
            for city in _CITY_WEATHER:
                if city in msg:
                    # 选最长的匹配（避免 "北京" 匹配到 "南京" 的问题）
                    if matched_city is None or len(city) > len(matched_city):
                        matched_city = city
            if matched_city:
                return matched_city
            # 关键词提取
            for keyword in ["查询", "天气", "预报", "temperature", "weather", "在"]:
                parts = msg.split(keyword)
                if len(parts) > 1:
                    after = parts[-1].strip()
                    # 去除"的"等助词
                    after = after.lstrip("的").strip()
                    first_word = after.split()[0].strip("，。！？,.;:!?的")
                    if first_word and len(first_word) <= 10:
                        return first_word
            # 尝试取消息中的地名（常见的 xx市/xx城 模式）
            import re
            city_pattern = re.findall(r'([\u4e00-\u9fff]{2,6}(?:市|城))', msg)
            if city_pattern:
                return city_pattern[0].rstrip("市城")
            # 再尝试：取任意2字中文字词（可能是城市）
            words = re.findall(r'[\u4e00-\u9fff]{2,4}', msg)
            if words:
                return words[0]

        # ── 表达式参数 ──
        if param_name == "expression":
            # 提取数学表达式
            # 去除常见的引导词
            for prefix in ["计算", "算一下", "等于多少", "帮我算", "是多少"]:
                if prefix in msg:
                    expr = msg.split(prefix, 1)[-1].strip()
                    expr = expr.split("。")[0].split("，")[0].split("!")[0]
                    if expr:
                        # 中文字符转符号
                        expr = expr.replace("×", "*").replace("÷", "/").replace("＝", "=")
                        return expr
            # 直接匹配数学表达式
            import re
            math_pattern = r'[\d\s\+\-\*\/\(\)\%\.\^\,]+'
            match = re.search(math_pattern, msg)
            if match:
                expr = match.group().strip()
                if expr:
                    return expr

        # ── 方程参数 ──
        if param_name == "equation":
            for prefix in ["解方程", "求解", "帮我解"]:
                if prefix in msg:
                    eq = msg.split(prefix, 1)[-1].strip().split("。")[0]
                    return eq

        # ── 单位换算参数 ──
        if param_name == "from_unit":
            # 常见单位
            units = ["米", "千米", "公里", "厘米", "毫米", "英寸", "英尺", "千克", "公斤",
                     "克", "毫克", "磅", "摄氏度", "华氏度", "m", "km", "cm", "mm", "kg", "g",
                     "lb", "°c", "°f", "celsius", "fahrenheit"]
            for unit in units:
                if unit in msg:
                    return unit

        if param_name == "to_unit":
            for kw in ["换算成", "转换成", "转成", "换成", "等于多少", "是多少", "to", "为"]:
                if kw in msg:
                    parts = msg.split(kw, 1)
                    if len(parts) > 1:
                        remaining = parts[1]
                        units = ["英里", "米", "千米", "公里", "厘米", "毫米", "英寸", "英尺",
                                 "千克", "公斤", "克", "毫克", "磅", "摄氏度", "华氏度",
                                 "m", "km", "cm", "mm", "kg", "g", "lb", "°c", "°f",
                                 "mile", "miles", "yard", "inch"]
                        for unit in units:
                            if unit in remaining:
                                return unit
                        # 如果没找到具体单位，尝试取第一个有意义的词
                        words = remaining.strip().split()[0].strip("，。！？,.;:!?的")
                        if words and len(words) <= 6:
                            return words
            return "米"  # 默认

        # ── 文本参数 ──
        if param_name == "text":
            # 提取要翻译/处理的文本
            for prefix in ["翻译", "把", "将"]:
                if prefix in msg:
                    after = msg.split(prefix, 1)[-1].strip()
                    for suffix in ["翻译成", "翻成", "译成", "用", "成"]:
                        if suffix in after:
                            after = after.split(suffix, 1)[0].strip()
                    # 去除尾部残留的语言名称
                    for lang_word in ["中文", "英文", "英语", "日语", "法语", "德语", "韩语", "西班牙语"]:
                        if after.endswith(lang_word):
                            after = after[:-len(lang_word)].strip()
                        if after.startswith(lang_word):
                            after = after[len(lang_word):].strip()
                    if after:
                        return after

        if param_name == "target_lang":
            lang_map = {
                "中文": ["中文", "汉语", "chinese", "zh"],
                "英语": ["英语", "英文", "english", "en"],
                "日语": ["日语", "日文", "japanese", "ja"],
                "韩语": ["韩语", "韩文", "korean", "ko"],
                "法语": ["法语", "法文", "french", "fr"],
                "德语": ["德语", "德文", "german", "de"],
                "西班牙语": ["西班牙语", "spanish", "es"],
            }
            for target_lang, keywords in lang_map.items():
                for kw in keywords:
                    if kw in msg:
                        return target_lang
            # 如果消息含"翻译成"后面跟语言
            for prefix in ["翻译成", "翻成", "译成", "用", "成"]:
                if prefix in msg:
                    after = msg.split(prefix, 1)[-1].strip().split("说")[0].strip()
                    if after:
                        return after

        # ── 文件名参数 ──
        if param_name == "filename":
            for prefix in ["保存为", "文件名为", "命名为", "叫"]:
                if prefix in msg:
                    name = msg.split(prefix, 1)[-1].strip().split()[0].strip("，。！？,.;:!")
                    if name:
                        return name

        # ── SQL 参数 ──
        if param_name == "query":
            # 提取 SQL
            sql_keywords = ["SELECT", "select", "SELECT ", "select "]
            for kw in sql_keywords:
                if kw in msg:
                    idx = msg.index(kw)
                    sql = msg[idx:].strip()
                    # 去除尾部非 SQL 内容
                    for terminator in ["。", "！", "？", "!", "?", ";"]:
                        if terminator in sql:
                            sql = sql.split(terminator)[0]
                    return sql
            # 自然语言转 SQL
            if "所有员工" in msg:
                return "SELECT * FROM employees;"
            if "所有产品" in msg or "商品" in msg:
                return "SELECT * FROM products;"
            if "技术部" in msg:
                return "SELECT * FROM employees WHERE department = '技术部';"
            if "员工" in msg and ("工资" in msg or "薪资" in msg or "薪水" in msg or "salary" in msg.lower()):
                return "SELECT name, department, salary FROM employees ORDER BY salary DESC;"
            if "员工" in msg and ("部门" in msg or "department" in msg.lower()):
                return "SELECT department, COUNT(*) as count FROM employees GROUP BY department;"
            if "员工" in msg or "人员" in msg:
                return "SELECT * FROM employees;"
            if "产品" in msg and ("价格" in msg or "便宜" in msg or "贵" in msg):
                return "SELECT * FROM products ORDER BY price;"
            if "产品" in msg:
                return "SELECT * FROM products;"

        # ── 数值参数 ──
        if param_type in ("number", "integer"):
            import re
            numbers = re.findall(r'-?\d+\.?\d*', msg)
            if param_name == "days":
                for kw in ["未来", "接下来"]:
                    if kw in msg:
                        after = msg.split(kw, 1)[-1] if kw in msg else msg
                        nums = re.findall(r'\d+', after)
                        if nums:
                            return int(nums[0])
            if numbers:
                if param_type == "integer":
                    return int(float(numbers[0]))
                return float(numbers[0])

        # ── 布尔参数 ──
        if param_type == "boolean":
            return True  # 默认

        # ── 标题/描述参数 ──
        if param_name == "title":
            for prefix in ["标题为", "标题叫", "关于", "报告标题"]:
                if prefix in msg:
                    after = msg.split(prefix, 1)[-1].strip().split("。")[0]
                    if after:
                        return after
            # 取消息中第一个引号内容
            import re
            quoted = re.findall(r'[""](.+?)[""]', msg)
            if quoted:
                return quoted[0]
            # 从"报告"前面提取标题（"XXX报告"）
            if "报告" in msg:
                parts = msg.split("报告", 1)
                before = parts[0].strip()
                for skip in ["生成", "写", "创建", "一份", "一个", "的", "帮我"]:
                    before = before.replace(skip, "")
                before = before.strip()
                if before:
                    return before
                # 如果报告前没有内容，取"数据"后的内容
                if "数据" in msg:
                    data_part = msg.split("数据", 1)[1].strip()
                    # 取逗号前的部分
                    if "，" in data_part:
                        title = data_part.split("，", 1)[0].strip()
                        if title:
                            return title
                    if "," in data_part:
                        title = data_part.split(",", 1)[0].strip()
                        if title:
                            return title
            return "数据报告"

        if param_name == "data_json":
            import re
            # 1. 尝试提取方括号数组
            array_match = re.search(r'(\[.*?\])', msg, re.DOTALL)
            if array_match:
                json_str = array_match.group(1)
                # 验证是否为合法 JSON
                try:
                    import json as json_mod
                    json_mod.loads(json_str)
                    return json_str
                except json_mod.JSONDecodeError:
                    pass
            # 2. 尝试提取花括号对象
            json_match = re.search(r'(\{.*\})', msg, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                try:
                    import json as json_mod
                    json_mod.loads(json_str)
                    return json_str
                except json_mod.JSONDecodeError:
                    pass
            # 3. 如果提取到的是逗号分隔的对象（缺少[]），自动包装
            obj_match = re.findall(r'\{[^}]+,[^}]+\}', msg)
            if obj_match and len(obj_match) > 1:
                return "[" + ", ".join(obj_match) + "]"

        # ── content / description 参数 ──
        if param_name in ("content", "description"):
            # 取用户消息中去除引导词后的部分
            for prefix in ["内容是", "内容为", "写道", "内容："]:
                if prefix in msg:
                    after = msg.split(prefix, 1)[-1].strip()
                    if after:
                        return after

        # 默认返回字符串参数
        if param_type == "string" and param_name not in ("expression", "equation"):
            pass  # 不自动填充

        return None

    def _generate_direct_reply(self, user_msg: str) -> str:
        """对不需要工具调用的消息直接生成回复。"""
        msg_lower = user_msg.lower()

        if any(q in msg_lower for q in ["你是谁", "你叫什么", "who are you"]):
            return "我是 AI Agent，一个基于 Function Calling 的智能助手，可以帮你查天气、算数学、翻译、生成文件、查询数据库等。有什么需要帮忙的吗？"

        if any(c in msg_lower for c in ["谢谢", "thank", "thanks", "多谢"]):
            return "不客气！有其他需要帮忙的随时告诉我 😊"

        if any(q in msg_lower for q in ["你能做什么", "你会什么", "功能", "能力", "help", "capabilities"]):
            return (
                "我可以帮你完成以下任务：\n\n"
                "🌤 **查天气** — 告诉我城市名即可\n"
                "🔢 **算数学** — 支持加减乘除、平方根、三角函数、解方程、单位换算\n"
                "🌐 **翻译** — 支持多语言互译，自动检测语言\n"
                "📄 **生成文件** — 创建文本文件、Markdown 报告、CSV 数据\n"
                "🗄 **查数据库** — 执行 SQL 查询，探索数据\n\n"
                "试试对我说：\n"
                "- \"北京天气怎么样？\"\n"
                "- \"计算 25 * 48\"\n"
                "- \"翻译 Hello world 成中文\"\n"
                "- \"生成一份员工数据报告\"\n"
                "- \"查询数据库有哪些表\""
            )

        if any(f in msg_lower for f in ["再见", "拜拜", "goodbye", "bye"]):
            return "再见！期待下次为你服务 👋"

        # 默认回复
        return (
            f"收到你的消息了。如果你需要帮助，可以告诉我具体想做什么，"
            f"比如查天气、算数学、翻译文本、生成文件或查询数据库等。"
        )

    # ── 对话管理 ─────────────────────────────────────────────────────────────

    def clear_memory(self) -> None:
        """清空对话历史。"""
        self.memory.clear()
        self._last_tool_results = []

    def reset(self) -> None:
        """重置 Agent 状态。"""
        self.memory.reset_session()
        self._last_tool_results = []

    def get_conversation_summary(self) -> str:
        """获取对话摘要。"""
        return self.memory.print_history()

    # ── 信息查询 ─────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """获取 Agent 状态信息。"""
        return {
            "mode": "local" if self.config.use_local_mode else f"api({self.config.model})",
            "tools": len(self.registry),
            "tools_list": self.registry.list_tools(),
            "messages": self.memory.message_count,
            "tokens": self.memory.token_count,
            "session": self.memory.session_id,
        }

    def get_tool_summary(self) -> str:
        """获取工具注册摘要。"""
        return self.registry.summary()

    def __repr__(self) -> str:
        return (
            f"<Agent tools={len(self.registry)} "
            f"messages={self.memory.message_count} "
            f"mode={'local' if self.config.use_local_mode else 'api'}>"
        )
