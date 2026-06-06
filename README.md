# Spark — 马列毛经典 AI 阅读助手

A local desktop AI assistant for reading and analyzing Marxist-Leninist-Maoist classics. Runs entirely offline with a local LLM (Ollama + Qwen2.5 7B).

## Features

| Feature | Description |
|---------|-------------|
| 💬 **Q&A Chat** | Three modes: RAG (document-grounded), Clipboard Context, Direct Q&A |
| 📖 **Reader** | Built-in text reader with AI paragraph analysis and historical background |
| 📚 **Document Library** | Drag-drop import for .txt .md .pdf .docx, vector DB management |
| ⚙️ **Settings** | Model selection, clipboard monitoring, hotkey config, auto-start |

**Theoretical stance:** All analysis is grounded in Marxist-Leninist-Maoist theory with historical-materialist context, independent of any contemporary political framework.

## Prerequisites

- **Windows 10/11** (Linux/macOS: partial support)
- **Python 3.10+**
- **Ollama** — [Download](https://ollama.com/download)
- **GPU recommended** — RTX 5060 tested (8GB VRAM runs 7B models comfortably)

## Quick Start

### 1. Install Ollama & pull models

```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

### 2. Set up Python environment

```bash
cd spark
python -m venv backend/.venv
backend\.venv\Scripts\pip install -r requirements.txt
```

### 3. Launch

```bash
backend\.venv\Scripts\python gui\app.py
```

Or double-click the `start_spark.bat --gui` from File Explorer.

## Usage

### First run

1. Launch the app — it checks Ollama connectivity automatically
2. Switch to **📚 Document Library** tab
3. Click **📄 Add File** and select `documents/马克思主义哲学概要.txt` (or drag-drop any .txt/.md/.pdf/.docx)
4. Switch to **💬 Q&A** tab and ask a question in RAG mode

### Reader Tab Smart Detection

Open a text file in the **📖 Reader** tab. Click any paragraph — the AI analyzes it and shows historical context and concept explanation in the right panel.

### Document Library

- **Drag-drop** files directly into the library window
- Supports: `.txt` `.md` `.pdf` `.docx`
- All text is chunked, embedded, and stored in a local ChromaDB vector database

## Project Structure

```
spark/
├── gui/                  # PySide6 desktop GUI
│   ├── app.py           # Entry point + system tray + hotkey
│   ├── main_window.py   # 4-tab window framework
│   ├── chat_tab.py      # Q&A chat with conversation history
│   ├── reader_tab.py    # Text reader with AI analysis
│   ├── library_tab.py   # Document library + vector DB management
│   ├── settings_tab.py  # Settings panel
│   ├── conversation_db.py # SQLite chat history
│   ├── ai_worker.py     # Background AI thread (keeps UI responsive)
│   ├── file_parser.py   # .pdf/.docx/.txt text extraction
│   └── resources/
│       └── theme.qss    # Dark academic stylesheet
├── backend/              # Core AI engine (unchanged from CLI MVP)
│   ├── config.py        # Model settings + prompts
│   ├── ollama_client.py # Ollama HTTP API wrapper
│   ├── clipboard_monitor.py # Clipboard polling
│   ├── rag_engine.py    # ChromaDB RAG engine
│   ├── ingest.py        # Document ingestion CLI
│   └── main.py          # Original CLI entry point
├── documents/            # Sample documents for testing
├── requirements.txt
├── start_spark.bat       # CLI launcher
└── README.md
```

## Configuration

Edit `backend/config.py` or use the **⚙️ Settings** tab in the GUI:

| Setting | Default | Description |
|---------|---------|-------------|
| Chat model | `qwen2.5:7b` | LLM for Q&A and analysis |
| Embed model | `nomic-embed-text` | Text embedding for RAG |
| Clipboard monitoring | On | Background clipboard polling |
| Auto-explain threshold | 50 chars | Min text length to trigger explanation |
| Global hotkey | `Ctrl+Shift+S` | Toggle window visibility |
| Auto-start | Off | Launch on Windows boot |

## FAQ

**Q: Does this require internet?**
A: No. All processing is local. No data ever leaves your machine.

**Q: Why is the AI response slow?**
A: Qwen2.5 7B takes 2-10 seconds per response on consumer GPUs. The UI runs in background threads so it stays responsive.

**Q: Can I use a different model?**
A: Yes. Pull any Ollama-compatible model (`ollama pull <model>`) and select it in Settings.

**Q: Why the MLM theoretical stance?**
A: The tool is designed as a serious reading companion for Marxist-Leninist-Maoist texts. It analyzes concepts within their historical-materialist context rather than through any contemporary political lens.

## Tech Stack

- **GUI:** PySide6 (Qt for Python)
- **LLM:** Ollama + Qwen2.5 7B
- **Vector DB:** ChromaDB (local, persistent)
- **Embeddings:** nomic-embed-text
- **Documents:** PyMuPDF (PDF), python-docx (Word)

## License

MIT
