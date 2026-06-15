"""
📋 工具注册中心 (Tool Registry)

核心职责：
  1. 工具注册 — 将 Python 函数注册为可被 LLM 调用的工具
  2. 参数解析 — 自动提取函数签名，生成 OpenAI Function Calling 规范
  3. 工具调度 — 根据 LLM 返回的工具名称和参数，找到对应函数并调用
  4. 结果格式化 — 将工具执行结果规范化为 LLM 可理解的字符串

设计理念：
  - 使用装饰器模式注册工具，简洁直观
  - 自动从类型注解推导参数 schema，减少重复编写
  - 支持同步和异步工具函数
  - 可插拔式架构，方便新增工具

使用示例：
  ```python
  registry = ToolRegistry()

  @registry.register("say_hello", "向用户问好")
  def say_hello(name: str) -> str:
      return f"你好，{name}！"
  ```
"""

import inspect
import json
import traceback
from typing import Any, Callable, Dict, Optional, get_type_hints

# ─── 类型别名 ────────────────────────────────────────────────────────────────
ToolFunc = Callable[..., Any]
ToolSchema = Dict[str, Any]  # OpenAI Function Calling 格式


class ToolRegistrationError(Exception):
    """工具注册时发生的错误。"""
    pass


class ToolNotFoundError(Exception):
    """找不到指定工具。"""
    pass


class ToolExecutionError(Exception):
    """工具执行时发生的错误。"""
    pass


# ─── Python 类型 → JSON Schema 类型映射 ──────────────────────────────────────
_TYPE_MAP: Dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    type(None): "null",
}

# 反向补全：允许的类型集合
_ALLOWED_TYPES = set(_TYPE_MAP.keys())


def _py_type_to_json_type(py_type: type) -> str:
    """将 Python 类型映射为 JSON Schema 类型。"""
    origin = getattr(py_type, "__origin__", None)
    if origin is not None:
        # 处理泛型类型如 Optional[str], List[int] 等
        return _TYPE_MAP.get(origin, "string")
    if py_type in _TYPE_MAP:
        return _TYPE_MAP[py_type]
    # 尝试处理 Union 类型
    args = getattr(py_type, "__args__", None)
    if args:
        # 取第一个非 None 类型
        for arg in args:
            if arg is not type(None):
                return _py_type_to_json_type(arg)
    return "string"  # 默认


def _is_optional_type(py_type: type) -> bool:
    """判断是否为 Optional 类型。"""
    args = getattr(py_type, "__args__", None)
    if args and type(None) in args:
        return True
    return False


def _build_param_schema(func: ToolFunc) -> Dict[str, Any]:
    """
    从函数的类型注解自动构建 JSON Schema 参数定义。
    
    支持：
      - 基本类型 (str, int, float, bool)
      - Optional 类型 (自动标记非必需)
      - 默认值参数 (自动标记非必需)
    """
    sig = inspect.signature(func)
    hints = get_type_hints(func, None, None)  # 宽松获取

    properties = {}
    required_params = []

    for name, param in sig.parameters.items():
        if name == "return":
            continue

        # 获取类型（优先注解，否则从默认值推断）
        py_type = hints.get(name, None)
        if py_type is None:
            if param.default is not inspect.Parameter.empty:
                py_type = type(param.default)
            else:
                py_type = str  # 默认字符串

        json_type = _py_type_to_json_type(py_type)

        # 构建属性描述
        prop: Dict[str, Any] = {"type": json_type}

        # 若参数有默认值或为 Optional，则非必需
        has_default = param.default is not inspect.Parameter.empty
        is_optional = _is_optional_type(py_type)

        if not has_default and not is_optional:
            required_params.append(name)

        # 从函数文档提取参数描述（简易解析）
        doc = (func.__doc__ or "")
        for line in doc.split("\n"):
            line = line.strip()
            if line.startswith(f":param {name}:"):
                prop["description"] = line.split(":", 2)[-1].strip()
                break

        properties[name] = prop

    return {
        "type": "object",
        "properties": properties,
        "required": required_params,
    }


def _extract_tool_description(func: ToolFunc) -> str:
    """从函数文档提取工具的简短描述（第一行）。"""
    doc = (func.__doc__ or "").strip()
    if not doc:
        return ""
    # 取第一段
    first_line = doc.split("\n\n")[0].strip()
    return first_line


