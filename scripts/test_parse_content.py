#!/usr/bin/env python3
"""Checks that parse_content lifts the agent-side blocks (Attested, Direct
answers, External) out of `content`, so TomBot chat never sees them
(ruling N1010-6 a), and parses them into their own fields.

    python3 scripts/test_parse_content.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_content import parse_section, parse_content_doc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_FILE = os.path.join(ROOT, 'docs', 'tombot', 'tombot-content-v3.md')

PROSE = 'I did the thing (2020 - 2022).\n\nIt went well.'
RAW = f'''
**Questions that route here:**
- What did you do?

<!-- a comment -->

{PROSE}

**Attested:**
- Ann Example (Director, Innovation, Process (Contract), Acme & Co; 2025-11-05): "She shipped it. Twice." [linkedin]
- Bo Sample (Lead Engineer, ZeroNorth; 2019-10-26): "Both times Tom set a goal." [linkedin]

**Direct answers:**
- Fractional work? Yes.
  product: - | source: TomBot META
- Danish? Not stated.

**External:**
- [Elastic welcomes Opbeat](https://www.elastic.co/blog/welcome-opbeat-to-the-elastic-family)

**Suggested follow-ups:**
- "tell me more" [OTHER.ID]

---
'''

passed = failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f'ok   {name}')
    else:
        failed += 1
        print(f'FAIL {name}')


s = parse_section('TEST.ID', RAW)
check('content is the prose only', s['content'] == PROSE)
for label in ('**Attested:**', '**Direct answers:**', '**External:**', '[linkedin]', 'Ann Example'):
    check(f'content has no {label}', label not in s['content'])
check('two attested entries', len(s['attested']) == 2)
check('attested entry shape', s['attested'][0] == {
    'name': 'Ann Example', 'title': 'Director, Innovation, Process (Contract)', 'company': 'Acme & Co',
    'date': '2025-11-05', 'excerpt': 'She shipped it. Twice.'})
check('direct answers with continuation', s['direct_answers'] == [
    'Fractional work? Yes.\nproduct: - | source: TomBot META', 'Danish? Not stated.'])
check('external entry', s['external'] == [{
    'url': 'https://www.elastic.co/blog/welcome-opbeat-to-the-elastic-family', 'label': 'Elastic welcomes Opbeat'}])
check('follow-ups still parsed', s['follow_ups'] == [{'text': 'tell me more', 'target': 'OTHER.ID'}])

plain = parse_section('PLAIN.ID', f'\n**Questions that route here:**\n- Q\n\n{PROSE}\n')
check('no blocks -> empty lists', (plain['attested'], plain['direct_answers'], plain['external']) == ([], [], []))

try:
    parse_section('BAD.ID', f'{PROSE}\n\n**Attested:**\n- Someone said something\n')
    check('malformed Attested line raises', False)
except ValueError:
    check('malformed Attested line raises', True)

# The real content file: no block text reaches any section's content.
if os.path.exists(CONTENT_FILE):
    chunks = parse_content_doc(CONTENT_FILE)
    leaked = [c['id'] for c in chunks
              if any(x in c['content'] for x in ('**Attested:**', '**Direct answers:**', '**External:**', '[linkedin]'))]
    check('real content: no block in any content', not leaked)
    check('real content: attested sections exist', any(c['attested'] for c in chunks))
    hidden = [c['id'] for c in chunks for a in c['attested'] if a['name'] in ('Martin Baker', 'Paul Hugh Mollin', 'Tristan Slessor')]
    check('real content: no hidden recommender', not hidden)

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
