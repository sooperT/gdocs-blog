#!/usr/bin/env python3
"""
Measure /ask/brief on the nine real job ads (items 24, 31, 32).

Posts each JD in docs/agent-readable/evals/health/jds/*.txt (the ads, not the
application texts) to <base>/ask/brief and prints one line per ad: rows,
met / partial / not met, how many rows came from STAR rows, how many evidence
queries ran. Writes a markdown table to evals/health/runs/<date>-brief.md
when --write is given. Paid: one Claude splitter call, one evidence-queries
call and up to 3 Voyage embeddings per requirement, per ad.

Usage:
    python3 scripts/measure_brief.py --base https://staging--spectacular-licorice-ac27b4.netlify.app [--write]
"""
import argparse
import datetime
import glob
import json
import os
import sys
import urllib.request

JDS = 'docs/agent-readable/evals/health/jds'


def post_brief(base, text):
    req = urllib.request.Request(f'{base}/ask/brief', data=text.encode('utf-8'), method='POST',
                                 headers={'content-type': 'text/plain', 'user-agent': 'tbn-measure-brief/1.0'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    files = sorted(f for f in glob.glob(f'{JDS}/*.txt') if 'application' not in os.path.basename(f))
    lines = ['| Ad | Rows | Met | Partial | Not met | From STAR rows |', '|---|---|---|---|---|---|']
    totals = dict(rows=0, met=0, partial=0, not_met=0, pp=0)
    for f in files:
        name = os.path.basename(f).removesuffix('.txt')
        try:
            d = post_brief(a.base, open(f, encoding='utf-8').read())
        except Exception as e:  # noqa: BLE001
            print(f'{name}: ERROR {e}')
            lines.append(f'| {name} | error | | | | |')
            continue
        rows = d.get('rows', [])
        if not rows and d.get('error'):
            print(f'{name}: {d["error"]}')
            lines.append(f'| {name} | {d["error"]} | | | | |')
            continue
        c = dict(rows=len(rows), met=sum(r['met'] == 'met' for r in rows), partial=sum(r['met'] == 'partial' for r in rows),
                 not_met=sum(r['met'] == 'not met' for r in rows), pp=sum(r.get('kind') == 'proof-point' for r in rows))
        for k in totals:
            totals[k] += c[k]
        print(f'{name:48s} rows {c["rows"]:2d}  met {c["met"]:2d}  partial {c["partial"]:2d}  not met {c["not_met"]:2d}  star {c["pp"]:2d}')
        lines.append(f'| {name} | {c["rows"]} | {c["met"]} | {c["partial"]} | {c["not_met"]} | {c["pp"]} |')
    lines.append(f'| **total** | {totals["rows"]} | {totals["met"]} | {totals["partial"]} | {totals["not_met"]} | {totals["pp"]} |')
    print(f'{"total":48s} rows {totals["rows"]:2d}  met {totals["met"]:2d}  partial {totals["partial"]:2d}  not met {totals["not_met"]:2d}  star {totals["pp"]:2d}')
    if a.write:
        os.makedirs('docs/agent-readable/evals/health/runs', exist_ok=True)
        out = f'docs/agent-readable/evals/health/runs/{datetime.date.today().isoformat()}-brief.md'
        with open(out, 'a', encoding='utf-8') as fh:
            fh.write(f'\n## {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")} {a.base}\n\n' + '\n'.join(lines) + '\n')
        print(f'written: {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
