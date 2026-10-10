#!/usr/bin/env python3
"""
Generate the facts page for AI agents at /about/agent/

Reads TomBot content (docs/tombot/tombot-content-v3.md) and writes
about/agent/index.html. Every fact on the page is a verbatim line from
a TomBot section, shown with its section id. The generator fails if a
configured line is no longer in its section, so content drift breaks
the build instead of the page.

Usage:
    python3 generate_agent_page.py
"""

import json
import os
import re
import sys
from html import escape as _escape

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
from parse_content import parse_content_doc  # noqa: E402
from pylib.templates import html_head, site_header, site_nav, site_footer  # noqa: E402

CONTENT_FILE = 'docs/tombot/tombot-content-v3.md'
OUTPUT_FILE = 'about/agent/index.html'

TITLE = 'Tom Stenson, product, Copenhagen: facts for agents'
META_DESC_PREFIX = 'Tom Stenson, product, Copenhagen: '
META_DESC_LINE = ('META', "I'm now a product janitor for hire - available for fractional & interim "
                          "product management work, and open to the right permanent role.")

PAGE_STYLE = '''<style>
        /* Agent page (D7): plain monospace body, no CRT effects */
        body::before, body::after { content: none; }
        .crt-overlay { display: none; }
        .agent-page { font-family: ui-monospace, Menlo, Consolas, 'Courier New', monospace; font-size: 16px; }
        .agent-page h1 { font-size: 1.5em; margin: 1em 0 0.5em; }
        .agent-page h2 { font-size: 1.2em; margin: 2.4em 0 0.8em; }
        .agent-page h1, .agent-page h2 { text-shadow: none; }
        .agent-page dl { margin: 0; }
        .agent-page dt { font-weight: bold; margin-top: 1em; }
        .agent-page dd { margin: 0.2em 0 0 1.5em; }
        .agent-page cite { font-style: normal; opacity: 0.75; white-space: nowrap; }
        .agent-page .table-wrap { overflow-x: auto; }
        .agent-page table { margin: 0; font-size: 15px; }
        .agent-page th, .agent-page td { padding: 6px 8px; vertical-align: top; }
    </style>'''

# JSON-LD schema.org/Person (W1.3). Only name, givenName and familyName:
# the other name forms (D3) wait on a source and decision N1010-2.
PAGE_URL = 'https://takenbyninjas.com/about/agent/'
LINKEDIN_URL = 'https://www.linkedin.com/in/tomstenson/'
# (section id, verbatim phrase): role phrase quoted in the proof points table
JOB_TITLE = ('NOVO.R1', 'Product Manager')
# (section id, verbatim phrases)
KNOWS_ABOUT = ('META.COMPETENCIES', [
    'Product Management',
    'Growth',
    'Discovery & Incubation',
    'Strategic Partnership',
    'Informal leadership',
    'Prototyping',
    'coaching',
    'agile',
])

# Who: (term, section id, verbatim line or list of lines)
WHO = [
    ('Name', None, 'Tom Stenson'),
    ('Summary', 'META', "I think in systems and I ship things. I've been doing both for 20 years "
                        "across product, growth and marketing."),
    ('Location', 'META.LOCATION', 'British, living in Copenhagen since 2010. I have Danish permanent '
                                  'residency, so no work visa is required.'),
    ('Role shapes', 'META.LOOKING', "I'm available for fractional & interim product management work, "
                                    "also open to the right permanent role."),
    ('Services', 'META.SERVICES', [
        'Taking an idea from 0 to shipped product.',
        'Turning around an underperforming product, team or initiative.',
        "Addressing complex / critical initiatives that no-one else can get moving.",
        'Scaling your team - maturing product ops & structuring better ways of working.',
        'Creating growth.',
    ]),
]

