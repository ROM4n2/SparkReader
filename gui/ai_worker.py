"""
Background workers — runs Ollama calls in QThreads to keep UI responsive.
"""
from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot

from backend.ollama_client import OllamaClient
from backend.rag_engine import RAGEngine


class AiWorker(QObject):
    """Runs a chat completion in a background thread."""

    finished = Signal(str)
    error = Signal(str)

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


class IngestWorker(QObject):
    """Ingests a file into the vector database in a background thread."""

    finished = Signal(str, int)    # (filename, chunk_count)
    error = Signal(str, str)       # (filename, error_message)
    progress = Signal(str)         # (status_message)

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path

    @Slot()
    def run(self):
        name = Path(self.file_path).name
        try:
            self.progress.emit(f"正在解析: {name}")
            engine = RAGEngine()
            count = engine.ingest_file(self.file_path)
            engine.close()
            self.finished.emit(name, count)
        except Exception as e:
            self.error.emit(name, str(e))


class DirIngestWorker(QObject):
    """Ingests all supported files in a directory in background."""

    finished = Signal(int)         # (total_chunks)
    error = Signal(str)            # (error_message)
    progress = Signal(str)         # (status_message)

    def __init__(self, dir_path: str):
        super().__init__()
        self.dir_path = dir_path

    @Slot()
    def run(self):
        try:
            self.progress.emit("正在扫描目录...")
            engine = RAGEngine()
            total = engine.ingest_directory(self.dir_path)
            engine.close()
            self.finished.emit(total)
        except Exception as e:
            self.error.emit(str(e))
