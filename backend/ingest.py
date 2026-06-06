"""
Spark - 文档导入工具

将 documents/ 目录下的文本/标记文件导入 Chroma 向量库。
"""
import sys
import os

# Fix Windows console encoding for emoji/Unicode
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure we can import from the backend directory
sys.path.insert(0, os.path.dirname(__file__))

from rag_engine import RAGEngine


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Spark - 文档导入工具")
    parser.add_argument("--dir", default=None, help="要导入的目录（默认: documents/）")
    parser.add_argument("--file", default=None, help="单个文件路径")
    parser.add_argument("--clear", action="store_true", help="清空向量库后重新导入")
    parser.add_argument("--info", action="store_true", help="查看向量库状态")
    args = parser.parse_args()

    engine = RAGEngine()

    try:
        if args.info:
            count = engine.collection.count()
            print(f"📊 向量库状态")
            print(f"   集合名: {engine.collection.name}")
            print(f"   文档片段数: {count}")
            if count > 0:
                # Show unique sources
                results = engine.collection.get(include=["metadatas"])
                sources = set(m["source"] for m in results["metadatas"] if m.get("source"))
                print(f"   来源文件:")
                for s in sorted(sources):
                    print(f"     - {s}")
            return

        if args.clear:
            print("🗑️  清空向量库...")
            count = engine.collection.count()
            if count > 0:
                engine.collection.delete(ids=engine.collection.get()["ids"])
            print(f"   已删除 {count} 个片段")

        if args.file:
            print(f"📄 正在导入: {args.file}")
            count = engine.ingest_file(args.file)
            print(f"✅ 完成: 导入 {count} 个片段")

        else:
            target_dir = args.dir or os.path.join(os.path.dirname(__file__), "..", "documents")
            print(f"📂 正在扫描目录: {target_dir}")
            count = engine.ingest_directory(target_dir)
            if count == 0:
                print("⚠️  未找到任何 .txt 或 .md 文件")
            else:
                print(f"✅ 完成: 共导入 {count} 个片段")

    finally:
        engine.close()


if __name__ == "__main__":
    main()
