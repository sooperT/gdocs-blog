#!/usr/bin/env python3
"""The day-0 measurement pack (PRD section 11, slice-status 2026-10-13 item 1).

One read, one markdown report, joining the inputs the insights loop names:

1. Agent fetches (`agent_fetches`): counts by path, by bot family, by day,
   plus the distinct referers (query strings already stripped on write).
2. `/ask` and `/ask/brief` usage rows (same table, `meta` JSONB): calls per
   day, by tag, by asker, top sections, null rate, injection flags, brief
   met / partial / not met totals, role shapes.
3. Umami AI referrers through `scripts/stats.mjs` (the /stats tool on the
   main checkout). If it cannot run, that section says why and the report
   continues.
4. S4 "Converts" and the J7 morning view.

    python3 scripts/live_report.py --env staging                 # last 7 days, stdout
    python3 scripts/live_report.py --env production --days 30
    python3 scripts/live_report.py --env staging --days 30 --write
        -> docs/agent-readable/evals/runs/<date>-live.md, with the delta
           against the previous -live.md if one exists

Read-only: a single SELECT. Same --env discipline as every other DB script
(scripts/db_target.py). A missing table or an empty window prints zeros.

Privacy (PRD guardrail 8): no IPs are stored or read; user agents are
reduced to a family name, and anything unrecognised is cut to 60
characters; referers were stripped of their query string on write; nothing
a visitor typed is in the table, and nothing beyond counts, section ids and
fixed-list labels is printed. The asker field is free text from the caller,
so it is bucketed to the three documented values plus "other".
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUNS_DIR = os.path.join(ROOT, "docs", "agent-readable", "evals", "runs")

# ---------------------------------------------------------------- bot families
# Order matters: first match wins. Internal probes and generic clients go
# before the catch-alls so a health run never reads as a crawler.
BOT_FAMILIES = [
    ("OpenAI", r"GPTBot|ChatGPT-User|OAI-SearchBot"),
    ("Anthropic", r"ClaudeBot|Claude-User|Claude-SearchBot|anthropic"),
    ("Perplexity", r"PerplexityBot|Perplexity-User"),
    ("Google", r"Google-Extended|Googlebot|GoogleOther"),
    ("Microsoft", r"bingbot|Copilot|BingPreview|msnbot"),
    ("Apple", r"Applebot"),
    ("Meta", r"meta-externalagent|facebookexternalhit"),
    ("Amazon", r"Amazonbot"),
    ("ByteDance", r"Bytespider"),
    ("CommonCrawl", r"CCBot"),
    ("DuckDuckGo", r"DuckAssistBot|DuckDuckBot"),
    ("internal (tbn-*)", r"^tbn-"),
    ("curl", r"^curl/"),
    ("python", r"python-requests|python-urllib|aiohttp|httpx"),
    ("other bot", r"bot|crawler|spider|fetch"),
    ("browser", r"Mozilla/"),
]

# Named AI crawlers for the S4 leading indicator (PRD J5 done-when).
NAMED_CRAWLERS = ("OpenAI", "Anthropic", "Perplexity", "Google", "Microsoft")
# Our own probes and shell clients: never a convert, whatever they called.
INTERNAL_FAMILIES = ("internal (tbn-*)", "curl", "python", "(empty)")
PATH_TABLE_MAX = 40

# Referrer domains that count as "an AI assistant sent a human here".
AI_REFERRERS = (
    "chat.openai.com", "chatgpt.com", "claude.ai", "perplexity.ai",
    "copilot.microsoft.com", "gemini.google.com",
)
# bing.com only counts when the referrer carries a Copilot marker.
BING_COPILOT = re.compile(r"bing\.com.*(copilot|/chat)", re.IGNORECASE)

ASK_PATHS = ("/ask", "/ask/brief")
ASKERS = ("recruiter-agent", "hiring-manager", "human")
UA_MAX = 60
PRIVATE_PATH = "/for-agents/"


def family(user_agent):
    ua = user_agent or ""
    if not ua:
        return "(empty)"
    for name, pattern in BOT_FAMILIES:
        if re.search(pattern, ua, re.IGNORECASE):
            return name
    return "other"


IPV4_RE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")


def short_ua(user_agent):
    """The only form a raw user agent may ever take in the report: the first
    product token (up to the first space), IPs redacted, at most 60 characters."""
    token = (user_agent or "").strip().split(" ", 1)[0]
    return IPV4_RE.sub("[ip]", token)[:UA_MAX]


def asker_bucket(value):
    if not value:
        return "(none)"
    return value if value in ASKERS else "other"


# ---------------------------------------------------------------- read

SQL = """
    SELECT created_at, path, user_agent, referer, status, meta
    FROM agent_fetches
    WHERE created_at >= NOW() - (%s * INTERVAL '1 day')
    ORDER BY created_at