# Proof points: each cell is (verbatim text, section id it is quoted from).
# Strength is a label, not a quote: Led only where the section says so plainly.
PROOF_POINTS = [
    {
        'product': ('Wegovycare', 'NOVO.R1'),
        'role': ('Senior Product Manager at Novo Nordisk', 'NOVO.R1'),
        'outcome': ('Achieved 10% penetration in our first national market', 'NOVO.R1'),
        'year': ('Mar 2020 - Feb 2022', 'NOVO.R1'),
        'strength': ('Led', 'NOVO.R1', 'I led the full product lifecycle end to end'),
    },
    {
        'product': ('GenAI proof of concept for automating compliance reviews', 'NOVO.R2'),
        'role': ('Associate Product Director at Novo Nordisk', 'NOVO.R2'),
        'outcome': ('the proof of concept showed a clear path to dramatically faster release cycles',
                    'NOVO.R2.GENAI'),
        'year': ('Feb 2022 - 2026', 'NOVO.R2'),
        'strength': ('Led', 'NOVO.R2', 'Pitched and built a GenAI proof of concept'),
    },
    {
        'product': ('TREAT', 'LEO.R1'),
        'role': ('PM/GM', 'LEO.R1'),
        'outcome': ('Halved customer acquisition costs, increased customer activation by 7x', 'LEO.R1'),
        'year': ('Nov 2016 - Aug 2017', 'LEO.R1'),
        'strength': ('Led', 'LEO.R1.TURNAROUND',
                     'it was proposed I become the lead with them reporting to me'),
    },
    {
        'product': ('a prototype diagnosis app using machine learning', 'LEO.R3'),
        'role': ('PM/GM at LEO Innovation Lab', 'LEO.R3'),
        'outcome': ('Achieved >80% accuracy across 3 skin conditions', 'LEO.R3'),
        'year': ('Nov 2018 - Jan 2020', 'LEO.R3'),
        'strength': ('Led', 'LEO.R3', 'leading a 10-person team'),
    },
    {
        'product': ('Opbeat', 'OPBEAT'),
        'role': ('Head of Marketing', 'OPBEAT'),
        'outcome': ('Trebled traffic and sign-ups in 12 months', 'OPBEAT'),
        'year': ('2014-2016', 'META.JOBS'),
        'strength': ('Led', 'OPBEAT',
                     'I joined as Head of Marketing and built the brand, marketing strategy, team and channels'),
    },
    {
        'product': ('EuroDNS', 'EURODNS'),
        'role': ('Marketing Director', 'EURODNS'),
        'outcome': ('reversed the decline, doubled organic traffic, halved bounce rate', 'EURODNS.R1.TURNAROUND'),
        'year': ('2013-2014', 'META.JOBS'),
        'strength': ('Led', 'EURODNS.R1.TURNAROUND', 'I restructured the marketing department'),
    },
]

# Behavioural facts: (term, section id, verbatim line)
BEHAVIOUR = [
    ('Motivation', 'META.COMPASS', 'My compass is simple: impact, learning, and fun.'),
    ('Approach', 'TQ.APPROACH', "It's about doing whatever's needed to find and follow the opportunity."),
    ('Approach', 'TQ.APPROACH', 'When working on something new, I usually start from first principles.'),
    ('Problems he looks for', 'META.LOOKING', "I like challenging product problems with a big upside - the kind "
                                             "where there's no playbook and you have to figure it out."),
    ('Working setup', 'TQ.SETUP', 'Flexible - it depends on the organisational culture.'),
    ('Working setup', 'TQ.SETUP', "I've successfully worked remotely and managed teams across countries "
                                  "(UK→US, DK→Luxembourg, DK→Romania)."),
    ('As a colleague', 'META.COLLEAGUE', 'I asked a former colleague this once, and she said '
                                         '"kind, caring and fun."'),
    ('As a colleague', 'META.COLLEAGUE', 'People tend to come to me when they want to spar on tough '
                                         'problems or think through something messy.'),
]


def escape(text):
    """Escape body text, leaving quotes and apostrophes readable in the raw HTML."""
    return _escape(text, quote=False)


def load_sections():
    """Section id -> answer text, with inline [SECTION.ID] routing tags removed."""
    sections = {}
    for s in parse_content_doc(CONTENT_FILE):
        sections[s['id']] = re.sub(r' ?\[[A-Z][A-Z0-9_.]+\]', '', s['content'])
    return sections


def check(sections, section_id, text):
    """Fail loudly if a quoted line is no longer verbatim in its section."""
    if section_id is None:
        return
    if section_id not in sections:
        sys.exit(f'✗ Section {section_id} not found in {CONTENT_FILE}')
    if text not in sections[section_id]:
        sys.exit(f'✗ Not verbatim in {section_id}: {text!r}')


def cite(*section_ids):
    ids = ', '.join(dict.fromkeys(section_ids))
    return f'<cite>TomBot {escape(ids)}</cite>'


def build_who(sections):
    lines = ['        <h2 id="who">Who</h2>', '        <dl>']
    for term, sid, value in WHO:
        lines.append(f'            <dt>{escape(term)}</dt>')
        if isinstance(value, list):
            for item in value:
                check(sections, sid, item)
            items = ''.join(f'<li>{escape(v)}</li>' for v in value)
            lines.append(f'            <dd><ul>{items}</ul> {cite(sid)}</dd>')
        else:
            check(sections, sid, value)
            source = f' {cite(sid)}' if sid else ''
            lines.append(f'            <dd>{escape(value)}{source}</dd>')
    lines.append('        </dl>')
    return lines


