"""
🚀 AI Agent — 工具调用型多功能助手

基于 Function Calling 架构的智能助手，支持：
  查天气 | 算数学 | 翻译 | 生成文件 | 查询数据库 | 多轮记忆

运行方式:
    streamlit run app.py
"""

import streamlit as st
import json
import time
import os
import sys
from pathlib import Path

# 将项目根目录加入路径
sys.path.insert(0, str(Path(__file__).parent))

from agent import Agent, AgentConfig, ConversationMemory

# ═══════════════════════════════════════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="AI Agent — 工具调用型助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 自定义 CSS ──────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* 主容器 */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1rem;
    }
    .main-header h1 {
        margin: 0;
        font-size: 1.8rem;
    }
    .main-header p {
        margin: 0.3rem 0 0 0;
        opacity: 0.9;
        font-size: 0.95rem;
    }

    /* 对话消息 */
    .user-message {
        background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%);
        padding: 0.8rem 1rem;
        border-radius: 18px 18px 4px 18px;
        margin: 0.4rem 0;
        max-width: 85%;
        margin-left: auto;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .assistant-message {
        background: white;
        padding: 0.8rem 1rem;
        border-radius: 18px 18px 18px 4px;
        margin: 0.4rem 0;
        max-width: 85%;
        border: 1px solid #e5e7eb;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .tool-call {
        background: #f3f4f6;
        padding: 0.5rem 0.8rem;
        border-radius: 8px;
        margin: 0.3rem 0;
        font-size: 0.85rem;
        border-left: 3px solid #6366f1;
    }
    .tool-success {
        border-left-color: #10b981;
    }
    .tool-error {
        border-left-color: #ef4444;
    }

    /* 侧边栏 */
    .sidebar-section {
        margin-bottom: 1.5rem;
    }
    .sidebar-section h3 {
        font-size: 0.9rem;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    .tool-tag {
        display: inline-block;
        background: #eef2ff;
        color: #4338ca;
        padding: 0.15rem 0.6rem;
        border-radius: 12px;
        font-size: 0.75rem;
        margin: 0.15rem;
        border: 1px solid #c7d2fe;
    }

    /* 统计卡片 */
    .stat-card {
        background: white;
        padding: 0.8rem;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        text-align: center;
        border: 1px solid #f3f4f6;
    }
    .stat-card .stat-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #4f46e5;
    }
    .stat-card .stat-label {
        font-size: 0.75rem;
        color: #9ca3af;
        margin-top: 0.2rem;
    }

    /* 输入框 */
    .stTextInput > div > div > input {
        border-radius: 24px;
        border: 2px solid #e5e7eb;
        padding: 0.6rem 1rem;
        font-size: 1rem;
    }
    .stTextInput > div > div > input:focus {
        border-color: #6366f1;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.15);
    }

    /* 按钮 */
    .stButton > button {
        border-radius: 24px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.4rem 1.5rem;
        font-weight: 500;
    }
    .stButton > button:hover {
        opacity: 0.9;
        color: white;
    }

    /* 系统信息 */
    .info-box {
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 8px;
        padding: 0.6rem 1rem;
        margin: 0.4rem 0;
        font-size: 0.85rem;
        color: #166534;
    }
    .error-box {
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 8px;
        padding: 0.6rem 1rem;
        margin: 0.4rem 0;
        font-size: 0.85rem;
        color: #991b1b;
    }

    /* 响应式 */
    @media (max-width: 768px) {
        .user-message, .assistant-message {
            max-width: 95%;
        }
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 初始化
# ═══════════════════════════════════════════════════════════════════════════════

def init_agent() -> Agent:
    """初始化 Agent 实例。"""
    config = AgentConfig(
        use_local_mode=True,  # 使用本地模式（无需 API key）
        tool_retry_count=2,
        memory_max_tokens=4096,
    )
    agent = Agent(config=config)
    count = agent.register_builtin_tools(
        workspace_dir=str(Path(__file__).parent)
    )
    return agent


def init_session_state():
    """初始化 Streamlit 会话状态。"""
    if "agent" not in st.session_state:
        st.session_state.agent = init_agent()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "processing" not in st.session_state:
        st.session_state.processing = False
    if "show_details" not in st.session_state:
        st.session_state.show_details = True
    if "agent_status" not in st.session_state:
        st.session_state.agent_status = st.session_state.agent.get_status()


init_session_state()


# ═══════════════════════════════════════════════════════════════════════════════
# 侧边栏
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### 🤖 AI Agent")
    st.markdown("工具调用型多功能助手")

    st.markdown("---")

    # Agent 状态
    st.markdown('<div class="sidebar-section"><h3>系统状态</h3></div>', unsafe_allow_html=True)
    
    status = st.session_state.agent.get_status()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f'<div class="stat-card">'
            f'<div class="stat-value">{status["tools"]}</div>'
            f'<div class="stat-label">已注册工具</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            f'<div class="stat-card">'
            f'<div class="stat-value">{status["messages"]}</div>'
            f'<div class="stat-label">对话消息</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    # 运行模式
    mode_label = "🟢 本地模式 (演示)" if status["mode"] == "local" else "🔵 API 模式"
    st.markdown(f"**模式**: {mode_label}")
    st.markdown(f"**会话**: `{status['session'][:12]}...`")

    st.markdown("---")

    # 可用工具列表
    st.markdown('<div class="sidebar-section"><h3>🔧 可用工具</h3></div>', unsafe_allow_html=True)
    
    # 按分类展示
    registry = st.session_state.agent.registry
    categories = {}
    for name in registry.list_tools():
        meta = registry.get_metadata(name)
        cat = meta.get("category", "general")
        categories.setdefault(cat, []).append(name)

    for cat, tools in sorted(categories.items()):
        cat_icons = {
            "weather": "🌤",
            "math": "🔢",
            "translation": "🌐",
            "file": "📄",
            "database": "🗄",
            "general": "⚙️",
        }
        icon = cat_icons.get(cat, "📦")
        with st.expander(f"{icon} {cat}", expanded=True):
            for t in tools:
                meta = registry.get_metadata(t)
                st.markdown(f'<span class="tool-tag">{t}</span>', unsafe_allow_html=True)
                st.caption(meta["description"][:60])

    st.markdown("---")

    # 示例提示
    st.markdown('<div class="sidebar-section"><h3>💡 试试这样说</h3></div>', unsafe_allow_html=True)
    example_prompts = [
        "🌤 北京的天气怎么样？",
        "🔢 计算 25 × 48 + 100",
        "🔢 解方程 x² - 4 = 0",
        "🌐 翻译 Hello world 成中文",
        "📄 生成一份员工数据报告",
        "🗄 查询数据库有哪些表",
        "🔢 100公里等于多少英里",
        "🌐 检测一下这是什么语言: Bonjour",
    ]
    for prompt in example_prompts:
        if st.button(prompt, use_container_width=True, key=f"example_{prompt[:10]}"):
            st.session_state.input_text = prompt

    st.markdown("---")
    
    # 控制按钮
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 重置对话", use_container_width=True):
            st.session_state.agent.clear_memory()
            st.session_state.messages = []
            st.rerun()
    with col2:
        if st.button("⚙️ 重置 Agent", use_container_width=True):
            st.session_state.agent = init_agent()
            st.session_state.messages = []
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# 主界面
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(
    '<div class="main-header">'
    '<h1>🤖 AI Agent — 工具调用型智能助手</h1>'
    '<p>基于 Function Calling 架构 · 支持查天气 / 算数学 / 翻译 / 生成文件 / 查询数据库 · 多轮记忆</p>'
    '</div>',
    unsafe_allow_html=True
)

# ─── 对话展示 ────────────────────────────────────────────────────────────────

chat_container = st.container()

with chat_container:
    if not st.session_state.messages:
        # 欢迎界面
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("""
            <div style="text-align: center; padding: 3rem 1rem; color: #6b7280;">
                <div style="font-size: 4rem; margin-bottom: 1rem;">🤖</div>
                <h3 style="color: #374151;">你好！我是你的 AI Agent</h3>
                <p style="max-width: 400px; margin: 0 auto;">
                    我可以帮你查天气、算数学、翻译文本、生成文件和查询数据库。
                    在下方输入你的需求，或点击左侧的示例试试！
                </p>
                <div style="margin-top: 2rem; display: flex; flex-wrap: wrap; justify-content: center; gap: 0.5rem;">
                    <span style="background: #eef2ff; padding: 0.3rem 1rem; border-radius: 20px; font-size: 0.85rem;">🌤 查天气</span>
                    <span style="background: #eef2ff; padding: 0.3rem 1rem; border-radius: 20px; font-size: 0.85rem;">🔢 算数学</span>
                    <span style="background: #eef2ff; padding: 0.3rem 1rem; border-radius: 20px; font-size: 0.85rem;">🌐 翻译</span>
                    <span style="background: #eef2ff; padding: 0.3rem 1rem; border-radius: 20px; font-size: 0.85rem;">📄 生成文件</span>
                    <span style="background: #eef2ff; padding: 0.3rem 1rem; border-radius: 20px; font-size: 0.85rem;">🗄 查数据库</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        # 显示历史消息
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(
                    f'<div class="user-message">👤 {msg["content"]}</div>',
                    unsafe_allow_html=True
                )
            elif msg["role"] == "assistant":
                st.markdown(
                    f'<div class="assistant-message">🤖 {msg["content"]}</div>',
                    unsafe_allow_html=True
                )
            elif msg["role"] == "tool_call" and st.session_state.show_details:
                status_class = "tool-success" if msg.get("success") else "tool-error"
                icon = "✅" if msg.get("success") else "❌"
                st.markdown(
                    f'<div class="tool-call {status_class}">'
                    f'{icon} <strong>调用工具:</strong> {msg["tool"]} '
                    f'<code style="font-size:0.8rem;">{json.dumps(msg["arguments"], ensure_ascii=False)}</code>'
                    f'{" <span style=\"color:#ef4444;\">→ " + msg.get("error", "")[:80] + "</span>" if msg.get("error") else ""}'
                    f'</div>',
                    unsafe_allow_html=True
                )

# ─── 输入区域 ────────────────────────────────────────────────────────────────

st.markdown("---")

# 获取示例输入
input_value = st.session_state.get("input_text", "")

col_input, col_btn = st.columns([6, 1])
with col_input:
    user_input = st.text_input(
        "输入你的需求...",
        value=input_value,
        placeholder="例如：北京的天气怎么样？计算 25*48 翻译 Hello world...",
        label_visibility="collapsed",
        key="user_input",
        disabled=st.session_state.processing,
    )
with col_btn:
    send = st.button(
        "🚀 发送" if not st.session_state.processing else "⏳ 处理中...",
        use_container_width=True,
        disabled=st.session_state.processing,
    )

# 清理示例输入
if "input_text" in st.session_state:
    del st.session_state.input_text

# ─── 高级选项 ────────────────────────────────────────────────────────────────

with st.expander("⚙️ 高级选项", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.show_details = st.checkbox(
            "显示工具调用细节",
            value=st.session_state.show_details,
        )
    with col2:
        st.caption("当前使用本地模式（无需 API Key）")
        st.caption("如需真实 LLM，在 AgentConfig 中设置 use_local_mode=False")

# ─── 处理输入 ────────────────────────────────────────────────────────────────

if send and user_input.strip():
    st.session_state.processing = True
    
    # 添加用户消息
    st.session_state.messages.append({"role": "user", "content": user_input.strip()})
    
    # 处理
    try:
        with st.spinner("🤔 思考中..."):
            result = st.session_state.agent.execute(user_input.strip(), verbose=True)

        # 添加工具调用记录
        for tc in result.get("tool_calls", []):
            st.session_state.messages.append({
                "role": "tool_call",
                "tool": tc["tool"],
                "arguments": tc["arguments"],
                "success": tc["success"],
                "error": tc.get("error"),
            })

        # 添加助手回复
        response = result.get("response", "处理完成。")
        st.session_state.messages.append({"role": "assistant", "content": response})

        # 如果出错，显示错误
        if result.get("error"):
            st.session_state.messages.append({
                "role": "tool_call",
                "tool": "system",
                "arguments": {},
                "success": False,
                "error": result["error"],
            })

    except Exception as e:
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"😅 处理时出现了点问题：{str(e)}。请重试或换个问法。",
        })
        import traceback
        traceback.print_exc()

    finally:
        st.session_state.processing = False
        st.rerun()


# ─── 页脚 ────────────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown(
    '<div style="text-align: center; color: #9ca3af; font-size: 0.8rem;">'
    'Built with Function Calling Architecture · '
    'Tool Registry · Multi-turn Memory · Error Retry'
    '</div>',
    unsafe_allow_html=True
)
