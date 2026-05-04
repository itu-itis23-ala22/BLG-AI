from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from wiki_rag.config import CHROMA_DIR, DEFAULT_EMBED_MODEL, DEFAULT_LLM_MODEL, DEFAULT_OLLAMA_HOST


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Wikipedia RAG assistant")
    parser.add_argument("--ollama-host", default=os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST))
    parser.add_argument("--llm-model", default=os.getenv("OLLAMA_LLM_MODEL", DEFAULT_LLM_MODEL))
    parser.add_argument("--embed-model", default=os.getenv("OLLAMA_EMBED_MODEL", DEFAULT_EMBED_MODEL))

    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Fetch Wikipedia pages and build the vector store")
    ingest_parser.add_argument("--reset", action="store_true", help="Clear the existing Chroma collection first")

    ask_parser = subparsers.add_parser("ask", help="Ask one question")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--show-sources", action="store_true")
    ask_parser.add_argument("--top-k", type=int, default=6)

    chat_parser = subparsers.add_parser("chat", help="Start an interactive chat")
    chat_parser.add_argument("--show-sources", action="store_true")
    chat_parser.add_argument("--top-k", type=int, default=6)

    subparsers.add_parser("status", help="Show vector store status")
    subparsers.add_parser("reset", help="Delete local vector store files")

    args = parser.parse_args()

    if args.command == "ingest":
        ollama, store = _runtime(args)
        from wiki_rag.ingest import ingest_default_dataset

        result = ingest_default_dataset(store=store, ollama=ollama, reset=args.reset)
        print(f"Ingested {result.documents} Wikipedia documents.")
        print(f"Created/upserted {result.chunks} chunks.")
        print(f"Vector store now contains {result.collection_count} chunks.")
    elif args.command == "ask":
        ollama, store = _runtime(args)
        from wiki_rag.rag import LocalWikipediaRag

        rag = LocalWikipediaRag(store=store, ollama=ollama)
        result = rag.answer(args.question, top_k=args.top_k)
        print(result.answer)
        if args.show_sources:
            _print_sources(result.sources)
    elif args.command == "chat":
        ollama, store = _runtime(args)
        _chat_loop(store=store, ollama=ollama, show_sources=args.show_sources, top_k=args.top_k)
    elif args.command == "status":
        _, store = _runtime(args)
        print(f"Chroma path: {CHROMA_DIR}")
        print(f"Stored chunks: {store.count()}")
    elif args.command == "reset":
        if CHROMA_DIR.exists():
            shutil.rmtree(CHROMA_DIR)
        print("Local vector store reset complete.")


def _runtime(args: argparse.Namespace) -> tuple[Any, Any]:
    try:
        from wiki_rag.ollama_client import OllamaClient
        from wiki_rag.vector_store import WikiVectorStore
    except ModuleNotFoundError as exc:
        missing = exc.name or "a dependency"
        raise SystemExit(
            f"Missing dependency `{missing}`. Run `pip install -r requirements.txt` first."
        ) from exc

    ollama = OllamaClient(host=args.ollama_host, embed_model=args.embed_model, llm_model=args.llm_model)
    store = WikiVectorStore()
    return ollama, store


def _chat_loop(store: Any, ollama: Any, show_sources: bool, top_k: int) -> None:
    from wiki_rag.rag import LocalWikipediaRag

    rag = LocalWikipediaRag(store=store, ollama=ollama)
    print("Local Wikipedia RAG chat. Type :help for commands.")
    while True:
        try:
            query = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return

        if not query:
            continue
        if query in {":quit", ":exit", "quit", "exit"}:
            print("Goodbye.")
            return
        if query == ":help":
            print("Commands: :help, :sources on, :sources off, :clear, :reset, :quit")
            continue
        if query == ":sources on":
            show_sources = True
            print("Source display enabled.")
            continue
        if query == ":sources off":
            show_sources = False
            print("Source display disabled.")
            continue
        if query == ":clear":
            os.system("cls" if os.name == "nt" else "clear")
            continue
        if query == ":reset":
            store.reset()
            print("Vector store collection reset. Run `python main.py ingest --reset` before asking more questions.")
            continue

        result = rag.answer(query, top_k=top_k)
        print(f"\nAssistant: {result.answer}")
        if show_sources:
            _print_sources(result.sources)


def _print_sources(sources) -> None:
    if not sources:
        print("\nSources: none")
        return
    print("\nSources:")
    for index, source in enumerate(sources, start=1):
        title = source.metadata.get("title", "Unknown")
        entity_type = source.metadata.get("entity_type", "unknown")
        url = source.metadata.get("source_url", "")
        chunk_index = source.metadata.get("chunk_index", "?")
        print(f"{index}. {title} ({entity_type}, chunk {chunk_index}, distance {source.distance:.4f})")
        if url:
            print(f"   {url}")
        snippet = " ".join(source.text.split())[:240]
        if snippet:
            print(f"   Context: {snippet}...")


if __name__ == "__main__":
    main()

