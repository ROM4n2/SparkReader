"""
Spark - 马列经典著作 AI 阅读助手 (MVP)

两种模式：
1. 被动模式 - 后台监控剪贴板，自动解释长文本
2. 主动模式 - 用户输入问题，AI 回答

启动方式：
    python main.py            # 同时启动两种模式
    python main.py --chat     # 仅交互问答模式
    python main.py --watch    # 仅剪贴板监控模式

注意：
    - Ollama 服务需先启动（系统托盘中应有 Ollama 图标）
    - 如果用户名含中文导致模型加载失败，请设置环境变量：
      set OLLAMA_MODELS=C:\ollama_models
      再重启 Ollama 服务
"""
import sys
import threading
import argparse
import httpx

# Fix Windows console encoding for emoji/Unicode
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import (
    SYSTEM_PROMPT, CONTEXT_QA_TEMPLATE, DIRECT_QA_TEMPLATE,
    OLLAMA_BASE_URL, CHAT_MODEL,
)
from ollama_client import OllamaClient
from clipboard_monitor import ClipboardMonitor


# Shared reference to latest clipboard text (for Q&A context)
_latest_clipboard = ""


def run_clipboard_watcher():
    """
    Run clipboard monitor in the current thread.
    Updates _latest_clipboard on each detected text change.
    """
    global _latest_clipboard

    class ContextAwareMonitor(ClipboardMonitor):
        def _check_once(self):
            super()._check_once()
            global _latest_clipboard
            _latest_clipboard = self.last_text

    monitor = ContextAwareMonitor()
    monitor.start()


def run_interactive_qa():
    """
    Interactive Q&A loop in the current thread.
    User types questions, AI answers. Uses latest clipboard content as context.
    """
    client = OllamaClient()
    print("\n💬 Spark 问答模式")
    print("   输入你的问题，按 Enter 发送")
    print("   输入 /clear 清屏，/exit 或 Ctrl+C 退出")
    print("   当前剪贴板内容将自动作为上下文\n")

    try:
        while True:
            try:
                question = input("❓ ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not question:
                continue
            if question.lower() in ("/exit", "/quit", "/q"):
                break
            if question.lower() == "/clear":
                print("\033[2J\033[H", end="")  # Clear screen
                continue

            # Build prompt with or without context
            global _latest_clipboard
            if _latest_clipboard and len(_latest_clipboard.strip()) >= 10:
                prompt = CONTEXT_QA_TEMPLATE.format(
                    context=_latest_clipboard.strip()[:2000],  # Truncate to stay within context
                    question=question,
                )
            else:
                prompt = DIRECT_QA_TEMPLATE.format(question=question)

            try:
                response = client.chat(prompt)
                print(f"\n💡 {response}\n")
            except (ConnectionError, RuntimeError) as e:
                print(f"\n⚠️  错误: {e}\n")

    finally:
        client.close()


def pre_flight_check() -> bool:
    """
    Check that Ollama is running and the required model is available.
    Returns True if everything is OK, False otherwise.
    """
    print("🔍 正在检查 Ollama 状态...")
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        if CHAT_MODEL not in models:
            print(f"⚠️  未找到模型 {CHAT_MODEL}")
            print(f"   已安装模型: {', '.join(models) if models else '无'}")
            print(f"   请运行: ollama pull {CHAT_MODEL}")
            return False
        print(f"✅ Ollama 已连接 | 模型: {CHAT_MODEL}")
        return True
    except httpx.ConnectError:
        print(f"❌ 无法连接到 Ollama（{OLLAMA_BASE_URL}）")
        print(f"   请确保 Ollama 正在运行（检查系统托盘）")
        return False
    except Exception as e:
        print(f"❌ Ollama 检查失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Spark - 马列经典著作 AI 阅读助手")
    parser.add_argument("--chat", action="store_true", help="仅启动问答模式")
    parser.add_argument("--watch", action="store_true", help="仅启动剪贴板监控")
    args = parser.parse_args()

    print("🔥 Spark 已启动\n")

    # Pre-flight check
    if not pre_flight_check():
        sys.exit(1)

    if args.chat:
        run_interactive_qa()
    elif args.watch:
        monitor = ClipboardMonitor()
        monitor.start()
    else:
        # Both: monitor in background, Q&A in foreground
        watcher = threading.Thread(target=run_clipboard_watcher, daemon=True)
        watcher.start()
        try:
            run_interactive_qa()
        except KeyboardInterrupt:
            print("\n\n👋 再见！")


if __name__ == "__main__":
    main()
