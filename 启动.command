#!/bin/bash
# ============================================
# 🚀 多功能工具助手 - 一键启动脚本 (macOS)
# 双击即可运行，放在任何目录都支持
# ============================================

# 切换到脚本所在目录（核心：支持任意位置运行）
cd "$(dirname "$0")" || { echo "❌ 无法进入项目目录"; exit 1; }
PROJECT_DIR="$(pwd)"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"

echo "================================================"
echo "  🚀 多功能工具助手 - AI Agent"
echo "================================================"
echo ""

# 检查 venv 是否存在，不存在则自动创建
if [ ! -f "$VENV_PYTHON" ]; then
    echo "📦 首次运行，正在创建虚拟环境..."
    python3 -m venv "$PROJECT_DIR/venv"
    "$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt" -q
    echo "✅ 环境准备完成！"
    echo ""
fi

# 检查依赖是否安装
if ! "$VENV_PYTHON" -c "import streamlit" 2>/dev/null; then
    echo "📦 正在安装依赖..."
    "$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt" -q
    echo "✅ 依赖安装完成！"
    echo ""
fi

echo "🌐 正在启动服务..."
echo "   浏览器将自动打开"
echo "   如未自动打开，请访问: http://localhost:8501"
echo ""
echo "⏎ 按回车键停止服务"
echo "================================================"
echo ""

# 延迟打开浏览器，等 Streamlit 启动
(sleep 2 && open "http://localhost:8501") &

# 启动 Streamlit
"$VENV_PYTHON" -m streamlit run "$PROJECT_DIR/app.py" --server.port 8501

echo ""
echo "服务已停止。"