# ═══════════════════════════════════════════════════════════════════════════════
# ToolRegistry
# ═══════════════════════════════════════════════════════════════════════════════


class ToolRegistry:
    """
    工具注册中心。
    
    管理所有可被 Agent 调用的工具，提供注册、查询、调用能力。
    支持装饰器式和命令式两种注册方式。
    """

    def __init__(self):
        self._tools: Dict[str, ToolFunc] = {}        # name -> function
        self._schemas: Dict[str, ToolSchema] = {}     # name -> OpenAI schema
        self._metadata: Dict[str, Dict[str, Any]] = {} # name -> extra info

    # ── 注册 ─────────────────────────────────────────────────────────────────

    def register(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Callable[[ToolFunc], ToolFunc]:
        """
        装饰器/函数：注册一个工具。
        
        Args:
            name: 工具名称，默认使用函数名。
            description: 工具描述，默认从函数文档提取。
            metadata: 附加元数据（如分类、版本等）。
        
        Returns:
            装饰器或 None（命令式调用时无返回值）。
        
        Raises:
            ToolRegistrationError: 如果工具名重复或参数无效。
        
        使用示例:
            @registry.register()
            def my_tool(param1: str, param2: int = 0) -> str:
                \"\"\"工具描述。\"\"\"
                return f"{param1}: {param2}"
        """
        def _decorator(func: ToolFunc) -> ToolFunc:
            nonlocal name, description
            tool_name = name or func.__name__
            tool_desc = description or _extract_tool_description(func)

            if tool_name in self._tools:
                raise ToolRegistrationError(
                    f"工具 '{tool_name}' 已存在。请使用不同的名称。"
                )

            # 构建 OpenAI Function Calling Schema
            param_schema = _build_param_schema(func)
            schema: ToolSchema = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_desc,
                    "parameters": param_schema,
                },
            }

            self._tools[tool_name] = func
            self._schemas[tool_name] = schema
            self._metadata[tool_name] = {
                "name": tool_name,
                "description": tool_desc,
                "func_qualname": f"{func.__module__}.{func.__qualname__}",
                "category": metadata.get("category", "general") if metadata else "general",
                "version": metadata.get("version", "1.0") if metadata else "1.0",
            }

            return func

        return _decorator

    def register_tool(
        self,
        func: ToolFunc,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        命令式注册一个工具（非装饰器用法）。
        
        Args:
            func: 工具函数。
            name: 工具名称，默认使用函数名。
            description: 工具描述。
            metadata: 附加元数据。
        """
        decorator = self.register(name=name, description=description, metadata=metadata)
        decorator(func)

    # ── 查询 ─────────────────────────────────────────────────────────────────

    def get_tool(self, name: str) -> ToolFunc:
        """根据名称获取工具函数。"""
        if name not in self._tools:
            raise ToolNotFoundError(f"工具 '{name}' 未注册。可用工具: {self.list_tools()}")
        return self._tools[name]

    def get_schema(self, name: str) -> ToolSchema:
        """获取工具的 OpenAI Function Calling Schema。"""
        if name not in self._schemas:
            raise ToolNotFoundError(f"工具 '{name}' 未注册。")
        return self._schemas[name]

    def get_all_schemas(self) -> list[ToolSchema]:
        """获取所有已注册工具的 Schema 列表（用于 LLM 调用）。"""
        return [self._schemas[name] for name in self._tools]

    def get_metadata(self, name: str) -> Dict[str, Any]:
        """获取工具的元数据。"""
        if name not in self._metadata:
            raise ToolNotFoundError(f"工具 '{name}' 未注册。")
        return self._metadata[name]

    def list_tools(self) -> list[str]:
        """列出所有已注册的工具名称。"""
        return list(self._tools.keys())

    def get_tools_by_category(self, category: str) -> list[str]:
        """按分类列出工具。"""
        return [
            name for name, meta in self._metadata.items()
            if meta.get("category") == category
        ]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return f"<ToolRegistry tools={list(self._tools.keys())}>"

    # ── 调用 ─────────────────────────────────────────────────────────────────

    def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        max_retries: int = 0,
    ) -> Dict[str, Any]:
        """
        调用指定工具并返回结构化结果。
        
        Args:
            name: 工具名称。
            arguments: 参数字典。
            max_retries: 失败时的最大重试次数。
        
        Returns:
            {
                "success": bool,
                "result": Any,          # 成功时的返回值
                "error": str | None,    # 失败时的错误信息
                "tool_name": str,
                "arguments": Dict,
            }
        
        Raises:
            ToolNotFoundError: 工具不存在。
        """
        from ..retry import RetryHandler

        func = self.get_tool(name)

        # 参数校验与类型转换
        try:
            parsed_args = self._validate_and_cast(name, arguments)
        except (TypeError, ValueError) as e:
            return {
                "success": False,
                "result": None,
                "error": f"参数解析失败: {e}",
                "tool_name": name,
                "arguments": arguments,
            }

        # 执行（带重试）
        retry_handler = RetryHandler(max_retries=max_retries)

        def _execute():
            return func(**parsed_args)

        success, result, error = retry_handler.execute(_execute)

        return {
            "success": success,
            "result": result if success else None,
            "error": error if not success else None,
            "tool_name": name,
            "arguments": parsed_args,
        }

    def _validate_and_cast(
        self, name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        校验并尝试类型转换参数。
        
        LLM 传入的参数通常是字符串，需要转换为函数期望的类型。
        """
        func = self._tools[name]
        sig = inspect.signature(func)
        hints = get_type_hints(func, None, None)

        parsed = {}
        for param_name, param in sig.parameters.items():
            if param_name == "return":
                continue
            if param_name not in arguments:
                if param.default is not inspect.Parameter.empty:
                    continue
                # 检查是否为 Optional
                py_type = hints.get(param_name)
                if py_type and _is_optional_type(py_type):
                    continue
                raise ValueError(f"缺少必需参数: '{param_name}'")

            raw_value = arguments[param_name]
            expected_type = hints.get(param_name)

            if expected_type and raw_value is not None:
                try:
                    parsed[param_name] = self._cast_value(
                        raw_value, expected_type
                    )
                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"参数 '{param_name}' 类型转换失败: "
                        f"期望 {expected_type.__name__}, 得到 {type(raw_value).__name__}: {e}"
                    )
            else:
                parsed[param_name] = raw_value

        return parsed

    @staticmethod
    def _cast_value(value: Any, target_type: type) -> Any:
        """将值转换为目标类型。"""
        if value is None:
            return None
        if target_type in (Any,):
            return value
        # 如果已经是目标类型，直接返回
        if isinstance(value, target_type):
            return value
        # 基本类型转换
        if target_type is str:
            return str(value)
        if target_type is int:
            try:
                return int(str(value).strip())
            except (ValueError, TypeError):
                raise
        if target_type is float:
            try:
                return float(str(value).strip())
            except (ValueError, TypeError):
                raise
        if target_type is bool:
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes", "y")
            return bool(value)
        if target_type is list:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return [v.strip() for v in value.split(",")]
            if isinstance(value, (list, tuple)):
                return list(value)
            return [value]
        if target_type is dict:
            if isinstance(value, str):
                return json.loads(value)
            if isinstance(value, dict):
                return value
            return dict(value)
        return value

    # ── 序列化 ───────────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """将注册中心信息导出为字典（用于展示/调试）。"""
        return {
            "tool_count": len(self._tools),
            "tools": {
                name: {
                    "description": self._metadata[name]["description"],
                    "category": self._metadata[name]["category"],
                    "parameters": self._schemas[name]["function"]["parameters"],
                }
                for name in self._tools
            },
        }

    def summary(self) -> str:
        """返回注册中心的可读摘要。"""
        lines = ["📋 工具注册中心摘要", "=" * 40, ""]
        categories: Dict[str, list] = {}
        for name, meta in self._metadata.items():
            cat = meta.get("category", "general")
            categories.setdefault(cat, []).append(name)

        for cat, tools in sorted(categories.items()):
            lines.append(f"  📂 {cat} ({len(tools)} 个工具)")
            for t in tools:
                meta = self._metadata[t]
                params = self._schemas[t]["function"]["parameters"]
                req = params.get("required", [])
                info = f"    🔧 {t}({', '.join(req) if req else ''})"
                if meta["description"]:
                    info += f"  — {meta['description']}"
                lines.append(info)
            lines.append("")

        return "\n".join(lines)
