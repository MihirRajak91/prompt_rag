from __future__ import annotations

import argparse
import os
from pathlib import Path

import chromadb
import httpx
from dotenv import load_dotenv

from constants import DEFAULT_COLLECTION, DEFAULT_MODEL
from create_embeddings import embed_texts


def run_query(
    collection_name: str,
    model: str,
    chroma_path: Path,
    api_key: str,
    query: str,
    top_k: int,
) -> None:
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_or_create_collection(name=collection_name)

    with httpx.Client() as http_client:
        query_embedding = embed_texts(http_client, api_key, [query], model)[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for rank, (doc_id, doc, meta, distance) in enumerate(
        zip(ids, docs, metas, distances), start=1
    ):
        text = (meta or {}).get("text", "")
        print(f"{rank}. id={doc_id} distance={distance}")
        print(f"   data={doc}")
        if text:
            print(f"   text={text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Query ChromaDB for top-k chunks.")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--chroma-path", default="data/chroma")
    parser.add_argument("--query", help="Query text to retrieve top-k chunks.")
    parser.add_argument("query_text", nargs="?", help="Query text (positional).")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    query = args.query or args.query_text
    if not query:
        query = input("Enter query: ").strip()
    if not query:
        raise SystemExit("Provide a query via --query, positional arg, or stdin.")

    run_query(
        args.collection,
        args.model,
        Path(args.chroma_path),
        api_key,
        query,
        args.top_k,
    )


if __name__ == "__main__":
    main()
