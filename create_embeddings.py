from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List
from dotenv import load_dotenv

import chromadb
import httpx
from tqdm import tqdm

from constants import DATA_PATH, DEFAULT_COLLECTION, DEFAULT_MODEL, DEFAULT_BATCH_SIZE


def load_chunk_data(path: str) -> List[Dict[str, Any]]:
    spec = importlib.util.spec_from_file_location("rag_chunks_data", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "chunk_data"):
        raise RuntimeError("rag_chunks_data.py is missing chunk_data")
    return list(module.chunk_data)


def batched(items: List[Any], batch_size: int) -> Iterable[List[Any]]:
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def embed_texts(
    client: httpx.Client, api_key: str, texts: List[str], model: str
) -> List[List[float]]:
    response = client.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"input": texts, "model": model},
        timeout=60.0,
    )
    response.raise_for_status()
    data = response.json()
    return [item["embedding"] for item in data["data"]]


def build_collection(
    collection_name: str, model: str, batch_size: int, chroma_path: Path, api_key: str
) -> None:
    chunk_data = load_chunk_data(DATA_PATH)
    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    source_name = Path(DATA_PATH).name
    for index, item in enumerate(chunk_data):
        data_text = item.get("data") or ""
        if not data_text:
            continue
        ids.append(f"chunk-{index}")
        documents.append(data_text)
        metadatas.append(
            {
                "text": item.get("text", ""),
                "doc_type": item.get("doc_type", ""),
                "topic": item.get("topic", ""),
                "priority": item.get("priority", 0),
                "index": index,
                "source": source_name,
            }
        )

    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_or_create_collection(name=collection_name)

    with httpx.Client() as http_client:
        for batch_ids, batch_docs, batch_meta in tqdm(
            zip(
                batched(ids, batch_size),
                batched(documents, batch_size),
                batched(metadatas, batch_size),
            ),
            total=(len(ids) + batch_size - 1) // batch_size,
            desc="Embedding",
        ):
            embeddings = embed_texts(http_client, api_key, batch_docs, model)
            collection.upsert(
                ids=batch_ids,
                documents=batch_docs,
                metadatas=batch_meta,
                embeddings=embeddings,
            )

    preview_dir = Path("data/processed")
    preview_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = preview_dir / "embedding_preview.jsonl"
    json_path = preview_dir / "embedding_preview.json"

    preview_records = []
    with jsonl_path.open("w", encoding="utf-8") as jsonl_file:
        for doc_id, doc, meta in zip(ids, documents, metadatas):
            record = {"id": doc_id, "data": doc, "metadata": meta}
            jsonl_file.write(json.dumps(record, ensure_ascii=True) + "\n")
            preview_records.append(record)

    summary = {
        "count": len(preview_records),
        "collection": collection_name,
        "model": model,
        "records": preview_records,
    }
    with json_path.open("w", encoding="utf-8") as json_file:
        json.dump(summary, json_file, ensure_ascii=True, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create embeddings and store in ChromaDB.")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--chroma-path", default="data/chroma")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    chroma_path = Path(args.chroma_path)
    build_collection(args.collection, args.model, args.batch_size, chroma_path, api_key)


if __name__ == "__main__":
    main()
