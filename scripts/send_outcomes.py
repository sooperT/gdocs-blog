#!/usr/bin/env python3
"""The outcome line of the whole project, per tagged CV send.

The project's outcome is "a tagged CV send that shows an agent fetch with that
tag, followed by a reply or an interview". S1 to S4 are leading indicators;
this is the lagging one. One read, one markdown table, one row per send tag,
joining three sources:

1. The sends register `for-agents/sends.json` (written by the tracking-links
   skill through `scripts/cv_appendix.py --tag`): one entry per tagged send
   with company, role and date. The tag equals the CV's `utm_source`.
2. The agent log (`agent_fetches`): fetches of the tagged entry file
   (`/for-agents/start/<tag>/` or `/for-agents/start/<tag>.md`, logged with
   `meta.tag`, see `netlify/functions/agent-fetch.js`), plus `/ask` and
   `/ask/brief` rows whose `meta.tag` carries the tag (`ask.js`,
   `calibrate.js`; the key is written by `lib/usage.js`).
3. The human outcome: Tom's pipeline lives in a Miro table (skill
   job-search-ops: Pipeline has Company, Role, Stage, Ball with, Warm route,
   Last action, Next step, Updated; Archive has Company, Role, Outcome, Warm
   route, Notes, Closed). A script cannot call Miro, so it takes an export as
   `--pipeline <csv>` and, when none is given, prints the join with the
   outcome column as "pipeline not supplied".

    python3 scripts/send_outcomes.py --env staging --days 60
    python3 scripts/send_outcomes.py --env production --days 90 --pipeline mockups/pipeline.csv
    python3 scripts/send_outcomes.py --env staging --days 60 --write
        -> docs/agent-readable/evals/runs/<date>-sends.md

Pipeline CSV header (one row per company and role; a header row is required,
column order is free, unknown columns are ignored):

    company,role,stage,outcome,reply,interview,tag

    company    as in Miro (matched case-insensitively against sends.json)
    role       as in Miro (used only to break a tie when one company has two sends)
    stage      Radar / To do / Active / Dying / Dead
    outcome    Archive's Outcome: Rejected / No reply / Tom passed / Role closed / Unknown (blank if live)
    reply      ISO date of the first human reply, blank if none
    interview  ISO date of the first interview, blank if none
    tag        optional: the send tag, which wins over the company match

Outcome per send, in this order: interview (an interview date), reply (a reply
date), rejected (Outcome Rejected), silent (anything else, including No reply,
a live row with no dates, and a send with no pipeline row). "days to reply" is the reply date, or the interview date when there is
no reply date, minus the send date.

Read-only: a single SELECT, with the same --env discipline as every other DB
script (scripts/db_target.py). Privacy as live_report.py: counts and dates
only; no IPs, no referers, no user agent beyond its family name, nothing a
visitor typed. The pipeline file is Tom's own and never leaves the machine;
only company, role and the four outcome words reach the report.
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from live_report import INTERNAL_FAMILIES, ROOT, RUNS_DIR, _table, family, fetch_rows  # noqa: E402

SENDS_PATH = os.path.join(ROOT, "for-agents", "sends.json")
ASK_PATHS = ("/ask", "/ask/brief")
TAG_PATH_RE = re.compile(r"^/for-agents/start/([a-z0-9][a-z0-9-]{0,39})(?:/|\.md)?$")
OUTCOMES = ("interview", "reply", "rejected", "silent")
NOT_SUPPLIED = "pipeline not supplied"


# ---------------------------------------------------------------- sources

def load_sends(path=SENDS_PATH):
    """sends.json -> [{tag, company, role, date}], oldest first. Missing file -> []."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    out = []
    for tag, entry in (data.get("sends") or {}).items():
        out.append({
            "tag": tag,
            "company": entry.get("company") or tag,
            "role": entry.get("role") or "",
            "date": _parse_date(entry.get("date")),
        })
    return sorted(out, key=lambda s: (s["date"] or date.max, s["tag"]))


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def row_tag(row):
    """The send tag a log row carries: meta.tag, else the tagged entry path."""
    meta = row.get("meta") or {}
    if meta.get("tag"):
        return str(meta["tag"])
    m = TAG_PATH_RE.match(row.get("path") or "")
    return m.group(1) if m else None