"""

SQL_NO_META = """
    SELECT created_at, path, user_agent, referer, status, NULL
    FROM agent_fetches
    WHERE created_at >= NOW() - (%s * INTERVAL '1 day')
    ORDER BY created_at
"""


def fetch_rows(conn, days):
    """Rows as dicts. A missing table or meta column is not an error."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT to_regclass('agent_fetches')")
        if cur.fetchone()[0] is None:
            return [], "table agent_fetches does not exist"
        try:
            cur.execute(SQL, (days,))
        except Exception:  # noqa: BLE001  (table created before the meta column)
            conn.rollback()
            cur.execute(SQL_NO_META, (days,))
        rows = [dict(created_at=r[0], path=r[1], user_agent=r[2], referer=r[3], status=r[4], meta=r[5])
                for r in cur.fetchall()]
        return rows, None
    finally:
        cur.close()


# ---------------------------------------------------------------- aggregate

def _day(ts):
    if isinstance(ts, datetime):
        return ts.astimezone(timezone.utc).date().isoformat() if ts.tzinfo else ts.date().isoformat()
    return str(ts)[:10]


def aggregate(rows):
    """Pure: rows in, counts out. Nothing here touches a network."""
    fetches = [r for r in rows if r["path"] not in ASK_PATHS]
    asks = [r for r in rows if r["path"] == "/ask"]
    briefs = [r for r in rows if r["path"] == "/ask/brief"]

    f = {
        "total": len(fetches),
        "by_path": Counter(r["path"] for r in fetches),
        "by_family": Counter(family(r["user_agent"]) for r in fetches),
        "by_family_path": Counter((family(r["user_agent"]), r["path"]) for r in fetches),
        "by_day": Counter(_day(r["created_at"]) for r in fetches),
        "non_200": Counter(family(r["user_agent"]) for r in fetches if r["status"] != 200),
        "referers": Counter(r["referer"] for r in fetches if r["referer"]),
        "other_uas": Counter(short_ua(r["user_agent"]) for r in fetches if family(r["user_agent"]) == "other"),
        "tagged_start": Counter((r["meta"] or {}).get("tag") for r in fetches if (r["meta"] or {}).get("tag")),
        "crawlers_on_agent_index": sorted({family(r["user_agent"]) for r in fetches
                                           if r["path"] == PRIVATE_PATH and family(r["user_agent"]) in NAMED_CRAWLERS}),
    }

    def meta(r):
        return r["meta"] or {}

    ask_sections = Counter(meta(r).get("section") for r in asks if meta(r).get("section"))
    ask_null = sum(1 for r in asks if not meta(r).get("section"))
    flags = Counter(fl for r in asks + briefs for fl in (meta(r).get("flags") or []))

    u = {
        "ask_calls": len(asks),
        "brief_calls": len(briefs),
        "by_day": Counter((_day(r["created_at"]), r["path"]) for r in asks + briefs),
        "by_tag": Counter(meta(r).get("tag") or "(none)" for r in asks + briefs),
        "by_asker": Counter(asker_bucket(meta(r).get("asker")) for r in asks + briefs),
        "by_family": Counter(family(r["user_agent"]) for r in asks + briefs),
        "sections": ask_sections,
        "ask_null": ask_null,
        "ask_null_rate": (ask_null / len(asks)) if asks else 0.0,
        "ask_withheld": sum(int(meta(r).get("withheld") or 0) for r in asks),
        "flags": flags,
        "brief": {
            "requirements": sum(int(meta(r).get("requirements") or 0) for r in briefs),
            "met": sum(int(meta(r).get("met") or 0) for r in briefs),
            "partial": sum(int(meta(r).get("partial") or 0) for r in briefs),
            "not_met": sum(int(meta(r).get("not_met") or 0) for r in briefs),
            "proof_point_rows": sum(int(meta(r).get("proof_point_rows") or 0) for r in briefs),
            "adjacent": sum(int(meta(r).get("adjacent") or 0) for r in briefs),
            "splitter": Counter(meta(r).get("splitter") or "(none)" for r in briefs),
            "facts_not_stated": Counter(x for r in briefs for x in (meta(r).get("facts_not_stated") or []) if x),
        },
        "shapes": {k: Counter(meta(r).get(k) or "unknown" for r in briefs) for k in ("seniority", "function", "sector")},
        "not_met_by_shape": {
            k: Counter() for k in ("seniority", "function", "sector")
        },
        # External callers only (S4): not our health runs, smoke checks or curl.
        "external_brief_calls": sum(1 for r in briefs if family(r["user_agent"]) not in INTERNAL_FAMILIES),
        "external_tagged_calls": sum(1 for r in asks + briefs if meta(r).get("tag") and family(r["user_agent"]) not in INTERNAL_FAMILIES),
    }
    for r in briefs:
        for k in ("seniority", "function", "sector"):
            u["not_met_by_shape"][k][meta(r).get(k) or "unknown"] += int(meta(r).get("not_met") or 0)
    return {"fetches": f, "usage": u}


