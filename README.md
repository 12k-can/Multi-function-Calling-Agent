<p align="center">
  <img src="https://img.icons8.com/fluency/96/000000/robot.png" alt="AI Agent Logo" width="120" />
</p>

<h1 align="center">🤖 Multi-function Calling Agent</h1>

<p align="center">
  <strong>基于 Function Calling 架构的多功能 AI 智能助手</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-1.28%2B-red" alt="Streamlit">
  <img src="https://img.shields.io/badge/LLM-Function%20Calling-green" alt="Function Calling">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="License">
</p>

<p align="center">
  <a href="#english">English</a> ·
  <a href="#chinese">中文</a>
</p>

---

<h2 id="chinese">🇨🇳 项目简介</h2>

本项目实现了一个基于 **Function Calling（工具调用）** 架构的 AI 智能助手，能够完成查天气、算数学、翻译、生成文件、查询数据库等多种任务。系统完整展示了工具注册、参数解析、错误重试、结果返回的完整流程，并内置了多轮对话记忆系统。

### ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🧠 **工具注册中心** | 装饰器式注册，自动从类型注解生成 OpenAI Function Calling Schema |
| 🔧 **13 个内置工具** | 天气查询、数学计算、方程求解、单位换算、翻译、文件生成、数据库查询 |
| 🔄 **智能错误重试** | 指数退避 + 随机抖动，Tool Call 自动重试 |
| 💾 **多轮对话记忆** | Token 预算管理、自动裁剪、摘要记忆、磁盘持久化 |
| 🚀 **双模式运行** | 本地模式（无需 API Key）+ OpenAI API 模式 |
| 🖥 **Streamlit UI** | 美观的交互界面，支持侧边栏工具管理、对话历史展示 |

### 🏗 系统架构

```
用户输入 → Agent 引擎 → 意图识别
                           │
                    ┌──────┴──────┐
                    ▼              ▼
               本地模式          API 模式
          (规则引擎模拟FC)    (OpenAI FC)
                    │              │
                    └──────┬──────┘
                           ▼
                    ToolRegistry
                    ┌───┼───┐───┐───┐
                    ▼   ▼   ▼   ▼   ▼
                天气  数学 翻译 文件 数据库
                           │
                           ▼
                    RetryHandler
                    (错误重试)
                           │
                           ▼
                    ConversationMemory
                    (多轮记忆)
                           │
                           ▼
                    最终回复 → 用户
```

### 📁 项目结构

```
ai-agent-interview/
├── app.py                      # 🖥 Streamlit 前端界面
├── requirements.txt            # 📦 依赖清单
├── agent/
│   ├── __init__.py             # 📤 包导出
│   ├── core.py                 # 🧠 核心 Agent 引擎
│   │   ├── Agent               # 主引擎：协调LLM、工具、记忆、重试
│   │   ├── AgentConfig         # 配置管理
│   │   ├── _local_llm_call()   # 本地模式（规则引擎）
│   │   └── _api_llm_call()     # API 模式（OpenAI）
│   │
│   ├── memory.py               # 💾 多轮对话记忆
│   │   ├── ConversationMemory  # 消息管理、Token裁剪、摘要生成
│   │   └── Message             # 消息数据模型
│   │
│   ├── retry.py                # 🔄 错误重试
│   │   ├── RetryHandler        # 重试执行器
│   │   └── RetryConfig         # 退避策略配置
│   │
│   └── tools/
│       ├── registry.py         # 📋 工具注册中心（核心）
│       │   ├── ToolRegistry    # 注册、Schema生成、参数校验、调度
│       │   ├── _build_param_schema()  # 自动生成参数Schema
│       │   └── _validate_and_cast()   # 类型转换与校验
│       │
│       ├── weather.py          # 🌤 天气查询工具
│       ├── math_tools.py       # 🔢 数学计算/解方程/单位换算
│       ├── translation.py      # 🌐 翻译/语言检测
│       ├── file_tools.py       # 📄 文件生成（md/csv/txt/json）
│       └── database.py         # 🗄 SQLite 数据库查询
```

### 🛠 安装与使用

#### 方式一：本地运行

```bash
# 1. 克隆仓库
git clone https://github.com/12k-can/Multi-function-Calling-Agent.git
cd Multi-function-Calling-Agent

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动应用
streamlit run app.py
```

打开浏览器访问 `http://localhost:8501` 即可使用。

#### 方式二：Docker（可选）

```bash
docker build -t ai-agent .
docker run -p 8501:8501 ai-agent
```

### 🎯 使用示例

在界面中输入自然语言即可触发工具调用：

| 你的输入 | 触发工具 | 效果 |
|---------|---------|------|
| "北京的天气怎么样？" | `get_weather` | 🌤 返回北京天气信息 |
| "计算 25 × 48 + 100" | `calculate` | 🔢 返回计算结果 1300 |
| "100公里等于多少英里" | `convert_units` | 📏 返回 62.1371 英里 |
| "翻译 Hello world 成中文" | `translate` | 🌐 返回"你好 世界" |
| "解方程 x² - 4 = 0" | `solve_equation` | 📐 返回 x = ±2 |
| "查询所有员工" | `execute_sql` | 🗄 返回员工数据表 |
| "生成一份数据报告" | `generate_report` | 📊 生成 Markdown 报告 |

### 🔌 工具注册示例

