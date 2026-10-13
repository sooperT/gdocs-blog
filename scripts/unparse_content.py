#!/usr/bin/env python3
"""Rebuild docs/tombot/tombot-content-v3.md from scripts/parsed_content.json.

Written 2026-10-13 after the private docs tree was lost (a tracked docs symlink
overwrote it on merge). The parsed JSON is tracked and was current, so the
markdown is regenerated from it; parse_content.py on the result must give the
same JSON back (scripts/test_unparse_content.py checks that). HTML comments and
the file header are taken from an older snapshot when one is given.

    python3 scripts/unparse_content.py --out <path> [--snapshot <old markdown>]
"""
import argparse, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARSED = os.path.join(ROOT, 'scripts', 'parsed_content.json')

DEFAULT_HEADER = """# TomBot Content v3

**Purpose:** Consolidated content for TomBot v3. Each section is a canonical answer with a unique ID.

**How to read this document:**
- Each `## ID` section is a canonical answer
- `**Questions that route here:**` shows the question variations that match to this answer
- `[ID]` references after bullets indicate available drill-downs
- `<!-- DRILL-DOWNS: ... -->` lists all child content for this section
- `**Direct answers:**`, `**Attested:**` and `**External:**` are agent-side blocks (parsed into their own fields)
- `**Suggested follow-ups:**` lists tested questions to suggest after this response

**IMPORTANT: No contractions in question variations!**

Regenerated from scripts/parsed_content.json on 2026-10-13 (scripts/unparse_content.py) after the docs tree was lost.

---
"""


def snapshot_layout(path):
    """Header text and {section id: group heading} from an older copy of the file."""
    if not path or not os.path.exists(path):
        return DEFAULT_HEADER, {}
    text = open(path, encoding='utf-8').read()
    first = re.search(r'^# (?!TomBot Content)(.+)$', text, re.M)
    header = text[:first.start()] if first else DEFAULT_HEADER
    groups, current = {}, None
    for line in text.split('\n'):
        if line.startswith('# ') and not line.startswith('# TomBot Content'):
            current = line.rstrip()
        elif line.startswith('## '):
            groups[line[3:].strip()] = current
    return header, groups


def render_section(s):
    out = [f"## {s['id']}", '']
    if s.get('questions'):
        out.append('**Questions that route here:**')
        out += [f'- {q}' for q in s['questions']]
        out.append('')
    if s.get('drill_downs'):
        out.append(f"<!-- DRILL-DOWNS: {', '.join(s['drill_downs'])} -->")
        out.append('')
    out.append(s['content'].rstrip())
    out.append('')
    if s.get('attested'):
        out.append('**Attested:**')
        for a in s['attested']:
            out.append(f"- {a['name']} ({a['title']}, {a['company']}; {a['date']}): \"{a['excerpt']}\" [linkedin]")
        out.append('')
    if s.get('direct_answers'):
        out.append('**Direct answers:**')
        out += [f'- {d}' for d in s['direct_answers']]
        out.append('')
    if s.get('external'):
        out.append('**External:**')
        out += [f"- [{e['label']}]({e['url']})" for e in s['external']]
        out.append('')
    if s.get('follow_ups'):
        out.append('**Suggested follow-ups:**')
        for f in s['follow_ups']:
            out.append(f'- "{f["text"]}" [{f["target"]}]' if f.get('target') else f'- "{f["text"]}"')
        out.append('')
    out.append('---')
    out.append('')
    return '\n'.join(out)


def unparse(sections, header=DEFAULT_HEADER, groups=None):
    groups = groups or {}
    parts = [header.rstrip('\n') + '\n']
    last_group = None
    for s in sections:
        g = groups.get(s['id'], last_group)
        if g and g != last_group:
            parts.append(f'\n{g}\n')
            last_group = g
        parts.append('\n' + render_section(s))
    return ''.join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--snapshot')
    ap.add_argument('--parsed', default=PARSED)
    a = ap.parse_args()
    sections = json.load(open(a.parsed, encoding='utf-8'))
    header, groups = snapshot_layout(a.snapshot)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, 'w', encoding='utf-8').write(unparse(sections, header, groups))
    print(f'wrote {a.out}: {len(sections)} sections')


if __name__ == '__main__':
    main()
