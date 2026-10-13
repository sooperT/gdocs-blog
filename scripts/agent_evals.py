#!/usr/bin/env python3
"""
Agent evals (S1 Found, S2 Read correctly): run files for the fixed query set.

`new`, `check` and `diff` make zero network calls. The queries are run by hand
(or by a session's own search tool) and the ranks typed into the run file; this
script keeps the run files in one fixed shape so later runs diff against
earlier ones.

`fetch` is the only subcommand that touches the network: free plain GETs of a
deployed site (facts page, llms.txt, robots, sitemaps, the `/ask` map). It
never calls `/ask?q=` or `/ask/brief`, which cost embeddings and Claude calls.

Usage:
    python3 scripts/agent_evals.py new <engine> [date]   # print a blank run file
    python3 scripts/agent_evals.py check <run.md>        # validate + score a run
    python3 scripts/agent_evals.py diff <old.md> <new.md> # what moved (S1 or fetch runs)
    python3 scripts/agent_evals.py fetch --base <url> [--write] [--date YYYY-MM-DD]
    python3 scripts/agent_evals.py --base <url> [--write] [--date YYYY-MM-DD]   # same as fetch

Rank columns: Tom's position in the result list, 0 if absent.
fetch --write saves docs/agent-readable/evals/runs/<date>-fetch.md.
Fetch check ids: C = check_staging's smoke checks, E = eval assertions,
S = a URL in the deployed sitemap-agent.xml, L = a link in the deployed llms.txt.
"""

import json
import os
import re
import sys
import time
from datetime import date, datetime
from urllib.parse import urlsplit

QUERIES_FILE = "docs/agent-readable/evals/queries.md"
RUN_COLUMNS = ["id", "query", "target", "engine", "tbn", "linkedin", "tombot", "top result", "pass"]
RANK_COLUMNS = ["tbn", "linkedin", "tombot"]

RUNS_DIR = "docs/agent-readable/evals/runs"
FETCH_COLUMNS = ["id", "path", "status", "content type", "result", "detail"]
SITE_HOSTS = ("takenbyninjas.com", "www.takenbyninjas.com")
# Paths that cost money (Voyage embeddings, Claude calls). fetch does free calls only.
PAID_MARKERS = ("?q=", "&q=", "brief=", "/ask/brief")
EXPECTED_SECTIONS = 73
MAX_LINKED_URLS = 120  # per list (sitemap-agent.xml, llms.txt); about 90 and 35 today
PAUSE_SECONDS = 0.2    # between requests, to be polite to the host


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


def is_paid(path):
    """True for any path that would trigger a paid call"""
    return any(marker in path for marker in PAID_MARKERS)


class FreeFetcher:
    """Plain GETs against one base URL, cached per path, with a pause between requests"""

    def __init__(self, base):
        self.base = base.rstrip("/")
        self.cache = {}

    def get(self, path):
        # Free calls only: /ask?q= and /ask/brief cost embeddings and Claude calls,
        # and a path can arrive here from a deployed sitemap or llms.txt, so the
        # guard sits at the one place every request passes through.
        if is_paid(path):
            raise ValueError(f"refused, paid path: {path}")
        if path not in self.cache:
            from check_staging import fetch  # same scripts/ directory; one implementation
            if self.cache:
                time.sleep(PAUSE_SECONDS)
            self.cache[path] = fetch(self.base, path)
        return self.cache[path]


def fetch_row(cid, path, status, ctype, ok, detail):
    """One run-file row, cells safe for a markdown table"""
    detail = re.sub(r"\s+", " ", str(detail)).replace("|", "/").strip()[:160]
    return {"id": cid, "path": path, "status": str(status) if status else "-",
            "content type": ctype.split(";")[0].strip() or "-",
            "result": "ok" if ok else "FAIL", "detail": detail}


def site_path(url, base):
    """Path of a site URL, so it can be re-hosted on the base; None if external.
    Staging serves llms.txt with links already on the staging host, so the base's
    own host counts as the site too."""
    parts = urlsplit(url.strip())
    if parts.netloc.lower() not in SITE_HOSTS + (urlsplit(base).netloc.lower(),):
        return None
    return (parts.path or "/") + (f"?{parts.query}" if parts.query else "")


def smoke_rows(fetcher):
    """C rows: every check in check_staging's CHECKS, judged the same way"""
    from check_staging import CHECKS
    rows = []
    for n, (path, types, extra) in enumerate(CHECKS, 1):
        status, ctype, body = fetcher.get(path)
        ok, detail = True, ""
        if status != 200:
            ok, detail = False, f"status {status}" if status else body
        elif ctype.lower().split(";")[0].strip() not in types:
            ok, detail = False, f"expected {' or '.join(types)}"
        elif extra:
            ok, detail = extra(body)
        rows.append(fetch_row(f"C{n}", path, status, ctype, ok, detail))
    return rows


