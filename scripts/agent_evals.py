#!/usr/bin/env python3
"""
Agent evals (S1 Found, S2 Read correctly): run files for the fixed query set.

Makes zero network calls. The queries are run by hand (or by a session's own
search tool) and the ranks typed into the run file; this script keeps the run
files in one fixed shape so later runs diff against earlier ones.

Usage:
    python3 scripts/agent_evals.py new <engine> [date]   # print a blank run file
    python3 scripts/agent_evals.py check <run.md>        # validate + score a run
    python3 scripts/agent_evals.py diff <old.md> <new.md> # what moved

Rank columns: Tom's position in the result list, 0 if absent.
"""

import re
import sys
from datetime import date

QUERIES_FILE = "docs/agent-readable/evals/queries.md"
RUN_COLUMNS = ["id", "query", "target", "engine", "tbn", "linkedin", "tombot", "top result", "pass"]
RANK_COLUMNS = ["tbn", "linkedin", "tombot"]


def table_rows(text):
    """Yield the cells of every markdown table row, skipping separators"""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or re.match(r"^\|[\s\-|:]+\|$", line):
            continue
        yield [cell.strip() for cell in line.strip("|").split("|")]


def load_queries(path=QUERIES_FILE):
    """Read the query set: list of (id, query, target)"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    queries = []
    for cells in table_rows(text):
        if len(cells) == 3 and re.match(r"^[A-D]\d+$", cells[0]):
            queries.append(tuple(cells))
    return queries


def load_run(path):
    """Read a run file: dict of id -> row dict"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    rows = {}
    for cells in table_rows(text):
        if len(cells) == len(RUN_COLUMNS) and re.match(r"^[A-D]\d+$", cells[0]):
            rows[cells[0]] = dict(zip(RUN_COLUMNS, cells))
    return rows


def best_rank(row):
    """Best (lowest non-zero) rank across Tom's surfaces, 0 if absent"""
    ranks = [int(row[c]) for c in RANK_COLUMNS if int(row[c]) > 0]
    return min(ranks) if ranks else 0


def passes(target, rank):
    """Does this rank meet the query's target"""
    if target.startswith("#1"):
        return rank == 1
    if target.startswith("Top 5"):
        return 1 <= rank <= 5
    if target.startswith("absent"):
        return rank == 0
    return False


def cmd_new(engine, run_date):
    print(f"# S1 run {run_date}, engine {engine}\n")
    print("Query set: v1 (`evals/queries.md`). Rank is Tom's position, 0 if absent.\n")
    print("| " + " | ".join(RUN_COLUMNS) + " |")
    print("|" + "---|" * len(RUN_COLUMNS))
    for qid, query, target in load_queries():
        print(f"| {qid} | {query} | {target} | {engine} | 0 | 0 | 0 |  |  |")
    print("\n## A7 full answer (for S2 grading)\n")


def cmd_check(path):
    queries = load_queries()
    rows = load_run(path)
    errors = []
    appearances = 0
    met = 0
    for qid, query, target in queries:
        row = rows.get(qid)
        if row is None:
            errors.append(f"{qid}: missing from run")
            continue
        if row["query"] != query:
            errors.append(f"{qid}: query text differs from the query set")
        try:
            rank = best_rank(row)
        except ValueError:
            errors.append(f"{qid}: rank is not a number")
            continue
        ok = passes(target, rank)
        if row["pass"] != ("yes" if ok else "no"):
            errors.append(f"{qid}: pass column says '{row['pass']}', computed {'yes' if ok else 'no'}")
        if rank > 0:
            appearances += 1
        if ok:
            met += 1
    for qid in rows:
        if qid not in [q[0] for q in queries]:
            errors.append(f"{qid}: not in the query set")

    for error in errors:
        print(f"✗ {error}")
    print(f"Queries: {len(queries)}  Appearances: {appearances}  Targets met: {met}")
    return 1 if errors else 0


def cmd_diff(old_path, new_path):
    old, new = load_run(old_path), load_run(new_path)
    moved = 0
    for qid in sorted(set(old) | set(new), key=lambda q: (q[0], int(q[1:]))):
        before = best_rank(old[qid]) if qid in old else None
        after = best_rank(new[qid]) if qid in new else None
        if before != after:
            moved += 1
            print(f"{qid}: {before} -> {after}")
    print(f"{moved} queries moved")
    return 0


def main():
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "new":
        cmd_new(args[1], args[2] if len(args) > 2 else date.today().isoformat())
        return 0
    if len(args) == 2 and args[0] == "check":
        return cmd_check(args[1])
    if len(args) == 3 and args[0] == "diff":
        return cmd_diff(args[1], args[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
