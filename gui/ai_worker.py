"""
Background AI worker — runs Ollama chat calls in a QThread to keep UI responsive.
"""
from PySide6.QtCore import QObject, Signal, Slot

from backend.ollama_client import OllamaClient


class AiWorker(QObject):
    """Runs a chat completion in a background thread."""

    finished = Signal(str)    # (response_text)
    error = Signal(str)       # (error_message)

    def __init__(self, prompt: str, model: str | None = None):
        super().__init__()
        self.prompt = prompt
        self.model = model

    @Slot()
    def run(self):
        try:
            client = OllamaClient()
            if self.model:
                client.model = self.model
            result = client.chat(self.prompt)
            client.close()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
