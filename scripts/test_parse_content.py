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

# Story facets (R1013-2): the route terms a row's facets add for the loader.
sys.path.insert(0, ROOT)
from pylib.story_facets import FACETS, ROW_PRODUCTS, UNPLACED, facet_route_terms, facet_json  # noqa: E402

terms = facet_route_terms([
    {'text': 'Line one.', 'answers': 'growth, activation', 'variants': [{'text': 'Line one, again.'}, {'text': 'Line one.'}]},
    {'text': 'Line two.', 'answers': 'growth, activation', 'variants': []},
    {'text': '', 'answers': None},
])
check('facets: route terms are the line, what it answers and the variants, in order, deduplicated', terms == ['Line one.', 'growth, activation', 'Line one, again.', 'Line two.'])
check('facets: no facets, no terms', facet_route_terms(None) == [] and facet_route_terms([]) == [])
check('facets: every row key has a product to check against', all(k in ROW_PRODUCTS for k in FACETS))
all_facets = [f for v in FACETS.values() for f in v]
check('facets: 165 placed on 32 rows, 4 unplaced (the draft\'s 169; item 47 placed FU1 and FU7)', (len(all_facets), len(FACETS), len(UNPLACED)) == (165, 32, 4))
check('facets: ids unique', len({f['id'] for f in all_facets + UNPLACED}) == len(all_facets) + len(UNPLACED))
check('facets: every one has a line, a CV source and what it answers',
      all(f['text'] and f['source'].startswith('CV ') and f['answers'] for f in all_facets + UNPLACED))
check('facets: every variant has a line and a CV source',
      all(v['text'] and v['source'].startswith('CV ') for f in all_facets for v in f['variants']))
check('facets: the published shape carries the tier and the correction note',
      facet_json(all_facets[0])['tier'] == 'self-reported' and all('edited' in facet_json(f) for f in all_facets if f.get('edited')))
check('R1013-1: Diagnosis App facets say 12, and build, not ship',
      all('10-person' not in f['text'] and '10 person' not in f['text'] and 'ship' not in f['text'].lower() for f in FACETS['R13']))
check('R1013-1: TREAT facets with a team size say 15, never 17', all('17' not in f['text'] for f in FACETS['R15'])
      and any('15' in f['text'] for f in FACETS['R15']))
check('R1013-1: the domain search and the order process keep their facets on their own rows, not split or merged',
      FACETS['R27'] and FACETS['R28'] and {f['id'][:3] for f in FACETS['R27']} == {'F27'} and {f['id'][:3] for f in FACETS['R28']} == {'F28'})

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