# ---------------------------------------------------------------- umami

def find_stats_mjs():
    """The /stats tool is untracked on the main checkout; look up the tree."""
    env = os.environ.get("TBN_STATS_MJS")
    if env and os.path.exists(env):
        return env
    d = ROOT
    for _ in range(6):
        candidate = os.path.join(d, "scripts", "stats.mjs")
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def classify_referrers(referrers):
    """Umami referrer rows [{x: domain, y: visits}] -> {domain: visits} for AI sources."""
    ai = Counter()
    for row in referrers or []:
        dom = str(row.get("x") or "").lower()
        n = int(row.get("y") or 0)
        if any(dom == d or dom.endswith("." + d) for d in AI_REFERRERS) or BING_COPILOT.search(dom):
            ai[dom] += n
    return ai


def umami_ai_referrers(days, runner=None):
    """Returns (counter_or_None, reason). Never prints the key; stats.mjs reads it itself."""
    path = find_stats_mjs()
    if not path:
        return None, "scripts/stats.mjs not found on this checkout or its parents (set TBN_STATS_MJS)"
    cmd = ["node", path, "referrers", "--site", "tbn", "--days", str(days), "--json"]
    try:
        if runner is None:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
            out, err, code = proc.stdout, proc.stderr, proc.returncode
        else:
            out, err, code = runner(cmd)
    except FileNotFoundError:
        return None, "node is not installed"
    except subprocess.TimeoutExpired:
        return None, "stats.mjs timed out after 40s"
    if code != 0:
        first = (err or out or "").strip().splitlines()
        return None, "stats.mjs exited %s: %s" % (code, first[0][:120] if first else "no output")
    try:
        data = json.loads(out)
    except ValueError:
        return None, "stats.mjs did not return JSON"
    return classify_referrers(data.get("referrers")), None


# ---------------------------------------------------------------- S4 and J7

def s4_converts(agg, ai_referrers):
    """S4 "Converts" (STATUS.md S1 to S4; PRD J5 leading indicator).

    Counted: AI referrer visits (an assistant sent a human), tagged usage
    calls (an agent that came from a CV send used the endpoints), and brief
    calls (an agent brought a job), external callers only: our own health
    runs, smoke checks and curl probes never count. Leading indicator: named
    crawlers that have fetched /for-agents/ at least once.
    """
    u = agg["usage"]
    tagged_calls = u["external_tagged_calls"]
    ai_visits = sum(ai_referrers.values()) if ai_referrers is not None else None
    return {
        "ai_referrer_visits": ai_visits,
        "tagged_calls": tagged_calls,
        "brief_calls": u["external_brief_calls"],
        "all_brief_calls": u["brief_calls"],
        "ask_calls": u["ask_calls"],
        "converts": (ai_visits or 0) + tagged_calls + u["external_brief_calls"],
        "crawlers_on_agent_index": agg["fetches"]["crawlers_on_agent_index"],
        "crawlers_named": len(NAMED_CRAWLERS),
    }


