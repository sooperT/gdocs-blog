#!/usr/bin/env python3
"""View agent-surface fetches (PRD D5 / W2.5): which crawlers fetched which
agent pages over the last N days. Read-only (a single SELECT).

    python3 scripts/view_agent_fetches.py            # last 7 days
    python3 scripts/view_agent_fetches.py -d 30
    python3 scripts/view_agent_fetches.py --dry-run  # print the SQL, no DB

Needs the agent_fetches table (scripts/setup_agent_fetches.py).
"""

import argparse
import os
import re
from collections import Counter

# Order matters: first match wins. Generic browsers go last.
UA_FAMILIES = [
    ('GPTBot', r'GPTBot'),
    ('OAI-SearchBot', r'OAI-SearchBot'),
    ('ChatGPT-User', r'ChatGPT-User'),
    ('ClaudeBot', r'ClaudeBot'),
    ('Claude-User', r'Claude-User'),
    ('Claude-SearchBot', r'Claude-SearchBot'),
    ('anthropic-ai', r'anthropic-ai'),
    ('PerplexityBot', r'PerplexityBot'),
    ('Perplexity-User', r'Perplexity-User'),
    ('Google-Extended', r'Google-Extended'),
    ('Googlebot', r'Googlebot'),
    ('Bingbot', r'bingbot'),
    ('Applebot', r'Applebot'),
    ('Bytespider', r'Bytespider'),
    ('CCBot', r'CCBot'),
    ('meta-externalagent', r'meta-externalagent'),
    ('Amazonbot', r'Amazonbot'),
    ('DuckAssistBot', r'DuckAssistBot'),
    ('Exa', r'\bExa\b'),
    ('curl', r'^curl/'),
    ('python', r'python-requests|python-urllib|aiohttp|httpx'),
    ('other bot', r'bot|crawler|spider|fetch'),
    ('browser', r'Mozilla/'),
]


def family(user_agent):
    ua = user_agent or ''
    if not ua:
        return '(empty)'
    for name, pattern in UA_FAMILIES:
        if re.search(pattern, ua, re.IGNORECASE):
            return name
    return 'other'


SQL = '''
    SELECT path, user_agent, status, COUNT(*) AS n
    FROM agent_fetches
    WHERE created_at >= NOW() - (%s * INTERVAL '1 day')
    GROUP BY path, user_agent, status
'''

# Usage rows with meta (2026-10-12): /ask, /ask/brief and tagged start fetches.
SQL_META = '''
    SELECT created_at, path, meta
    FROM agent_fetches
    WHERE created_at >= NOW() - (%s * INTERVAL '1 day') AND meta IS NOT NULL
    ORDER BY created_at DESC
    LIMIT 200
'''


def view(days):
    import psycopg2
    from db_target import resolve_db

    conn = psycopg2.connect(resolve_db('read agent_fetches from'))
    cur = conn.cursor()
    cur.execute(SQL, (days,))
    rows = cur.fetchall()
    try:
        cur.execute(SQL_META, (days,))
        meta_rows = cur.fetchall()
    except Exception:  # noqa: BLE001  (table without the meta column)
        conn.rollback()
        meta_rows = []
    cur.close()
    conn.close()

    if not rows:
        print(f"No agent fetches in the last {days} days.")
        return

    counts = Counter()
    errors = Counter()
    for path, ua, status, n in rows:
        key = (family(ua), path)
        counts[key] += n
        if status != 200:
            errors[key] += n

    total = sum(counts.values())
    print(f"Agent fetches, last {days} days: {total}\n")
    print(f"{'FAMILY':<20} {'PATH':<16} {'FETCHES':>7} {'NON-200':>7}")
    for (fam, path), n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"{fam:<20} {path:<40} {n:>7} {errors[(fam, path)]:>7}")

    if meta_rows:
        tags = Counter()
        asks = Counter()
        print(f"\nUsage with meta (newest first, {len(meta_rows)} rows): tag | path | counts")
        for created, path, meta in meta_rows:
            m = meta or {}
            tag = m.get('tag') or '-'
            tags[tag] += 1
            asks[path] += 1
            if path == '/ask/brief':
                detail = (f"req {m.get('requirements')} met {m.get('met')} partial {m.get('partial')} not_met {m.get('not_met')} "
                          f"star {m.get('proof_point_rows')} adj {m.get('adjacent')} | {m.get('seniority')}/{m.get('function')}/{m.get('sector')} | asker {m.get('asker') or '-'}")
            elif path == '/ask':
                detail = f"section {m.get('section') or 'none'} matches {m.get('matches')} q_len {m.get('query_length')} | asker {m.get('asker') or '-'}"
            else:
                detail = ''
            print(f"  {created:%Y-%m-%d %H:%M}  {tag:<14} {path:<32} {detail}")
        print("\nBy tag: " + ', '.join(f"{t}: {n}" for t, n in tags.most_common()))
        print("By path: " + ', '.join(f"{p}: {n}" for p, n in asks.most_common()))


def main():
    parser = argparse.ArgumentParser(description='View agent-surface fetches by user agent family and path')
    parser.add_argument('--env', choices=['staging', 'production'], required=True, help='which database (scripts/db_target.py)')
    parser.add_argument('-d', '--days', type=int, default=7, help='Look back this many days (default 7)')
    parser.add_argument('--dry-run', action='store_true', help='Print the SQL and exit without touching the DB')
    args = parser.parse_args()

    if args.dry_run:
        print(SQL.strip().replace('%s', str(int(args.days))))
        return
    view(args.days)


if __name__ == '__main__':
    main()
