Priority Metadata

Overview
Each chunk carries a numeric `priority` that signals how important the content is during retrieval and later filtering/reranking. Higher numbers mean stronger preference when multiple chunks are relevant.

How Priority Is Assigned
- 100: Critical detection rules that decide workflow structure (e.g., condition detection).
- 90: High-importance rules that govern event selection or prevent mistakes (e.g., built-in filtering rules).
- 80: Important guidance that shapes planning behavior (e.g., planner policy, data-ops rules).
- 70: Supporting rules that apply in specific cases (e.g., loop routing rules).
- 40: Catalog/reference lists (event catalogs, trigger catalogs).

Current Mapping (Examples)
- Condition detection chunk: `priority: 100`
- Action events with built-in filtering: `priority: 90`
- Planner policy and data-ops rules: `priority: 80`
- Loop rules: `priority: 70`
- All catalog slices (events, triggers): `priority: 40`

Usage Notes
- Priority does not change embeddings; it is metadata meant for filtering or reranking.
- If you introduce new rule chunks, set priority based on how critical the rules are to correct planning.
- If a catalog grows very large, keep it at a lower priority so rules win when both match.
