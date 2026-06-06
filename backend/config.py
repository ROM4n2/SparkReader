"""
Spark - configuration constants.
Edit this file to adjust model, thresholds, and behavior.
"""
import os

# --- Ollama settings ---
OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")
CHAT_MODEL = "qwen2.5:7b"           # Main model for Q&A and explanations
EMBED_MODEL = "nomic-embed-text"    # Embedding model for RAG

# --- RAG settings ---
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_db")  # Vector DB storage
CHUNK_SIZE = 300                     # Characters per chunk (Chinese: char ≈ token)
CHUNK_OVERLAP = 50                   # Overlap between adjacent chunks
RAG_TOP_K = 3                        # Number of chunks to retrieve for context
DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "documents")  # Where to look for text files

# Windows Chinese username workaround:
# If model loading fails with garbled path error, set this env var
# before starting Ollama: set OLLAMA_MODELS=C:\ollama_models

# --- Clipboard monitoring ---
MIN_EXPLAIN_LENGTH = 50    # Min Chinese characters to trigger auto-explain
POLL_INTERVAL = 2.0        # Seconds between clipboard checks

# --- System prompt ---
SYSTEM_PROMPT = (
    "你是一个马列经典著作阅读助手。你的任务是帮助用户理解马列毛经典著作"
    "（包括马克思主义哲学、政治经济学、科学社会主义以及毛泽东的著作和诗词）。"
    "回答要准确、简洁、有深度。引用原文时请注明出处。"
)

# --- Prompt templates ---
AUTO_EXPLAIN_TEMPLATE = (
    "用户正在阅读以下文本，请用简洁的语言解释其核心思想、历史背景和关键概念。\n\n"
    "文本：\n{text}\n\n"
    "请给出简要解释（300字以内）："
)

CONTEXT_QA_TEMPLATE = (
    "以下文本是用户正在阅读的内容：\n\n{context}\n\n"
    "用户的问题是：{question}\n\n"
    "请基于以上文本回答，结合你的知识进行补充。"
)

DIRECT_QA_TEMPLATE = (
    "用户的问题是：{question}\n\n"
    "请用中文回答，准确、有深度。"
)

RAG_PROMPT_TEMPLATE = (
    "你是一个马列经典著作阅读助手。请基于以下参考资料回答用户的问题。\n\n"
    "参考资料：\n{context}\n\n"
    "用户的问题是：{question}\n\n"
    "请基于参考资料回答，引用原文时注明出处。如果参考资料不足以回答，"
    "请结合你自己的知识进行补充。"
)
