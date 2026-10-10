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


def view(days):
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv()

    conn = psycopg2.connect(os.environ['NILEDB_URL'])
    cur = conn.cursor()
    cur.execute(SQL, (days,))
    rows = cur.fetchall()
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
        print(f"{fam:<20} {path:<16} {n:>7} {errors[(fam, path)]:>7}")


def main():
    parser = argparse.ArgumentParser(description='View agent-surface fetches by user agent family and path')
    parser.add_argument('-d', '--days', type=int, default=7, help='Look back this many days (default 7)')
    parser.add_argument('--dry-run', action='store_true', help='Print the SQL and exit without touching the DB')
    args = parser.parse_args()

    if args.dry_run:
        print(SQL.strip().replace('%s', str(int(args.days))))
        return
    view(args.days)


if __name__ == '__main__':
    main()
