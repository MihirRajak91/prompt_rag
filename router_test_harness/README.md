# Router Test Harness

This is a **planner-agnostic regression harness** for validating your routing + retrieval behavior while you iterate.

## What it tests
For each query, it runs `query_embeddings.py` and asserts:

- **Router topics** (from `"[debug] router accepted topics"` lines)
- **Support topics** (from `meta.doc_type=... topic=...` lines)
- **Forbidden topics** do not appear
- Optional caps on topic counts (to catch over-retrieval)

## Files
- `router_harness.py` — test runner
- `cases.json` — golden test suite

## How to run

From your project root (where `query_embeddings.py` lives):

```bash
uv run python router_test_harness/router_harness.py --cases router_test_harness/cases.json --script query_embeddings.py
```

If your run command differs (e.g., plain python):

```bash
python router_test_harness/router_harness.py --cases router_test_harness/cases.json --script query_embeddings.py --python-cmd "python"
```

Run only one case:

```bash
uv run python router_test_harness/router_harness.py --cases router_test_harness/cases.json --only "BIN + notification"
```

## Adding new tests

Add an entry to `cases.json`:

```json
{
  "name": "your test name",
  "query": "natural language query here",
  "expect_router_topics": ["topicA"],
  "expect_support_topics": ["topicB"],
  "forbid_support_topics": ["topicC"],
  "max_support_topics": 6
}
```

## Notes
- This harness treats `query_embeddings.py` as a **black box**, so you can validate retrieval behavior
  **before** wiring anything to `planner.py`.
- If a test fails, it prints the raw CLI output by default (`show_raw_on_fail=true`).


✅ PASS cases (what’s working)
1) if ... else ... ✅

Your conditions topic shows up because your structural forcing catches explicit if + else. 

query_embeddings

2) Domino case ✅

Also passes because it has else and if patterns (still caught by the current structural rules). 

query_embeddings

3) Built-in action filtering ✅

Router picks actions_builtin_filtering correctly for delete the record where.... This aligns with the action-built-in rules you have in your policy chunks (it’s coming out as the top support chunk). 

planner

❌ FAIL #1: “send email when status is approved” (missing conditions)
What happened

Router chose notifications_intent (fine), but your structural forcing did NOT add conditions.

Why (root cause)

Your structural_topics() only forces conditions when:

if + (then or else)

OR unless

OR (when and then) ✅ this is the important one 

query_embeddings

Your query has "when" but no "then", so it doesn’t trigger.

Meaning

You’re missing the very common pattern:

“do X when Y” (implicit branching)

Minimal fix

Update structural_topics() to treat " when " as conditional even without " then ".

❌ FAIL #2: SEQ query (missing conditions)

Query:

“check if status is approved send email and check if amount > 1000 send notification”

Why it failed

Same reason: your structural detection looks for "if " + " then " (or " else ").
But this query uses “check if …” without the literal "then" token, and there’s no "else".

Meaning

Your structural forcing currently detects syntax too narrowly.

Minimal fix

Extend structural detection to include:

"check if"

"and check if"

"verify if"

These are clearly branching/condition constructs even without “then”.

❌ FAIL #3: “get records where status is approved” (expected filtering, got actions_builtin_filtering)
What happened

Router selected actions_builtin_filtering and then support retrieval followed that topic-gate.

Why (root cause)

This one is not a structural forcing issue. It’s a router intent / embedding issue:

Your router thinks “get records where …” is closer to action-built-in policy than filtering policy.

That means your router chunk(s) for filtering topic are either:

not present/weak in router role chunks, or

semantically too similar to action-built-in chunk text, or

missing key phrases like “get records where”, “retrieve records where”, etc.

Your own support rules define a clear difference between filtering vs built-in actions, but the router isn’t learning it from its router embeddings. 

planner

