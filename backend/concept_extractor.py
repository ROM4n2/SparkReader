"""
Concept extractor — uses RAG retrieval + LLM to extract related concepts.
Populates knowledge.db with concepts and relations automatically.
"""
import json
import re

from backend.config import KNOWLEDGE_EXTRACT_PROMPT, RAG_TOP_K
from backend.ollama_client import OllamaClient
from backend.rag_engine import RAGEngine
from backend import knowledge_db


def _clean_json(text: str) -> str:
    """Extract JSON array from LLM output that may contain markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:]) if lines[0].startswith("```") else text
        if text.endswith("```"):
            text = text[: text.rfind("```")].strip()
    return text


def extract_concepts(concept_name: str, client: OllamaClient = None) -> list[dict]:
    """
    Extract related concepts for a given concept name.
    Returns list of {concept, relation, explanation} dicts.
    Uses RAG retrieval to get context, then LLM to extract relations.
    Results are auto-saved to knowledge.db.
    """
    should_close = False
    if client is None:
        client = OllamaClient()
        should_close = True

    try:
        # 1. Check cache
        if knowledge_db.concept_has_relations(concept_name):
            return knowledge_db.get_relations(concept_name)

        # 2. RAG retrieval
        engine = RAGEngine()
        chunks = engine.search(concept_name, top_k=RAG_TOP_K)
        context = "\n\n".join(c["text"] for c in chunks)
        engine.close()

        if not context.strip():
            knowledge_db.upsert_concept(concept_name)
            return []

        # 3. LLM extraction (no stance — structural task)
        prompt = KNOWLEDGE_EXTRACT_PROMPT.format(
            concept_name=concept_name,
            context=context[:3000],
        )
        raw = client.chat(prompt, system_prompt="")
        cleaned = _clean_json(raw)

        try:
            items = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\[.*\]", cleaned, re.DOTALL)
            items = json.loads(match.group()) if match else []

        # 4. Save to DB
        knowledge_db.upsert_concept(concept_name)
        for item in items:
            knowledge_db.add_relation(
                source_name=concept_name,
                target_name=item["concept"],
                relation_type=item["relation"],
                explanation=item.get("explanation", ""),
            )

        return items

    finally:
        if should_close:
            client.close()


def extract_concepts_for_text(text: str, client: OllamaClient = None) -> str | None:
    """
    Given a paragraph of text, detect the primary concept name.
    Used as the first step in the passive analysis chain: click paragraph →
    detect concept → extract relations.
    Returns the concept name, or None if no clear concept found.
    """
    should_close = False
    if client is None:
        client = OllamaClient()
        should_close = True

    try:
        prompt = (
            "从以下文本中提取最核心的一个概念（只用1-5个字回答，只返回概念名）：\n\n"
            "{text}"
        ).format(text=text[:500])
        name = client.chat(prompt, system_prompt="").strip()
        name = name.strip("。，. ,\"'「」《》").split("\n")[0]
        if not name or len(name) > 20:
            return None
        return name
    finally:
        if should_close:
            client.close()
