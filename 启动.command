#!/bin/bash
# 🚀 多功能工具助手 - 一键启动脚本
# 双击此文件即可启动 (macOS)

cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"

echo "================================================"
echo "  🚀 多功能工具助手 - AI Agent"
echo "================================================"
echo ""

# 检查 venv 是否存在
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

echo "🌐 服务启动中，请在浏览器访问："
echo "   http://localhost:8501"
echo ""
echo "⏎ 按回车键停止服务"
echo "================================================"
echo ""

"$VENV_PYTHON" -m streamlit run "$PROJECT_DIR/app.py" --server.port 8501

echo ""
echo "服务已停止。"
