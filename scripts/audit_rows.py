#!/usr/bin/env python3
"""Audit the STAR rows for the stitching Tom caught by eye on 2026-10-13 (R1013-21 to -23).

Flags, per row in generate_agent_page.PROOF_POINTS (verbatim cells, before tightening):
  STITCH   situation/task/action and result cite different sections (a CV bullet
           borrowed as a result, or a description borrowed from another line)
  THIN     situation or task is None ("not yet stated" on the page)
  SHARED   two rows of one product carry results that overlap heavily (variants are
           allowed to share a result, R1013-23; listed so Tom can say which are one story)
  DESC     the description cell cites a different section from the rest of the row
Read-only. Exit 0 always; the report is for Tom.
"""
import re
import sys
from collections import defaultdict

sys.path.insert(0, '.')
import generate_agent_page as g  # noqa: E402

STAR = ('situation', 'task', 'action', 'result')


def parent(sid):
    return sid.split('.')[0] if sid else None


def words(t):
    return set(re.findall(r"[a-z0-9%]+", (t or '').lower())) - {'the', 'a', 'and', 'of', 'in', 'to', 'for', 'our', 'first'}


flags = []
by_product = defaultdict(list)
for n, row in enumerate(g.PROOF_POINTS, 1):
    name = f"{n:02d} {row['product'][0]} ({row['role'][0]})"
    cells = {k: row.get(k) for k in STAR}
    secs = {k: v[1] for k, v in cells.items() if v}
    thin = [k for k in ('situation', 'task') if not cells[k]]
    if thin:
        flags.append((n, 'THIN', f"{name}: {', '.join(thin)} not yet stated"))
    # A story and its own drill-down (NOVO.R1 and NOVO.R1.TRANSFORM) are one family; only
    # cells from different families count as stitched.
    fams = {k: parent(v) for k, v in secs.items()}
    if len(set(fams.values())) > 1:
        sta = {fams[k] for k in ('situation', 'task', 'action') if k in fams}
        res = fams.get('result')
        if res and res not in sta:
            flags.append((n, 'STITCH', f"{name}: result cites {secs['result']}, the story cites {', '.join(sorted(sta))}"))
        else:
            flags.append((n, 'STITCH', f"{name}: situation/task/action cite {', '.join(sorted(set(secs.values())))}"))
    d = row.get('desc')
    if d and secs and d[1] not in set(secs.values()) and parent(d[1]) != parent(next(iter(secs.values()))):
        flags.append((n, 'DESC', f"{name}: description cites {d[1]}, the row cites {', '.join(sorted(set(secs.values())))}"))
    if cells['result']:
        by_product[row['product'][0]].append((n, cells['result'][0]))

for product, rows in by_product.items():
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = words(rows[i][1]), words(rows[j][1])
            if a and b and len(a & b) / min(len(a), len(b)) >= 0.5:
                flags.append((rows[i][0], 'SHARED', f"{product}: rows {rows[i][0]:02d} and {rows[j][0]:02d} share a result: "
                              f"\"{rows[i][1][:60]}\" / \"{rows[j][1][:60]}\""))

flags.sort()
print(f"{len(g.PROOF_POINTS)} rows, {len(flags)} flags\n")
for _, kind, text in flags:
    print(f"{kind:7s} {text}")