def linked_rows(fetcher, prefix, source, urls):
    """S or L rows: every site URL listed in a deployed file returns 200 on the base"""
    paths = []
    for url in urls:
        path = site_path(url, fetcher.base)
        if path and path not in paths:
            paths.append(path)
    rows = []
    for n, path in enumerate(paths[:MAX_LINKED_URLS], 1):
        try:
            status, ctype, body = fetcher.get(path)
        except ValueError as e:
            rows.append(fetch_row(f"{prefix}{n}", path, None, "", False, e))
            continue
        ok = status == 200
        detail = f"listed in {source}" if ok else (f"listed in {source}, status {status}" if status else body)
        rows.append(fetch_row(f"{prefix}{n}", path, status, ctype, ok, detail))
    if len(paths) > MAX_LINKED_URLS:
        rows.append(fetch_row(f"{prefix}{MAX_LINKED_URLS + 1}", source, None, "", False,
                              f"{len(paths)} URLs listed, only the first {MAX_LINKED_URLS} fetched"))
    return rows


def has_person(data):
    """Does a parsed JSON-LD value carry a node of @type Person"""
    if isinstance(data, list):
        return any(has_person(item) for item in data)
    if not isinstance(data, dict):
        return False
    kind = data.get("@type")
    if kind == "Person" or (isinstance(kind, list) and "Person" in kind):
        return True
    return has_person(data.get("@graph"))


def assert_human_sitemap(body):
    """R1012-4 b: sitemap.xml stays human-only"""
    locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", body)
    agent = [loc for loc in locs if "/for-agents/" in loc]
    if agent:
        return False, f"{len(agent)} /for-agents/ URLs in the human sitemap, first {agent[0]}"
    return bool(locs), f"{len(locs)} URLs, none under /for-agents/" if locs else "no <loc> entries"


def map_ids(body):
    """Section ids in the /ask map, None if it is not a map"""
    try:
        sections = json.loads(body).get("sections")
    except (ValueError, AttributeError):
        return None
    if not isinstance(sections, list):
        return None
    return [str(s.get("id", "")) if isinstance(s, dict) else str(s) for s in sections]


def assert_map_count(body):
    ids = map_ids(body)
    if ids is None:
        return False, "not a JSON map with sections"
    return len(ids) == EXPECTED_SECTIONS, f"{len(ids)} sections, expected {EXPECTED_SECTIONS}"


def assert_map_no_pp(body):
    ids = map_ids(body)
    if ids is None:
        return False, "not a JSON map with sections"
    pp = [i for i in ids if i.startswith("PP.")]
    return (not pp), f"{len(pp)} PP. ids in the map, first {pp[0]}" if pp else "no PP. ids in the map"


