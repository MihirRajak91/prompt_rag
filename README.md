Project Documentation

Overview
This project builds a small RAG pipeline for workflow planning. It embeds chunked rule text with OpenAI embeddings, stores vectors in ChromaDB, and retrieves the most relevant chunks for a query using a two‑pass router/support strategy.

Folder Structure
- `data/processed/rag_chunks_data.py`: source chunks with metadata (topic, priority, role).
- `create_embeddings.py`: builds embeddings and stores them in Chroma.
- `query_embeddings.py`: queries Chroma and prints top‑k chunks.
- `data/processed/embedding_preview.jsonl`: per‑chunk preview written at embed time.
- `data/processed/embedding_preview.json`: summary preview written at embed time.

Setup
1) Create `.env` with your API key:
   - `OPENAI_API_KEY=...`
2) Install dependencies:
   - `uv pip install -r` (or your usual install flow from `pyproject.toml`)

Chunk Metadata
Each chunk carries metadata:
- `doc_type`: `RULE` or `CATALOG`
- `topic`: logical group (e.g., `conditions`, `notifications_intent`)
- `priority`: numeric hint for tie‑breaks
- `role`: `router` or `support`

Role Definitions
- `router`: short intent routing snippets (used in pass A).
- `support`: detailed rules, examples, and formatting (used in pass B).

Embedding Pipeline
Run:
```
python create_embeddings.py
```
What it does:
- Loads `chunk_data` from `data/processed/rag_chunks_data.py`.
- Embeds `data` with OpenAI.
- Stores embeddings in Chroma (`data/chroma`).
- Writes preview files:
  - `data/processed/embedding_preview.jsonl`
  - `data/processed/embedding_preview.json`

Query Pipeline (Two‑Pass Retrieval)
Run:
```
python query_embeddings.py
```
or
```
python query_embeddings.py "your question"
```

Detailed `query_embeddings.py` Flow
1) Embed the query text with OpenAI (`text-embedding-3-small` by default).
2) Router pass:
   - Query Chroma with `where={"role":{"$eq":"router"}}`.
   - Take the top router matches (default `TOP_ROUTER = 2`).
   - Collect their `topic` values as `chosen_topics`.
3) Support pass:
   - Query Chroma with an `$and` filter:
     - `role == support`
     - `topic IN chosen_topics`
   - Pull a larger candidate pool (`candidate_k = min(max(top_k*10, 80), 200)`).
4) Grouped selection on support items:
   - Group by `(doc_type, topic)` (missing values become `UNKNOWN`).
   - Pick a “best per group” item using:
     - Distance as primary rank.
     - Priority only when distances are within `PRIORITY_EPSILON`.
   - Apply a hard cutoff: keep only items with `distance <= best * 1.03`.
   - Select from allowed groups first, then fill from the filtered pool with a
     max-per-group cap (2).
5) Mandatory formatting policy:
   - Always fetch one `planner_policy` support chunk with:
     - `role == support`
     - `topic == planner_policy`
   - Append it (not ranked).
6) Print results:
   - For each chunk, print id, distance, data, and metadata (topic, doc_type, priority, role).

Pass A (Router)
- Query Chroma with `where={"role":{"$eq":"router"}}`.
- Take top router chunks (default: 2).
- Extract their `topic` values.

Pass B (Support)
- Query Chroma with `where={"role":{"$eq":"support"},"topic":{"$in": chosen_topics}}` using an `$and` filter.
- Select `top_k - 1` results using group‑aware diversity and distance cutoff.
- Append one `planner_policy` support chunk explicitly (mandatory).

Selection Rules (Support)
- Distance is primary.
- Priority only breaks ties within an epsilon.
- Groups are `(doc_type, topic)`; missing values become `UNKNOWN`.
- A cutoff keeps only near‑tie groups (ratio band).

Key Tunables
In `query_embeddings.py`:
- `TOP_ROUTER`: number of router chunks to consider.
- `MIN_GROUP_SIZE`: minimum items per group before it can lead.
- `PRIORITY_EPSILON`: distance tie threshold for priority.
- `top_k`: number of support chunks returned (default 6).

Rebuild Notes
Any change to `rag_chunks_data.py` requires a rebuild:
```
python create_embeddings.py
```
