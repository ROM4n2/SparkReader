"""
Summary worker — runs chapter/selection summarization in a QThread.
Reusable across tabs.
"""
import sys
import os
_SW_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJ_ROOT = os.path.abspath(os.path.join(_SW_DIR, ".."))
sys.path.insert(0, _PROJ_ROOT)
sys.path.insert(0, os.path.join(_PROJ_ROOT, "backend"))

from PySide6.QtCore import QObject, Signal, Slot

from backend.ollama_client import OllamaClient
from backend.config import SYSTEM_PROMPT, CHAPTER_SUMMARY_PROMPT, SELECTION_SUMMARY_PROMPT
from backend import knowledge_db


class SummaryWorker(QObject):
    """Runs a summarization prompt in a background thread."""

    finished = Signal(str, str)  # (file_path, summary_text)
    error = Signal(str)

    def __init__(self, file_path: str, text: str, scope: str = "selection"):
        """
        Args:
            file_path: source file path (for DB storage)
            text: the text to summarize
            scope: 'chapter' or 'selection'
        """
        super().__init__()
        self.file_path = file_path
        self.text = text
        self.scope = scope

    @Slot()
    def run(self):
        try:
            prompt = (
                CHAPTER_SUMMARY_PROMPT if self.scope == "chapter"
                else SELECTION_SUMMARY_PROMPT
            ).format(text=self.text[:4000])

            client = OllamaClient()
            result = client.chat(prompt, system_prompt=SYSTEM_PROMPT)
            client.close()

            scope_ref = "auto" if self.scope == "chapter" else self.text[:50]
            knowledge_db.save_summary(self.file_path, self.scope, scope_ref, result)

            self.finished.emit(self.file_path, result)
        except Exception as e:
            self.error.emit(str(e))