def build_proof_points(sections):
    lines = [
        '        <h2 id="proof-points">Proof points</h2>',
        '        <div class="table-wrap">',
        '        <table>',
        '            <thead><tr><th>Product</th><th>Role</th><th>Outcome</th>'
        '<th>Year</th><th>Strength</th><th>Source</th></tr></thead>',
        '            <tbody>',
    ]
    for row in PROOF_POINTS:
        used = []
        cells = []
        for key in ('product', 'role', 'outcome', 'year'):
            text, sid = row[key]
            check(sections, sid, text)
            used.append(sid)
            cells.append(escape(text))
        label, sid, evidence = row['strength']
        check(sections, sid, evidence)
        used.append(sid)
        cells.append(escape(label))
        cells.append(escape('TomBot ' + ', '.join(dict.fromkeys(used))))
        lines.append('                <tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
    lines.extend(['            </tbody>', '        </table>', '        </div>'])
    return lines


def build_behaviour(sections):
    lines = ['        <h2 id="behavioural-facts">Behavioural facts</h2>', '        <dl>']
    last = None
    for term, sid, value in BEHAVIOUR:
        check(sections, sid, value)
        if term != last:
            lines.append(f'            <dt>{escape(term)}</dt>')
            last = term
        lines.append(f'            <dd>{escape(value)} {cite(sid)}</dd>')
    lines.append('        </dl>')
    return lines


def build_jsonld(sections):
    """schema.org/Person as a JSON-LD script tag; quoted phrases are checked verbatim."""
    check(sections, *JOB_TITLE)
    kb_sid, kb_items = KNOWS_ABOUT
    for item in kb_items:
        check(sections, kb_sid, item)
    person = {
        '@context': 'https://schema.org',
        '@type': 'Person',
        'name': 'Tom Stenson',
        'givenName': 'Tom',
        'familyName': 'Stenson',
        'jobTitle': JOB_TITLE[1],
        'address': {
            '@type': 'PostalAddress',
            'addressLocality': 'Copenhagen',
            'addressCountry': 'DK',
        },
        'url': PAGE_URL,
        'mainEntityOfPage': PAGE_URL,
        'sameAs': [
            LINKEDIN_URL,
            'https://takenbyninjas.com/projects/tombot/',
            'https://takenbyninjas.com/about/',
        ],
        'knowsAbout': kb_items,
    }
    body = json.dumps(person, ensure_ascii=False, indent=2).replace('\n', '\n    ')
    return f'<script type="application/ld+json">\n    {body}\n    </script>'


def generate_html(sections):
    check(sections, *META_DESC_LINE)
    meta_desc = _escape(META_DESC_PREFIX + META_DESC_LINE[1])

    body = [
        '    <!-- MAIN CONTENT -->',
        '    <main class="agent-page">',
        '        <p>This page is written for AI agents and recruiters\' tools. '
        'If you are a person, the human version is at <a href="/about/">/about/</a>.</p>',
        '        <h1>Tom Stenson: facts for agents</h1>',
    ]
    body += build_who(sections)
    body += build_proof_points(sections)
    body += build_behaviour(sections)
    body += [
        '        <h2 id="availability">Availability and compensation</h2>',
        '        <dl>',
        '            <dt>Availability</dt>',
        '            <dd>On request. <a href="/projects/tombot/">/projects/tombot/</a></dd>',
        '            <dt>Compensation</dt>',
        '            <dd>On request. <a href="/projects/tombot/">/projects/tombot/</a></dd>',
        '        </dl>',
        '        <h2 id="sources">Sources</h2>',
        '        <p>Every claim on this page is a verbatim line from TomBot content, with its section id beside it. '
        'The content source is the TomBot at <a href="/projects/tombot/">/projects/tombot/</a>.</p>',
        '    </main>',
        '',
    ]

    return '\n'.join([
        html_head(
            title=TITLE,
            extra_scripts=[PAGE_STYLE, build_jsonld(sections)],
            meta_description=meta_desc,
            no_crt=True,
            canonical_path='/about/agent/',
        ),
        site_header(),
        site_nav(),
        '\n'.join(body),
        site_footer(),
    ]) + '\n'


def main():
    sections = load_sections()
    html = generate_html(sections)
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'✓ Agent facts page generated: {OUTPUT_FILE}')


if __name__ == '__main__':
    main()
