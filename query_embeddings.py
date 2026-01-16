from __future__ import annotations

import argparse
import os
from pathlib import Path

import chromadb
import httpx
from dotenv import load_dotenv

from constants import DEFAULT_COLLECTION, DEFAULT_MODEL
from create_embeddings import embed_texts


def route_query(query: str) -> dict:
    lowered = query.lower()
    wants_conditions = any(token in lowered for token in [" if ", " else ", " when ", " then "])
    wants_loops = any(token in lowered for token in [" times", " repeat", " for each", " loop "])

    topics = []
    if wants_conditions:
        topics.append("conditions")
    if wants_loops:
        topics.append("loops")

    return {
        "doc_type": "RULE" if wants_conditions or wants_loops else None,
        "topics": topics,
        "wants_conditions": wants_conditions,
        "wants_loops": wants_loops,
    }


def rerank_by_priority(results: dict) -> list[dict]:
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    merged = []
    for doc_id, doc, meta, distance in zip(ids, docs, metas, distances):
        priority = (meta or {}).get("priority", 0)
        merged.append(
            {
                "id": doc_id,
                "data": doc,
                "meta": meta or {},
                "distance": distance,
                "priority": priority,
            }
        )
    merged.sort(key=lambda item: (-item["priority"], item["distance"]))
    return merged


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
    route = route_query(query)
    where = {"doc_type": route["doc_type"]} if route["doc_type"] else None

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
        where=where,
    )

    ranked = rerank_by_priority(results)

    topics = route["topics"]
    if topics:
        filtered = [item for item in ranked if item["meta"].get("topic") in topics]
        if filtered:
            ranked = filtered

    if not ranked:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        ranked = rerank_by_priority(results)

    for rank, item in enumerate(ranked[:top_k], start=1):
        meta = item["meta"]
        text = meta.get("text", "")
        print(f"{rank}. id={item['id']} distance={item['distance']} priority={item['priority']}")
        print(f"   data={item['data']}")
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
