from __future__ import annotations

import argparse
import os
import statistics
from pathlib import Path

import chromadb
import httpx
from dotenv import load_dotenv

from constants import DEFAULT_COLLECTION, DEFAULT_MODEL
from create_embeddings import embed_texts


# Chroma returns "distances" by default. For cosine distance, lower is better.
DISTANCE_SORT = "asc"
MIN_GROUP_SIZE = 2


def build_items(results: dict) -> list[dict]:
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    merged = []
    for doc_id, doc, meta, distance in zip(ids, docs, metas, distances):
        merged.append(
            {
                "id": doc_id,
                "data": doc,
                "meta": meta or {},
                "distance": distance,
            }
        )
    return merged


def select_by_groups(items: list[dict], top_k: int) -> list[dict]:
    if DISTANCE_SORT != "asc":
        raise RuntimeError("This pipeline assumes cosine distance (lower is better).")

    grouped: dict[tuple[str, str], list[dict]] = {}
    for item in items:
        meta = item["meta"]
        doc_type = meta.get("doc_type") or "UNKNOWN"
        topic = meta.get("topic") or "UNKNOWN"
        group_key = (doc_type, topic)
        grouped.setdefault(group_key, []).append(item)

    def sort_key(item: dict) -> tuple[float, int]:
        return (item["distance"], -item["meta"].get("priority", 0))

    best_per_group = []
    for group_items in grouped.values():
        if len(group_items) < MIN_GROUP_SIZE:
            continue
        best_per_group.append(min(group_items, key=sort_key))
    if not best_per_group:
        best_per_group = [min(group_items, key=sort_key) for group_items in grouped.values()]
    best_per_group.sort(key=sort_key)

    selected: list[dict] = []
    seen_ids = set()

    if best_per_group:
        dists = [item["distance"] for item in best_per_group]
        best_score = dists[0]
        median_score = statistics.median(dists)
        allowed = [
            item for item in best_per_group if item["distance"] <= best_score * 1.03
        ]
        print(
            "[debug] groups="
            f"{len(best_per_group)} best={best_score:.4f} median={median_score:.4f} "
            f"ratio=1.03 allowed={len(allowed)}"
        )
        if allowed:
            print("[debug] allowed groups:")
            for item in allowed:
                meta = item["meta"]
                print(
                    "  - "
                    f"{(meta.get('doc_type') or 'UNKNOWN', meta.get('topic') or 'UNKNOWN')} "
                    f"dist={item['distance']:.4f}"
                )
    else:
        allowed = []

    for item in allowed:
        if item["id"] in seen_ids:
            continue
        selected.append(item)
        seen_ids.add(item["id"])
        if len(selected) >= top_k:
            return selected

    for item in best_per_group:
        if item["id"] in seen_ids:
            continue
        selected.append(item)
        seen_ids.add(item["id"])
        if len(selected) >= top_k:
            return selected

    remaining = [item for item in items if item["id"] not in seen_ids]
    remaining.sort(key=sort_key)
    topic_counts: dict[tuple[str, str], int] = {}
    for item in selected:
        meta = item["meta"]
        group_key = (meta.get("doc_type") or "UNKNOWN", meta.get("topic") or "UNKNOWN")
        topic_counts[group_key] = topic_counts.get(group_key, 0) + 1
    max_per_group = 2
    for item in remaining:
        meta = item["meta"]
        group_key = (meta.get("doc_type") or "UNKNOWN", meta.get("topic") or "UNKNOWN")
        if topic_counts.get(group_key, 0) >= max_per_group:
            continue
        selected.append(item)
        topic_counts[group_key] = topic_counts.get(group_key, 0) + 1
        if len(selected) >= top_k:
            break

    return selected


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
    candidate_k = min(max(top_k * 10, 80), 200)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=candidate_k,
        include=["documents", "metadatas", "distances"],
    )

    items = build_items(results)
    selected = select_by_groups(items, top_k)

    for rank, item in enumerate(selected[:top_k], start=1):
        meta = item["meta"]
        text = meta.get("text", "")
        print(f"{rank}. id={item['id']} distance={item['distance']}")
        print(f"   data={item['data']}")
        print(
            "   meta.doc_type="
            f"{meta.get('doc_type')} topic={meta.get('topic')} priority={meta.get('priority')}"
        )
        if text:
            print(f"   text={text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Query ChromaDB for top-k chunks.")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--chroma-path", default="data/chroma")
    parser.add_argument("--query", help="Query text to retrieve top-k chunks.")
    parser.add_argument("query_text", nargs="?", help="Query text (positional).")
    parser.add_argument("--top-k", type=int, default=4)
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
