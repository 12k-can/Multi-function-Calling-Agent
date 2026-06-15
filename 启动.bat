@echo off
chcp 65001 >nul
title 🚀 多功能工具助手 - AI Agent

REM ============================================
REM 🚀 多功能工具助手 - 一键启动脚本 (Windows)
REM 双击即可运行，放在任何目录都支持
REM ============================================

REM 切换到脚本所在目录（核心：支持任意位置运行）
cd /d "%~dp0"

echo ================================================
echo   🚀 多功能工具助手 - AI Agent
echo ================================================
echo.

REM 检查 venv 是否存在
if not exist "venv\Scripts\python.exe" (
    echo 📦 首次运行，正在创建虚拟环境...
    python -m venv venv
    call venv\Scripts\pip install -r requirements.txt -q
    echo ✅ 环境准备完成！
    echo.
)

REM 检查依赖是否安装
call venv\Scripts\python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo 📦 正在安装依赖...
    call venv\Scripts\pip install -r requirements.txt -q
    echo ✅ 依赖安装完成！
    echo.
)

echo 🌐 服务启动中，请在浏览器访问：
echo    http://localhost:8501
echo.
echo ⏎ 按 Ctrl+C 停止服务
echo ================================================
echo.

REM 启动 Streamlit
call venv\Scripts\streamlit run app.py --server.port 8501

echo.
echo 服务已停止。
pause