def numbers(agg, s4):
    """The flat set of numbers the delta compares."""
    f, u = agg["fetches"], agg["usage"]
    return {
        "fetches": f["total"],
        "ask_calls": u["ask_calls"],
        "brief_calls": u["brief_calls"],
        "ask_null": u["ask_null"],
        "injection_flags": u["flags"].get("injection_pattern", 0),
        "brief_met": u["brief"]["met"],
        "brief_partial": u["brief"]["partial"],
        "brief_not_met": u["brief"]["not_met"],
        "ai_referrer_visits": s4["ai_referrer_visits"] if s4["ai_referrer_visits"] is not None else 0,
        "s4_converts": s4["converts"],
        "crawlers_on_agent_index": len(s4["crawlers_on_agent_index"]),
    }


# ---------------------------------------------------------------- render

def _table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    if not rows:
        out.append("| " + " | ".join(["(none)"] + [""] * (len(headers) - 1)) + " |")
    return "\n".join(out)


def _counter_rows(counter, limit=None):
    items = sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))
    return [(k, v) for k, v in (items[:limit] if limit else items)]


def render(agg, ai_referrers, ai_reason, s4, env, days, today, table_note=None, previous=None):
    f, u = agg["fetches"], agg["usage"]
    L = []
    L.append("# Live report %s, %s, last %d days" % (today, env, days))
    L.append("")
    L.append("Run by `scripts/live_report.py --env %s --days %d` at %s. Read-only. "
             "Counts, section ids and fixed-list labels only (PRD guardrail 8)." % (env, days, datetime.now().strftime("%Y-%m-%d %H:%M")))
    if table_note:
        L.append("")
        L.append("Note: %s. Zeros below." % table_note)

    # 1. fetches
    L.append("")
    L.append("## 1. Agent fetches: %d" % f["total"])
    L.append("")
    L.append("### By bot family")
    L.append("")
    L.append(_table(["family", "fetches", "non-200"], [(k, v, f["non_200"].get(k, 0)) for k, v in _counter_rows(f["by_family"])]))
    if f["other_uas"]:
        L.append("")
        L.append("Unrecognised user agents (first %d characters): " % UA_MAX
                 + "; ".join("`%s` (%d)" % (k, v) for k, v in _counter_rows(f["other_uas"], 10)))
    L.append("")
    L.append("### By path")
    L.append("")
    L.append(_table(["path", "fetches"], _counter_rows(f["by_path"], PATH_TABLE_MAX)))
    if len(f["by_path"]) > PATH_TABLE_MAX:
        L.append("")
        L.append("Top %d of %d paths." % (PATH_TABLE_MAX, len(f["by_path"])))
    L.append("")
    L.append("### By family and path (top 25)")
    L.append("")
    L.append(_table(["family", "path", "fetches"], [(k[0], k[1], v) for k, v in _counter_rows(f["by_family_path"], 25)]))
    L.append("")
    L.append("### By day")
    L.append("")
    L.append(_table(["day", "fetches"], sorted(f["by_day"].items())))
    L.append("")
    L.append("### Referers (origin and path, query strings never stored)")
    L.append("")
    L.append(_table(["referer", "fetches"], _counter_rows(f["referers"])))
    if f["tagged_start"]:
        L.append("")
        L.append("Tagged entry-file fetches: " + ", ".join("`%s` %d" % (k, v) for k, v in _counter_rows(f["tagged_start"])))

    # 2. usage
    L.append("")
    L.append("## 2. /ask and /ask/brief usage: %d calls (%d ask, %d brief)" % (u["ask_calls"] + u["brief_calls"], u["ask_calls"], u["brief_calls"]))
    L.append("")
    L.append("### Calls per day")
    L.append("")
    days_seen = sorted({d for d, _ in u["by_day"]})
    L.append(_table(["day", "/ask", "/ask/brief"], [(d, u["by_day"].get((d, "/ask"), 0), u["by_day"].get((d, "/ask/brief"), 0)) for d in days_seen]))
    L.append("")
    L.append("### By tag")
    L.append("")
    L.append(_table(["tag", "calls"], _counter_rows(u["by_tag"])))
    L.append("")
    L.append("### By asker (bucketed to the documented values)")
    L.append("")
    L.append(_table(["asker", "calls"], _counter_rows(u["by_asker"])))
    L.append("")
    L.append("### By caller family")
    L.append("")
    L.append(_table(["family", "calls"], _counter_rows(u["by_family"])))
    L.append("")
    L.append("### Top sections (/ask, first match)")
    L.append("")
    L.append(_table(["section", "calls"], _counter_rows(u["sections"], 20)))
    L.append("")
    L.append("Null answers: %d of %d /ask calls (%.0f%%). Withheld fragments: %d. Injection flags: %d."
             % (u["ask_null"], u["ask_calls"], u["ask_null_rate"] * 100, u["ask_withheld"], u["flags"].get("injection_pattern", 0)))
    L.append("")
    L.append("### Briefs")
    L.append("")
    b = u["brief"]
    L.append(_table(["requirements", "met", "partial", "not met", "proof-point rows", "adjacent"],
                    [(b["requirements"], b["met"], b["partial"], b["not_met"], b["proof_point_rows"], b["adjacent"])]))
    L.append("")
    L.append("Splitter: " + (", ".join("%s %d" % kv for kv in _counter_rows(b["splitter"])) or "(none)")
             + ". Facts not stated: " + (", ".join("%s %d" % kv for kv in _counter_rows(b["facts_not_stated"])) or "(none)") + ".")
    L.append("")
    L.append("### Role shapes (briefs; not-met rows per shape)")
    L.append("")
    shape_rows = []
    for k in ("seniority", "function", "sector"):
        for label, n in _counter_rows(u["shapes"][k]):
            shape_rows.append((k, label, n, u["not_met_by_shape"][k].get(label, 0)))
    L.append(_table(["axis", "label", "briefs", "not met"], shape_rows))

    # 3. umami
    L.append("")
    L.append("## 3. AI referrers (Umami, takenbyninjas.com)")
    L.append("")
    if ai_referrers is None:
        L.append("not available: %s" % ai_reason)
    else:
        L.append(_table(["referrer", "visits"], _counter_rows(ai_referrers)))
        L.append("")
        L.append("Total AI referrer visits: %d." % sum(ai_referrers.values()))

    # 4. S4 and J7
    L.append("")
    L.append("## 4. S4 Converts")
    L.append("")
    L.append("Definition (STATUS.md S1 to S4; PRD J5 done-when as leading indicator): AI referrer visits "
             "+ tagged endpoint calls (an agent that came from a CV send) + brief calls (an agent brought a job), "
             "external callers only (our health runs, smoke checks and curl never count). "
             "Leading indicator: named crawlers that fetched `/for-agents/` at least once.")
    L.append("")
    ai_cell = "n/a" if s4["ai_referrer_visits"] is None else str(s4["ai_referrer_visits"])
    L.append(_table(["S4 converts", "AI referrer visits", "tagged calls (external)", "brief calls (external of all)", "crawlers on /for-agents/"],
                    [(s4["converts"], ai_cell, s4["tagged_calls"], "%d of %d" % (s4["brief_calls"], s4["all_brief_calls"]),
                      "%d of %d%s" % (len(s4["crawlers_on_agent_index"]), s4["crawlers_named"],
                                      (" (" + ", ".join(s4["crawlers_on_agent_index"]) + ")") if s4["crawlers_on_agent_index"] else ""))]))
    L.append("")
    L.append("## 5. J7: Tom, in the morning")
    L.append("")
    top_sections = ", ".join("%s %d" % kv for kv in _counter_rows(u["sections"], 5)) or "(none)"
    crawlers = ", ".join("%s %d" % kv for kv in _counter_rows(Counter({k: v for k, v in f["by_family"].items() if k in NAMED_CRAWLERS}))) or "(none)"
    not_met_cluster = ", ".join("%s %d" % kv for kv in _counter_rows(
        Counter({"%s/%s" % (k, l): n for k in ("function", "sector") for l, n in u["not_met_by_shape"][k].items() if n}), 5)) or "(none)"
    L.append(_table(["J7 asks", "answer"], [
        ("Who asked what", "%d /ask calls, %d null; top sections: %s" % (u["ask_calls"], u["ask_null"], top_sections)),
        ("Which crawlers came", crawlers),
        ("Briefs calibrated", "%d briefs, %d requirements: %d met, %d partial, %d not met" % (u["brief_calls"], b["requirements"], b["met"], b["partial"], b["not_met"])),
        ("Where not met clusters", not_met_cluster),
        ("AI referrers", ai_cell if ai_referrers is not None else "not available"),
        ("Send tags seen", ", ".join("%s %d" % kv for kv in _counter_rows(u["by_tag"]) if kv[0] != "(none)") or "(none)"),
    ]))

    # delta
    if previous is not None:
        L.append("")
        L.append("## 6. Delta against %s" % previous["name"])
        L.append("")
        cur = numbers(agg, s4)
        rows = []
        for k, v in cur.items():
            old = previous["numbers"].get(k)
            if old is None:
                rows.append((k, "n/a", v, "new"))
            else:
                d = v - old
                rows.append((k, old, v, ("%+d" % d) if d else "0"))
        L.append(_table(["number", "previous", "now", "delta"], rows))

    L.append("")
    L.append("<!-- live-numbers %s -->" % json.dumps(numbers(agg, s4), sort_keys=True))
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------- delta files

