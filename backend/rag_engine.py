"""
Spark - RAG 引擎（检索增强生成）

基于 ChromaDB 的本地向量检索系统：
1. 文档分块 → 嵌入 → 存入向量库
2. 用户提问 → 语义搜索 → 构建上下文 → LLM 回答

不使用 LangChain，手写完整调用链路。
"""
import os
import sys
import uuid

# Fix Windows console encoding for emoji/Unicode
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from pathlib import Path
from typing import List

import chromadb
from chromadb.config import Settings

from config import (
    CHROMA_PERSIST_DIR, CHUNK_SIZE, CHUNK_OVERLAP,
    RAG_TOP_K, RAG_PROMPT_TEMPLATE,
)
from ollama_client import OllamaClient


class RAGEngine:
    """
    Lightweight RAG engine with ChromaDB + local embeddings.

    Usage:
        engine = RAGEngine()
        engine.ingest_text("资本论的核心思想...", source="资本论简介")
        results = engine.search("什么是剩余价值？")
        answer = engine.ask("什么是剩余价值？")
    """

    def __init__(self, collection_name: str = "spark_docs"):
        self.ollama = OllamaClient()
        # Resolve persist directory to an absolute path
        persist_dir = str(Path(CHROMA_PERSIST_DIR).resolve())
        os.makedirs(persist_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},  # Use cosine similarity
        )

    # ── Document chunking ──────────────────────────────────────────

    def chunk_text(self, text: str, source: str = "") -> List[dict]:
        """
        Split text into overlapping chunks.

        Each chunk is a dict: {id, text, source, chunk_index}
        """
        chunks = []
        # Normalize whitespace
        text = text.strip()
        if not text:
            return chunks

        start = 0
        index = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))

            # Try to break at a sentence boundary (。！？\n) for cleaner chunks
            if end < len(text):
                # Look backwards for a sentence boundary within the last 50 chars
                boundary = -1
                for sep in ("。", "！", "？", "\n", "\n\n"):
                    pos = text.rfind(sep, max(start, end - 50), end)
                    if pos > boundary:
                        boundary = pos
                if boundary > start:
                    end = boundary + 1  # Include the punctuation

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk_id = str(uuid.uuid4())
                chunks.append({
                    "id": chunk_id,
                    "text": chunk_text,
                    "source": source,
                    "chunk_index": index,
                })

            # Advance by chunk_size - overlap, so chunks overlap
            start = end - CHUNK_OVERLAP if end < len(text) else len(text)
            index += 1

        return chunks

    # ── Ingestion ──────────────────────────────────────────────────

    BATCH_SIZE = 50  # Chunks per batch to avoid OOM and ChromaDB overload

    def ingest_text(self, text: str, source: str = "",
                    progress_callback=None) -> int:
        """
        Split text into chunks and store in ChromaDB in batches.

        Args:
            text: The full text content.
            source: Source name / file path for reference.
            progress_callback: Optional callable(msg: str) for progress updates.

        Returns:
            Number of chunks ingested.
        """
        chunks = self.chunk_text(text, source)
        if not chunks:
            return 0

        total = len(chunks)
        ingested = 0

        # Process in batches: embed → add → free memory
        for batch_start in range(0, total, self.BATCH_SIZE):
            batch = chunks[batch_start:batch_start + self.BATCH_SIZE]

            ids = [c["id"] for c in batch]
            texts = [c["text"] for c in batch]
            metadatas = [
                {"source": c["source"], "chunk_index": c["chunk_index"]}
                for c in batch
            ]

            # Generate embeddings for this batch
            if progress_callback:
                msg = f"正在嵌入 ({batch_start + 1}-{min(batch_start + self.BATCH_SIZE, total)}/{total})..."
                progress_callback(msg)
            embeddings = [self.ollama.embed(t) for t in texts]

            # Write this batch to ChromaDB
            self.collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas,
                embeddings=embeddings,
            )
            ingested += len(batch)

            # Allow memory to be freed before next batch
            del ids, texts, metadatas, embeddings, batch

        if progress_callback:
            progress_callback(f"完成，共 {ingested} 个片段")
        return ingested

    def ingest_file(self, file_path: str, progress_callback=None) -> int:
        """
        Load a text/markdown file and ingest it.

        Args:
            file_path: Path to .txt or .md file.
            progress_callback: Optional callable(msg: str) for progress updates.

        Returns:
            Number of chunks ingested.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # Use file_parser for .pdf/.docx, direct read for .txt/.md
        suffix = path.suffix.lower()
        if suffix in (".pdf", ".docx"):
            from gui.file_parser import parse_file
            text = parse_file(file_path)
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
        source = path.name
        return self.ingest_text(text, source=source, progress_callback=progress_callback)

    def ingest_directory(self, dir_path: str, progress_callback=None) -> int:
        """
        Ingest all .txt, .md, .pdf, .docx files in a directory.

        Args:
            dir_path: Directory to scan.
            progress_callback: Optional callable(msg: str) for progress updates.

        Returns:
            Total chunks ingested.
        """
        base = Path(dir_path)
        if not base.exists():
            raise FileNotFoundError(f"目录不存在: {dir_path}")

        total = 0
        files = []
        for ext in ("*.txt", "*.md", "*.pdf", "*.docx"):
            files.extend(sorted(base.glob(ext)))

        for i, fpath in enumerate(files):
            if progress_callback:
                progress_callback(f"({i + 1}/{len(files)}) {fpath.name}...")
            count = self.ingest_file(str(fpath), progress_callback=progress_callback)
            total += count
        if progress_callback:
            progress_callback(f"目录扫描完成，共 {total} 个片段")
        return total

    # ── Retrieval ──────────────────────────────────────────────────

    def search(self, query: str, top_k: int = RAG_TOP_K) -> List[dict]:
        """
        Semantic search: embed the query and find similar chunks.

        Args:
            query: The user's question.
            top_k: Number of results to return.

        Returns:
            List of {text, source, chunk_index, distance}
        """
        query_embedding = self.ollama.embed(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.collection.count()),
        )

        hits = []
        if results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                hits.append({
                    "text": results["documents"][0][i],
                    "source": results["metadatas"][0][i].get("source", ""),
                    "chunk_index": results["metadatas"][0][i].get("chunk_index", 0),
                    "distance": results["distances"][0][i] if results.get("distances") else 0,
                })
        return hits

    # ── Generation ─────────────────────────────────────────────────

    def ask(self, question: str, top_k: int = RAG_TOP_K) -> str:
        """
        Answer a question using RAG: retrieve relevant chunks, build context, ask LLM.

        Args:
            question: The user's question.
            top_k: Number of chunks to retrieve.

        Returns:
            The model's answer as a string.
        """
        hits = self.search(question, top_k=top_k)

        if not hits:
            # No relevant context found, fall back to direct Q&A
            from config import DIRECT_QA_TEMPLATE
            prompt = DIRECT_QA_TEMPLATE.format(question=question)
            return self.ollama.chat(prompt)

        # Build context from retrieved chunks
        context_parts = []
        for h in hits:
            header = f"--- 来自《{h['source']}》---" if h["source"] else ""
            context_parts.append(f"{header}\n{h['text']}")

        context = "\n\n".join(context_parts)
        prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=question)

        return self.ollama.chat(prompt)

    def close(self):
        """Clean up resources."""
        self.ollama.close()
