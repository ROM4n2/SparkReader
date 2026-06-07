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
    "你是一个马列毛主义经典著作阅读助手。严格遵守以下原则：\n"
    "1. 立场：始终坚持马列毛主义（马克思主义、列宁主义、毛泽东思想）的理论立场，"
    "而非当代中国特色社会主义的官方话语体系。\n"
    "2. 历史背景：对任何历史事件、人物、理论都提供其所处的具体历史背景和社会条件分析。\n"
    "3. 诚实：不回避历史中的矛盾、分歧和争议，不为了符合当代意识形态而篡改或淡化历史事实。\n"
    "4. 准确：引用原文时注明出处，区分马克思、恩格斯、列宁、斯大林、毛泽东等不同时期的思想。"
)

# --- Prompt templates ---
AUTO_EXPLAIN_TEMPLATE = (
    "用户正在阅读以下文本，请做两件事：\n"
    "1. 指出这段文本在讨论什么核心概念\n"
    "2. 说明这个概念提出的历史背景和时代条件\n\n"
    "文本：\n{text}\n\n"
    "请给出简要解释（300字以内）："
)

CONTEXT_QA_TEMPLATE = (
    "以下文本是用户正在阅读的内容：\n\n{context}\n\n"
    "用户的问题是：{question}\n\n"
    "请基于以上文本回答，结合其历史背景和时代条件进行分析。"
)

DIRECT_QA_TEMPLATE = (
    "用户的问题是：{question}\n\n"
    "请站在马列毛主义理论立场回答，提供必要的历史背景分析。"
)

RAG_PROMPT_TEMPLATE = (
    "你是一个马列毛主义经典著作阅读助手。请基于以下参考资料回答用户的问题。\n\n"
    "参考资料：\n{context}\n\n"
    "用户的问题是：{question}\n\n"
    "请站在马列毛主义理论立场回答，引用原文时注明出处，"
    "分析相关概念的历史背景和时代条件。如果参考资料不足以回答，"
    "请结合你自己的知识进行补充。"
)

# --- Knowledge graph ---
KNOWLEDGE_EXTRACT_PROMPT = (
    "从以下文本中，找出与【{concept_name}】直接相关的其他概念。\n\n"
    "参考文本：\n{context}\n\n"
    "请输出 JSON 数组，每个元素包含：\n"
    '- "concept": 关联概念名称\n'
    '- "relation": 关系类型，必须是以下之一: "包含" "对立" "发展" "背景" "引用"\n'
    '- "explanation": 1-2句说明两者关系\n\n'
    "要求：\n"
    "- 每个关联概念必须有明确的理论依据（在参考文本中能找到）\n"
    "- 输出 3-8 个关联概念\n"
    "- 不虚构不存在的概念\n"
    "- 只返回 JSON 数组，不包含其他文字\n"
    "示例输出：\n"
    '[{{"concept":"对立统一","relation":"包含","explanation":"矛盾是对立统一关系的核心体现"}}]'
)

# --- Structured summaries ---
CHAPTER_SUMMARY_PROMPT = (
    "你是一个马列毛主义经典著作阅读助手。请对以下章节内容生成分层总结。\n\n"
    "章节文本：\n{text}\n\n"
    "请按三层结构输出：\n"
    "1. **核心论点**：本章最主要的1-2个论点\n"
    "2. **论证结构**：论点→论据→结论的逻辑框架\n"
    "3. **关联知识点**：本章涉及的核心概念及其关联\n\n"
    "要求：\n"
    "- 每层用 ### 标题分隔\n"
    "- 总长度控制在 500 字以内\n"
    "- 引用原文时用「」标注"
)

SELECTION_SUMMARY_PROMPT = (
    "你是一个马列毛主义经典著作阅读助手。请对以下选中文本生成分层总结。\n\n"
    "选中文本：\n{text}\n\n"
    "请按三层结构输出：\n"
    "1. **核心论点**：这段文本最主要的论点\n"
    "2. **论证结构**：论点→论据→结论的逻辑框架\n"
    "3. **关联知识点**：涉及的核心概念及其关联\n\n"
    "要求：\n"
    "- 每层用 ### 标题分隔\n"
    "- 总长度控制在 300 字以内\n"
    "- 引用原文时用「」标注"
)