NUMBERS_RE = re.compile(r"<!-- live-numbers (\{.*?\}) -->")


def previous_report(runs_dir, today):
    """The most recent <date>-live.md before today, with its numbers block."""
    if not os.path.isdir(runs_dir):
        return None
    names = sorted(n for n in os.listdir(runs_dir) if n.endswith("-live.md") and n < "%s-live.md" % today)
    for name in reversed(names):
        with open(os.path.join(runs_dir, name), encoding="utf-8") as fh:
            m = NUMBERS_RE.search(fh.read())
        if m:
            try:
                return {"name": name, "numbers": json.loads(m.group(1))}
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------- main

def build_report(rows, env, days, today, table_note=None, ai_result=None, runs_dir=RUNS_DIR):
    agg = aggregate(rows)
    ai_referrers, ai_reason = ai_result if ai_result is not None else (None, "not requested")
    s4 = s4_converts(agg, ai_referrers)
    previous = previous_report(runs_dir, today)
    return render(agg, ai_referrers, ai_reason, s4, env, days, today, table_note=table_note, previous=previous)


def main():
    parser = argparse.ArgumentParser(description="One markdown read of the agent side: fetches, /ask usage, AI referrers, S4, J7")
    parser.add_argument("--env", choices=["staging", "production"], required=True, help="which database (scripts/db_target.py)")
    parser.add_argument("--days", type=int, default=7, help="look back this many days (default 7)")
    parser.add_argument("--write", action="store_true", help="write docs/agent-readable/evals/runs/<date>-live.md instead of stdout")
    parser.add_argument("--no-umami", action="store_true", help="skip the Umami call")
    args = parser.parse_args()

    import psycopg2
    sys.path.insert(0, HERE)
    from db_target import resolve_db

    conn = psycopg2.connect(resolve_db("read agent_fetches from"))
    try:
        rows, note = fetch_rows(conn, args.days)
    finally:
        conn.close()

    ai_result = (None, "skipped (--no-umami)") if args.no_umami else umami_ai_referrers(args.days)
    today = date.today().isoformat()
    report = build_report(rows, args.env, args.days, today, table_note=note, ai_result=ai_result)

    if args.write:
        os.makedirs(RUNS_DIR, exist_ok=True)
        out = os.path.join(RUNS_DIR, "%s-live.md" % today)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(report)
        print("Wrote %s (%d rows read)" % (os.path.relpath(out, ROOT), len(rows)))
    else:
        print(report)


if __name__ == "__main__":
    main()
