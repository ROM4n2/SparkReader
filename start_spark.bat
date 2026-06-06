@echo off
REM Spark - 马列经典著作 AI 阅读助手 启动脚本
REM 解决中文用户名导致 Ollama 模型加载失败的问题

echo 🔥 正在启动 Spark 环境...

REM 1. 设置英文模型路径（绕过中文用户名 bug）
set OLLAMA_MODELS=C:\ollama_models

REM 2. 确保 Ollama 服务在运行
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
python main.py %*

pause
