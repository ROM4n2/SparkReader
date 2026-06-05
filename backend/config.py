"""
Spark - configuration constants.
Edit this file to adjust model, thresholds, and behavior.
"""
import os

# --- Ollama settings ---
OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")
CHAT_MODEL = "qwen2.5:7b"           # Main model for Q&A and explanations
EMBED_MODEL = "nomic-embed-text"    # For future RAG phase

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