def assert_jsonld_person(body):
    blocks = re.findall(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", body, re.S | re.I)
    if not blocks:
        return False, "no JSON-LD block"
    for block in blocks:
        try:
            if has_person(json.loads(block)):
                return True, f"{len(blocks)} JSON-LD block(s), @type Person present"
        except ValueError:
            return False, "JSON-LD block does not parse as JSON"
    return False, f"{len(blocks)} JSON-LD block(s), none with @type Person"


def assert_proof_points(body):
    try:
        data = json.loads(body)
    except ValueError:
        return False, "not JSON"
    rows = data.get("proof_points") if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        return False, "no proof_points rows"
    count = data.get("count") if isinstance(data, dict) else None
    if count is not None and count != len(rows):
        return False, f"{len(rows)} rows but count says {count}"
    return True, f"{len(rows)} rows"


ASSERTIONS = [
    # id, path, assertion on the body
    ("E1", "/sitemap.xml", assert_human_sitemap),
    ("E2", "/ask", assert_map_count),
    ("E3", "/ask", assert_map_no_pp),
    ("E4", "/for-agents/", assert_jsonld_person),
    ("E5", "/for-agents/proof-points.json", assert_proof_points),
]


def assertion_rows(fetcher):
    """E rows: what an agent or crawler depends on beyond a status code"""
    rows = []
    for cid, path, check in ASSERTIONS:
        status, ctype, body = fetcher.get(path)
        if status != 200:
            ok, detail = False, f"status {status}" if status else body
        else:
            ok, detail = check(body)
        rows.append(fetch_row(cid, path, status, ctype, ok, detail))
    return rows


def run_fetch(base):
    """All fetch-based checks against one base URL: list of row dicts"""
    fetcher = FreeFetcher(base)
    rows = smoke_rows(fetcher) + assertion_rows(fetcher)
    status, _, body = fetcher.get("/sitemap-agent.xml")
    if status == 200:
        rows += linked_rows(fetcher, "S", "sitemap-agent.xml", re.findall(r"<loc>\s*(.*?)\s*</loc>", body))
    status, _, body = fetcher.get("/llms.txt")
    if status == 200:
        rows += linked_rows(fetcher, "L", "llms.txt", re.findall(r"\]\((https?://[^)\s]+)\)", body))
    return rows


def format_fetch_run(base, run_date, rows):
    failed = [r for r in rows if r["result"] == "FAIL"]
    lines = [
        f"# Fetch run {run_date}, base {base}",
        "",
        f"Run by `scripts/agent_evals.py fetch` at {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}. "
        "Free plain GETs only: no `/ask?q=`, no brief.",
        "`C` = smoke checks from `scripts/check_staging.py`. `E` = eval assertions. "
        "`S` = a URL in the deployed `sitemap-agent.xml`. `L` = a link in the deployed `llms.txt`. "
        "Production URLs in `S` and `L` are re-hosted on the base.",
        "",
        f"Result: {len(rows) - len(failed)} of {len(rows)} checks passed, {len(failed)} failed.",
        "",
        "| " + " | ".join(FETCH_COLUMNS) + " |",
        "|" + "---|" * len(FETCH_COLUMNS),
    ]
    lines += ["| " + " | ".join(r[c] for c in FETCH_COLUMNS) + " |" for r in rows]
    lines += ["", f"Totals: {len(rows)} checks, {len(rows) - len(failed)} ok, {len(failed)} FAIL"]
    return "\n".join(lines) + "\n"


def cmd_fetch(base, run_date, write):
    if not re.match(r"^https?://[^/]+", base):
        print(f"--base must be an http(s) URL, got {base!r}")
        return 2
    base = base.rstrip("/")
    rows = run_fetch(base)
    text = format_fetch_run(base, run_date, rows)
    print(text, end="")
    if write and all(r["status"] == "-" for r in rows):
        print(f"\nNo response from {base}: run file not written")
    elif write:
        path = os.path.join(RUNS_DIR, f"{run_date}-fetch.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"\nWrote {path}")
    return 1 if any(r["result"] == "FAIL" for r in rows) else 0


def load_fetch_run(path):
    """Read a fetch run file: dict of stable key -> row dict"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    rows = {}
    for cells in table_rows(text):
        if len(cells) == len(FETCH_COLUMNS) and re.match(r"^[CESL]\d+$", cells[0]):
            row = dict(zip(FETCH_COLUMNS, cells))
            # S and L numbers shift when a URL is added, so those rows are keyed by path
            key = row["id"] if row["id"][0] in "CE" else f"{row['id'][0]} {row['path']}"
            rows[key] = row
    return rows


def cmd_fetch_diff(old, new):
    changed = 0
    for key in sorted(set(old) | set(new)):
        before = old[key]["result"] if key in old else None
        after = new[key]["result"] if key in new else None
        if before != after:
            changed += 1
            row = new.get(key) or old[key]
            print(f"{row['id']} {row['path']}: {before} -> {after}")
    print(f"{changed} checks changed")
    return 0


def cmd_diff(old_path, new_path):
    old_fetch, new_fetch = load_fetch_run(old_path), load_fetch_run(new_path)
    if old_fetch and new_fetch:
        return cmd_fetch_diff(old_fetch, new_fetch)
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


def fetch_args(args):
    """Parse `--base <url> [--write] [--date YYYY-MM-DD]`: (base, date, write) or None"""
    base, run_date, write = None, date.today().isoformat(), False
    args = list(args)
    while args:
        flag = args.pop(0)
        if flag == "--write":
            write = True
        elif flag in ("--base", "--date") and args:
            if flag == "--base":
                base = args.pop(0)
            else:
                run_date = args.pop(0)
        else:
            return None
    if not base or not re.match(r"^\d{4}-\d{2}-\d{2}$", run_date):
        return None
    return base, run_date, write


def main():
    args = sys.argv[1:]
    if args and (args[0] == "fetch" or args[0].startswith("--")):
        parsed = fetch_args(args[1:] if args[0] == "fetch" else args)
        if parsed:
            return cmd_fetch(*parsed)
        print(__doc__)
        return 2
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
