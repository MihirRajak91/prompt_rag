#!/usr/bin/env python3
"""
Router Test Harness (planner-agnostic)

Runs query_embeddings.py as a subprocess for a list of test cases, then asserts:
- expected router topics (from "[debug] router accepted topics")
- expected presence/absence of topics in retrieved support chunks
- optional structural expectations (e.g., must include 'conditions' support chunk)

This harness intentionally treats query_embeddings.py as a black box to avoid
wiring into planner.py while you iterate on retrieval quality.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROUTER_TOPIC_RE = re.compile(r"^\s*-\s*topic=(?P<topic>[\w\-]+)\s+dist=", re.IGNORECASE)
CHUNK_META_RE = re.compile(r"^\s*meta\.doc_type=(?P<doc_type>\w+)\s+topic=(?P<topic>[\w\-]+)\s+priority=", re.IGNORECASE)


@dataclass
class RunResult:
    query: str
    raw: str
    router_topics: List[str]
    support_topics: List[str]


def run_query_embeddings(script_path: Path, query: str, python_cmd: List[str]) -> RunResult:
    """
    Executes query_embeddings.py which prompts on stdin with 'Enter query:'.
    We feed the query via stdin and parse stdout.
    """
    if not script_path.exists():
        raise FileNotFoundError(f"query_embeddings.py not found at: {script_path}")

    # Build command: (e.g.) uv run python query_embeddings.py
    cmd = python_cmd + [str(script_path)]

    proc = subprocess.run(
        cmd,
        input=(query + "\n").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    raw = proc.stdout.decode("utf-8", errors="replace")

    router_topics: List[str] = []
    support_topics: List[str] = []

    in_router_topics = False
    for line in raw.splitlines():
        if "[debug] router accepted topics:" in line:
            in_router_topics = True
            continue
        if in_router_topics:
            m = ROUTER_TOPIC_RE.search(line)
            if m:
                router_topics.append(m.group("topic"))
                continue
            # stop when we hit another debug line or blank
            if line.strip().startswith("[debug]") or line.strip() == "":
                in_router_topics = False

        m2 = CHUNK_META_RE.search(line)
        if m2:
            support_topics.append(m2.group("topic"))

    # de-dup while preserving order
    def dedup(xs: List[str]) -> List[str]:
        seen = set()
        out = []
        for x in xs:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    return RunResult(query=query, raw=raw, router_topics=dedup(router_topics), support_topics=dedup(support_topics))


def assert_case(case: Dict[str, Any], result: RunResult) -> Tuple[bool, List[str]]:
    """
    Returns (passed, messages)
    Case schema:
      - name: str
      - query: str
      - expect_router_topics: [str] (subset match)
      - forbid_router_topics: [str]
      - expect_support_topics: [str] (subset match)
      - forbid_support_topics: [str]
      - max_support_topics: int (optional)
      - max_router_topics: int (optional)
    """
    msgs: List[str] = []
    ok = True

    name = case.get("name", "<unnamed>")
    exp_r = case.get("expect_router_topics", [])
    forb_r = case.get("forbid_router_topics", [])
    exp_s = case.get("expect_support_topics", [])
    forb_s = case.get("forbid_support_topics", [])
    max_s = case.get("max_support_topics")
    max_r = case.get("max_router_topics")

    # Router topic subset expectations
    for t in exp_r:
        if t not in result.router_topics:
            ok = False
            msgs.append(f"[FAIL] missing router topic: {t}")
    for t in forb_r:
        if t in result.router_topics:
            ok = False
            msgs.append(f"[FAIL] forbidden router topic present: {t}")

    # Support topic subset expectations
    for t in exp_s:
        if t not in result.support_topics:
            ok = False
            msgs.append(f"[FAIL] missing support topic: {t}")
    for t in forb_s:
        if t in result.support_topics:
            ok = False
            msgs.append(f"[FAIL] forbidden support topic present: {t}")

    if isinstance(max_s, int) and len(result.support_topics) > max_s:
        ok = False
        msgs.append(f"[FAIL] support topic count {len(result.support_topics)} > max_support_topics {max_s}")

    if isinstance(max_r, int) and len(result.router_topics) > max_r:
        ok = False
        msgs.append(f"[FAIL] router topic count {len(result.router_topics)} > max_router_topics {max_r}")

    if ok:
        msgs.append("[PASS]")

    # Helpful context
    msgs.append(f"router_topics={result.router_topics}")
    msgs.append(f"support_topics={result.support_topics}")

    # Optional: dump raw on failure
    if not ok and case.get("show_raw_on_fail", True):
        msgs.append("---- raw output ----")
        msgs.append(result.raw)

    return ok, msgs


def main() -> int:
    ap = argparse.ArgumentParser(description="Router test harness for query_embeddings.py")
    ap.add_argument("--cases", required=True, help="Path to cases.json")
    ap.add_argument("--script", default="query_embeddings.py", help="Path to query_embeddings.py")
    ap.add_argument(
        "--python-cmd",
        default="uv run python",
        help="Command prefix used to run python (default: 'uv run python').",
    )
    ap.add_argument("--only", default="", help="Run only cases whose name contains this substring.")
    args = ap.parse_args()

    cases_path = Path(args.cases)
    script_path = Path(args.script)

    try:
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to read cases: {e}", file=sys.stderr)
        return 2

    python_cmd = args.python_cmd.split()

    total = 0
    passed = 0

    for case in cases:
        name = case.get("name", "<unnamed>")
        if args.only and args.only.lower() not in name.lower():
            continue

        total += 1
        query = case["query"]
        res = run_query_embeddings(script_path, query, python_cmd)
        ok, msgs = assert_case(case, res)

        status = "PASS" if ok else "FAIL"
        print(f"\n=== {status}: {name} ===")
        print(f"query: {query}")
        for m in msgs:
            print(m)

        if ok:
            passed += 1

    print(f"\nSummary: {passed}/{total} passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