```python
from agent.tools.registry import ToolRegistry

registry = ToolRegistry()

@registry.register(
    name="say_hello",
    description="向用户问好",
    metadata={"category": "example"}
)
def say_hello(name: str, greeting: str = "你好") -> str:
    """
    向指定用户问好。
    
    :param name: 用户名
    :param greeting: 问候语，默认"你好"
    :returns: 问候消息
    """
    return f"{greeting}，{name}！"

# 自动生成的 OpenAI Schema:
# {
#   "type": "function",
#   "function": {
#     "name": "say_hello",
#     "description": "向用户问好",
#     "parameters": {
#       "type": "object",
#       "properties": {
#         "name": {"type": "string"},
#         "greeting": {"type": "string"}
#       },
#       "required": ["name"]
#     }
#   }
# }
```

### ⚙️ 配置说明

在 `agent/core.py` 的 `AgentConfig` 中可配置：

```python
config = AgentConfig(
    use_local_mode=True,      # True=本地模式, False=OpenAI API模式
    model="gpt-4o-mini",      # API 模式下的模型名称
    api_key="sk-xxx",         # OpenAI API Key（API模式必需）
    api_base=None,            # 自定义 API 地址
    tool_retry_count=2,       # 工具调用失败重试次数
    memory_max_tokens=4096,   # 记忆系统 Token 预算
    max_tool_rounds=10,       # 单次对话最大工具调用轮次
)
```

### 🔑 切换到 API 模式

如需使用真实 LLM，在 `app.py` 中修改：

```python
config = AgentConfig(
    use_local_mode=False,
    api_key="sk-your-api-key",   # 替换为你的 OpenAI Key
    model="gpt-4o-mini",         # 或其他支持 FC 的模型
)
```

### 🧪 运行测试

```bash
python -m pytest tests/ -v
```

或直接运行内置测试：

```bash
python -c "
import sys; sys.path.insert(0, '.')
from agent.core import Agent
agent = Agent()
agent.register_builtin_tools()
result = agent.execute('北京的天气怎么样？')
print(result['response'])
"
```

### 🗺 技术要点

| 知识点 | 实现方式 |
|--------|---------|
| **工具注册** | `ToolRegistry` 使用装饰器模式，通过 `inspect` 模块解析函数签名，自动生成 OpenAI Function Calling Schema |
| **参数解析** | 从类型注解推导参数类型，`_validate_and_cast` 自动将 LLM 返回的字符串转为目标类型 |
| **错误重试** | `RetryHandler` 实现指数退避 + 随机抖动，支持可重试异常白名单和重试回调 |
| **结果返回** | 工具执行结果统一为 `{success, result, error, tool_name, arguments}` 结构 |
| **多轮记忆** | `ConversationMemory` 维护消息列表，自动裁剪超出 Token 预算的历史，支持摘要提取和磁盘持久化 |
| **意图识别** | 本地模式下通过关键词匹配 + 互斥规则实现工具选择，API 模式下由 LLM 自行决策 |
| **类型安全** | `pydantic` 可选支持，内置安全数学求值（AST 白名单），SQL 注入防护（仅允许 SELECT） |

### 📄 许可证

[MIT License](LICENSE)

---

<h2 id="english">🇬🇧 English</h2>

### Introduction

A **Function Calling** based AI Agent framework that supports weather queries, math calculations, translations, file generation, and database queries. It demonstrates the complete pipeline of tool registration, parameter parsing, error retry, and result returning, with built-in multi-turn conversation memory.

### Key Features

| Feature | Description |
|---------|-------------|
| 🧠 **Tool Registry** | Decorator-based registration, auto-generates OpenAI Function Calling Schema from type hints |
| 🔧 **13 Built-in Tools** | Weather, math, equation solving, unit conversion, translation, file generation, database queries |
| 🔄 **Smart Error Retry** | Exponential backoff with jitter, automatic retry for tool calls |
| 💾 **Multi-turn Memory** | Token budget management, auto-truncation, summary extraction, disk persistence |
| 🚀 **Dual Mode** | Local mode (no API key) + OpenAI API mode |
| 🖥 **Streamlit UI** | Beautiful interface with sidebar tool management and conversation history |

### Quick Start

```bash
git clone https://github.com/12k-can/Multi-function-Calling-Agent.git
cd Multi-function-Calling-Agent
pip install -r requirements.txt
streamlit run app.py
```

### Architecture

```
User Input → Agent Engine → Intent Detection → ToolRegistry
                                                   │
                                    ┌──────────────┼──────────────┐
                                    ▼              ▼              ▼
                                Weather        Math/Calc      Translation
                                    ▼              ▼              ▼
                                File Gen      Database       ...more tools
                                                   │
                                                   ▼
                                            RetryHandler
                                            (Error Retry)
                                                   │
                                                   ▼
                                        ConversationMemory
                                        (Multi-turn Memory)
                                                   │
                                                   ▼
                                            Final Response → User
```

### Tool Registration Example

```python
from agent.tools.registry import ToolRegistry

registry = ToolRegistry()

@registry.register(
    name="say_hello",
    description="Say hello to a user",
    metadata={"category": "example"}
)
def say_hello(name: str, greeting: str = "Hello") -> str:
    return f"{greeting}, {name}!"
```

### License

[MIT License](LICENSE)

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/12k-can">12k-can</a>
  <br>
  Built with Function Calling Architecture · Tool Registry · Multi-turn Memory · Error Retry
</p>
