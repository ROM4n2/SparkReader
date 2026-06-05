"""
Clipboard monitor.
Polls the Windows clipboard for new text and triggers explanations.
"""
import time
import pyperclip
from config import MIN_EXPLAIN_LENGTH, POLL_INTERVAL, AUTO_EXPLAIN_TEMPLATE
from ollama_client import OllamaClient


class ClipboardMonitor:
    """
    Polls clipboard in a loop. When new text >= MIN_EXPLAIN_LENGTH chars
    is detected, generates an explanation via Ollama.

    Call start() to run in the current thread, or use it as the target of
    a threading.Thread for background operation.
    """

    def __init__(self):
        self.last_text = ""
        self.client = OllamaClient()

    def start(self):
        """
        Start monitoring clipboard. Runs forever until interrupted.
        Designed to run in a background thread.
        """
        print(f"📋 剪贴板监控已启动（阈值: {MIN_EXPLAIN_LENGTH} 字）")
        print("   复制任何长文本（>50字），AI 将自动解释...")
        print("   按 Ctrl+C 退出\n")

        try:
            while True:
                self._check_once()
                time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            pass
        finally:
            self.client.close()

    def _check_once(self):
        """Check clipboard once. Called by the loop."""
        try:
            current = pyperclip.paste()
        except Exception:
            return  # Clipboard not accessible, skip this cycle

        if not current or not current.strip():
            return

        if current == self.last_text:
            return  # No change

        self.last_text = current

        if len(current.strip()) < MIN_EXPLAIN_LENGTH:
            return  # Too short to auto-explain

        # Generate explanation
        print(f"\n{'='*60}")
        print(f"📖 检测到新文本（{len(current.strip())} 字）")
        print(f"{'='*60}")

        prompt = AUTO_EXPLAIN_TEMPLATE.format(text=current)
        try:
            response = self.client.chat(prompt)
            print(f"\n💡 解释：\n{response}\n")
        except (ConnectionError, RuntimeError) as e:
            print(f"⚠️  生成解释失败: {e}\n")