def load_pipeline(path):
    """CSV -> list of dicts with lowercase keys. None when no path given."""
    if not path:
        return None
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = []
        for raw in reader:
            rows.append({(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()})
    return rows


def match_pipeline(send, pipeline):
    """The pipeline row for a send: by tag when the CSV has one, else by company (and role to break a tie)."""
    if not pipeline:
        return None
    by_tag = [r for r in pipeline if r.get("tag") and r["tag"].lower() == send["tag"].lower()]
    if by_tag:
        return by_tag[0]
    company = (send["company"] or "").lower()
    same = [r for r in pipeline if (r.get("company") or "").lower() == company]
    if len(same) > 1 and send.get("role"):
        narrowed = [r for r in same if (r.get("role") or "").lower() == send["role"].lower()]
        same = narrowed or same
    return same[0] if same else None


def outcome_of(prow):
    """(outcome word, reply date or None) from a pipeline row."""
    if prow is None:
        return "silent", None
    interview = _parse_date(prow.get("interview"))
    reply = _parse_date(prow.get("reply"))
    if interview:
        return "interview", reply or interview
    if reply:
        return "reply", reply
    if (prow.get("outcome") or "").strip().lower() == "rejected":
        return "rejected", None
    return "silent", None


# ---------------------------------------------------------------- join

def _days(later, earlier):
    if later is None or earlier is None:
        return None
    return (later - earlier).days


def _date_of(ts):
    if isinstance(ts, datetime):
        return ts.date()
    return _parse_date(ts)


def join(sends, rows, pipeline, today):
    """Pure: one dict per send tag. Nothing here touches a network."""
    by_tag = {}
    for r in rows:
        t = row_tag(r)
        if t:
            by_tag.setdefault(t, []).append(r)

    out = []
    for s in sends:
        tagged = by_tag.get(s["tag"], [])
        fetches = [r for r in tagged if r["path"] not in ASK_PATHS]
        external = [r for r in fetches if family(r["user_agent"]) not in INTERNAL_FAMILIES]
        dates = sorted(_date_of(r["created_at"]) for r in external)
        first = dates[0] if dates else None
        prow = match_pipeline(s, pipeline)
        outcome, reply_date = outcome_of(prow) if pipeline is not None else (NOT_SUPPLIED, None)
        out.append({
            "tag": s["tag"],
            "company": s["company"],
            "role": s["role"],
            "sent": s["date"],
            "days_since": _days(today, s["date"]),
            "fetches": len(external),
            "internal_fetches": len(fetches) - len(external),
            "first_fetch": first,
            "last_fetch": dates[-1] if dates else None,
            "families": Counter(family(r["user_agent"]) for r in external),
            "asks": sum(1 for r in tagged if r["path"] == "/ask"),
            "briefs": sum(1 for r in tagged if r["path"] == "/ask/brief"),
            "outcome": outcome,
            "days_to_first_fetch": _days(first, s["date"]),
            "days_to_reply": _days(reply_date, s["date"]),
        })
    unknown = sorted(t for t in by_tag if t not in {s["tag"] for s in sends})
    return out, unknown


def median(values):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2


def summary(joined, pipeline_supplied):
    """The three lines under the table, as plain numbers."""
    fetched = [j for j in joined if j["fetches"]]
    unfetched = [j for j in joined if not j["fetches"]]
    replied = lambda j: j["outcome"] in ("reply", "interview")  # noqa: E731
    return {
        "sends": len(joined),
        "sends_with_fetch": len(fetched),
        "fetched_replied": sum(1 for j in fetched if replied(j)) if pipeline_supplied else None,
        "unfetched": len(unfetched),
        "unfetched_replied": sum(1 for j in unfetched if replied(j)) if pipeline_supplied else None,
        "median_days_to_first_fetch": median(j["days_to_first_fetch"] for j in joined),
    }


# ---------------------------------------------------------------- render

def _fmt(value):
    return "-" if value is None else str(value)


def render(joined, unknown, summ, env, days, today, pipeline_supplied, table_note=None):
    L = ["# Send outcomes, %s (%s, last %d days)" % (today, env, days), ""]
    L.append("One row per tagged CV send (`for-agents/sends.json`), joined with the agent log "
             "(`agent_fetches`: the tagged entry file, `/ask` and `/ask/brief` rows with `meta.tag`) "
             "and the pipeline%s. Fetch counts exclude our own probes and shell clients; the bracket is those."
             % ("" if pipeline_supplied else " (not supplied this run: `--pipeline <csv>`, header in `scripts/send_outcomes.py`)"))
    if table_note:
        L.append("")
        L.append("Note: %s." % table_note)
    L.append("")
    rows = []
    for j in joined:
        fam = ", ".join("%s %d" % kv for kv in sorted(j["families"].items(), key=lambda kv: (-kv[1], kv[0]))) or "-"
        fetch_cell = str(j["fetches"]) + (" (+%d internal)" % j["internal_fetches"] if j["internal_fetches"] else "")
        rows.append((j["tag"], j["company"], j["role"], _fmt(j["sent"]), _fmt(j["days_since"]),
                     fetch_cell, _fmt(j["first_fetch"]), _fmt(j["last_fetch"]), fam,
                     j["asks"], j["briefs"], j["outcome"], _fmt(j["days_to_first_fetch"]), _fmt(j["days_to_reply"])))
    L.append(_table(["tag", "company", "role", "sent", "days since", "tagged fetches", "first fetch", "last fetch",
                     "bot families", "/ask", "briefs", "outcome", "days to first fetch", "days to reply"], rows))
    L.append("")
    L.append("1. Tagged sends with any fetch: %d of %d." % (summ["sends_with_fetch"], summ["sends"]))
    if pipeline_supplied:
        L.append("2. Fetched sends that replied: %d of %d; unfetched sends that replied: %d of %d."
                 % (summ["fetched_replied"], summ["sends_with_fetch"], summ["unfetched_replied"], summ["unfetched"]))
    else:
        L.append("2. Fetched sends that replied vs unfetched sends that replied: %s." % NOT_SUPPLIED)
    L.append("3. Median days to first fetch: %s." % (_fmt(summ["median_days_to_first_fetch"]) if summ["median_days_to_first_fetch"] is not None else "no fetches yet"))
    if unknown:
        L.append("")
        L.append("Tags in the log with no entry in sends.json (a retired send, a typo, or a probe): %s." % ", ".join(unknown))
    L.append("")
    return "\n".join(L)


def build_report(rows, env, days, today, pipeline=None, sends=None, table_note=None):
    sends = load_sends() if sends is None else sends
    joined, unknown = join(sends, rows, pipeline, today)
    summ = summary(joined, pipeline is not None)
    return render(joined, unknown, summ, env, days, today, pipeline is not None, table_note=table_note)


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Per tagged CV send: fetches, /ask calls, briefs and the human outcome")
    parser.add_argument("--env", choices=["staging", "production"], required=True, help="which database (scripts/db_target.py)")
    parser.add_argument("--days", type=int, default=90, help="look back this many days in the agent log (default 90)")
    parser.add_argument("--pipeline", help="CSV export of the Miro pipeline (header in the docstring)")
    parser.add_argument("--write", action="store_true", help="write docs/agent-readable/evals/runs/<date>-sends.md instead of stdout")
    args = parser.parse_args()

    import psycopg2
    from db_target import resolve_db

    conn = psycopg2.connect(resolve_db("read agent_fetches from"))
    try:
        rows, note = fetch_rows(conn, args.days)
    finally:
        conn.close()

    pipeline = load_pipeline(args.pipeline)
    today = date.today()
    report = build_report(rows, args.env, args.days, today, pipeline=pipeline, table_note=note)

    if args.write:
        os.makedirs(RUNS_DIR, exist_ok=True)
        out = os.path.join(RUNS_DIR, "%s-sends.md" % today.isoformat())
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(report)
        print("Wrote %s (%d rows read)" % (os.path.relpath(out, ROOT), len(rows)))
    else:
        print(report)


if __name__ == "__main__":
    main()
