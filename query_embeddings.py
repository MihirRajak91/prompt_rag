from __future__ import annotations

import argparse
import os
import statistics
from functools import cmp_to_key
from pathlib import Path

import chromadb
import httpx
from dotenv import load_dotenv

from constants import DEFAULT_COLLECTION, DEFAULT_MODEL
from create_embeddings import embed_texts

# Chroma returns "distances" by default. For cosine distance, lower is better.
DISTANCE_SORT = "asc"
MIN_GROUP_SIZE = 2
TOP_ROUTER = 3
PRIORITY_EPSILON = 0.03
ROUTER_MAX_ABS_GAP = 0.08    # tune: 0.03–0.10 depending on embedding scale
ROUTER_MAX_REL_GAP = 0.05    # 3% relative gap
ROUTER_MIN_GAP_TO_ALLOW_MULTI = 0.05  # if everything is too close, treat as ambiguous and keep 1


# NEW: Router topic acceptance window.
# Keep TOP_ROUTER candidates, but only accept topics whose distance is within this ratio of the best router distance.
# If best router dist = d0, accept items with dist <= d0 * ROUTER_CUTOFF_RATIO
ROUTER_CUTOFF_RATIO = 1.06


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

    def compare_items(left: dict, right: dict) -> int:
        ld = left["distance"]
        rd = right["distance"]

        if ld != rd:
            return -1 if ld < rd else 1

        # Only break ties by priority inside same group (topic/doc_type)
        lm = left["meta"]
        rm = right["meta"]
        lgroup = (lm.get("doc_type") or "UNKNOWN", lm.get("topic") or "UNKNOWN")
        rgroup = (rm.get("doc_type") or "UNKNOWN", rm.get("topic") or "UNKNOWN")
        if lgroup == rgroup:
            lp = lm.get("priority", 0)
            rp = rm.get("priority", 0)
            if lp != rp:
                return -1 if lp > rp else 1

        return 0

    def best_item(items_list: list[dict]) -> dict:
        best = items_list[0]
        for item in items_list[1:]:
            if compare_items(item, best) < 0:
                best = item
        return best

    best_per_group = []
    for group_items in grouped.values():
        if len(group_items) < MIN_GROUP_SIZE:
            continue
        best_per_group.append(best_item(group_items))
    if not best_per_group:
        best_per_group = [best_item(group_items) for group_items in grouped.values()]
    best_per_group.sort(key=cmp_to_key(compare_items))

    selected: list[dict] = []
    seen_ids = set()

    if best_per_group:
        dists = [item["distance"] for item in best_per_group]
        best_score = dists[0]
        median_score = statistics.median(dists)
        cutoff = best_score * 1.10
        allowed = [item for item in best_per_group if item["distance"] <= cutoff]
        filtered_items = [item for item in items if item["distance"] <= cutoff]
        print(
            "[debug] groups="
            f"{len(best_per_group)} best={best_score:.4f} median={median_score:.4f} "
            f"ratio=1.10 allowed={len(allowed)}"
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
        filtered_items = items

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

    remaining = [item for item in filtered_items if item["id"] not in seen_ids]
    remaining.sort(key=cmp_to_key(compare_items))
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


def structural_topics(query: str) -> list[str]:
    """
    Minimal structural detection (not intent keyword lists).
    If query expresses branching, ensure 'conditions' is included.
    """
    q = query.lower()
    has_if = "if " in q
    has_else = " else " in q or " otherwise" in q
    has_then = " then " in q
    has_unless = " unless " in q
    has_when_then = (" when " in q) and (" then " in q)

    if (has_if and (has_then or has_else)) or has_unless or has_when_then:
        return ["conditions"]
    return []


def pick_forced_first(items: list[dict], forced_topics: list[str], top_k: int) -> list[dict]:
    """
    Guarantee at least one item from forced_topics (if available),
    but keep overall ranking natural (don’t always put forced first).
    """
    if not forced_topics:
        return select_by_groups(items, top_k)

    forced_set = set(forced_topics)

    # Get best forced item (if any)
    forced_items = [it for it in items if (it.get("meta") or {}).get("topic") in forced_set]
    if not forced_items:
        return select_by_groups(items, top_k)

    best_forced = select_by_groups(forced_items, 1)[0]

    # Now rank remaining normally
    remaining = [it for it in items if it["id"] != best_forced["id"]]
    rest = select_by_groups(remaining, max(top_k - 1, 0))

    # Merge and then re-sort by your standard compare logic to preserve global ordering
    combined = [best_forced] + rest
    # Re-run select_by_groups on combined to let compare_items decide final order cleanly
    return select_by_groups(combined, top_k)



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

    # --- Router stage ---
    router_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=TOP_ROUTER,
        include=["documents", "metadatas", "distances"],
        where={"role": {"$eq": "router"}},
    )
    router_items = build_items(router_results)
    router_items.sort(key=lambda item: item["distance"])

    chosen_topics: list[str] = []
    if router_items:
        best = router_items[0]["distance"]

        # Compute gaps
        gaps = [it["distance"] - best for it in router_items[1:]]
        min_gap = min(gaps) if gaps else 999.0

        # If the router is "flat" (all topics very similar), keep only best topic
        if min_gap < ROUTER_MIN_GAP_TO_ALLOW_MULTI:
            accepted_router = [router_items[0]]
        else:
            accepted_router = []
            for it in router_items:
                abs_gap = it["distance"] - best
                rel_gap = abs_gap / max(best, 1e-9)
                if abs_gap <= ROUTER_MAX_ABS_GAP and rel_gap <= ROUTER_MAX_REL_GAP:
                    accepted_router.append(it)

        print(
            "[debug] router "
            f"best={best:.4f} min_gap={min_gap:.4f} "
            f"accepted={len(accepted_router)}/{len(router_items)}"
        )
        if accepted_router:
            print("[debug] router accepted topics:")
            for it in accepted_router:
                print(f"  - topic={it['meta'].get('topic')} dist={it['distance']:.4f}")

        for it in accepted_router:
            topic = it["meta"].get("topic")
            if topic and topic not in chosen_topics:
                chosen_topics.append(topic)


    # Structural topics (e.g., branching) are added, not replacing router.
    forced_topics = structural_topics(query)
    for t in forced_topics:
        if t not in chosen_topics:
            chosen_topics.append(t)

    # If router produced nothing (or everything got filtered), fall back to forced topics only.
    if not chosen_topics:
        chosen_topics = forced_topics[:] if forced_topics else ["planner_policy"]

    # --- Support stage (topic-gated) ---
    candidate_k = min(max(top_k * 10, 80), 200)
    support_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=candidate_k,
        include=["documents", "metadatas", "distances"],
        where={
            "$and": [
                {"role": {"$eq": "support"}},
                {"topic": {"$in": chosen_topics}},
            ]
        },
    )
    support_items = build_items(support_results)

    selected_support = pick_forced_first(
        support_items,
        forced_topics=forced_topics,
        top_k=max(top_k - 1, 1),
    )

    # Always append planner_policy at the end (if present).
    planner_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=1,
        include=["documents", "metadatas", "distances"],
        where={
            "$and": [
                {"role": {"$eq": "support"}},
                {"topic": {"$eq": "planner_policy"}},
            ]
        },
    )
    planner_items = build_items(planner_results)

    selected: list[dict] = selected_support[:]
    if planner_items:
        if not any((it.get("meta") or {}).get("topic") == "planner_policy" for it in selected):
            selected.append(planner_items[0])

    # Print final selection
    for rank, item in enumerate(selected[:top_k], start=1):
        meta = item["meta"]
        text = meta.get("text", "")
        print(f"{rank}. id={item['id']} distance={item['distance']}")
        print(f"   data={item['data']}")
        print(
            "   meta.doc_type="
            f"{meta.get('doc_type')} topic={meta.get('topic')} priority={meta.get('priority')}"
        )
        print(f"   meta.role={meta.get('role')}")
        if text:
            print(f"   text={text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Query ChromaDB for top-k chunks.")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--chroma-path", default="data/chroma")
    parser.add_argument("--query", help="Query text to retrieve top-k chunks.")
    parser.add_argument("query_text", nargs="?", help="Query text (positional).")
    parser.add_argument("--top-k", type=int, default=6)
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
