@echo off
REM Spark - 马列经典著作 AI 阅读助手 启动脚本
REM 用法: start_spark          (双模式)
REM       start_spark --chat   (问答模式)
REM       start_spark --rag    (RAG 文档问答模式)
REM       start_spark --ingest (导入文档到向量库)
REM       start_spark --gui    (GUI 桌面模式)

echo 🔥 正在启动 Spark 环境...

REM 1. 确保 Ollama 服务在运行
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe" >NUL
if "%ERRORLEVEL%"=="0" (
    echo ✅ Ollama 服务已在运行
) else (
    echo 🔄 正在启动 Ollama 服务...
    start /B "" "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
    timeout /T 3 /NOBREAK >NUL
)

REM 3. 激活虚拟环境并启动 Spark
cd /d "%~dp0backend"
call .venv\Scripts\activate.bat
echo.

if /I "%1"=="--gui" (
    shift
    python gui\app.py %*
) else (
    python main.py %*
)

pause
