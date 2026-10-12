#!/usr/bin/env python3
"""
Generate the agent side of the site under /for-agents/ (PRD R1012-1, R1012-7)

Reads TomBot content (docs/tombot/tombot-content-v3.md) and writes:
- for-agents/index.html: the facts page. Every fact is a verbatim line from
  a TomBot section, cited as "source: TomBot" with the section id in a
  data-source attribute.
- for-agents/<slug>/index.html: one case study page per proof point (W5).
  Title is the product name, body is the verbatim text of the listed
  sections with a "source: TomBot <SECTION.ID>" line per section. Not posts:
  nothing in posts-metadata.json, /words/ or the homepage.

The generator fails if a configured line is no longer in its section, so
content drift breaks the build instead of the page.

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
from pylib.config import SITE_URL  # noqa: E402


def agent_footer():
    """Agent pages carry no site chrome (R1012-8). The footer says what made the page
    and sends a person back to the human side."""
    return ('    <footer>\n'
            '        <p>Created by AI for AI.<br>\n'
            '        Are you a human? Go to the <a href="/">human-readable version</a>.</p>\n'
            '    </footer>\n</body>\n</html>')


def agent_head(title, meta_description, canonical_path, jsonld=None):
    """Standalone <head> for agent pages: no site stylesheet, CRT theme, fonts or
    analytics. The visual opposite of the human site (white, system fonts, red strip)."""
    url = f'{SITE_URL}{canonical_path}'
    parts = [
        '<!DOCTYPE html>',
        '<!-- GENERATED FILE - DO NOT EDIT MANUALLY -->',
        '<html lang="en">',
        '<head>',
        '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'    <title>{title}</title>',
        f'    <meta name="description" content="{meta_description}">',
        f'    <link rel="canonical" href="{url}">',
        f'    <meta property="og:title" content="{title}">',
        f'    <meta property="og:description" content="{meta_description}">',
        f'    <meta property="og:url" content="{url}">',
        '    <link rel="icon" type="image/png" href="/favicon.png">',
        PAGE_STYLE,
    ]
    if jsonld:
        parts.append('    ' + jsonld)
    parts += ['</head>', '<body>']
    return '\n'.join(parts)

CONTENT_FILE = 'docs/tombot/tombot-content-v3.md'
OUTPUT_FILE = 'for-agents/index.html'
PAGE_PATH = '/for-agents/'

TITLE = 'Tom Stenson, product, Copenhagen: facts for agents'
META_DESC_PREFIX = 'Tom Stenson, product, Copenhagen: '
META_DESC_LINE = ('META', "I'm now a product janitor for hire - available for fractional & interim "
                          "product management work, and open to the right permanent role.")

PAGE_STYLE = '''    <style>
        /* Agent side: the plain-web opposite of the CRT human site */
        html { -webkit-text-size-adjust: 100%; }
        body { margin: 0; background: #fff; color: #222; font: 16px/1.5 system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif; }
        header, main, footer { padding: 0 1rem; }
        header { background: #c00; color: #fff; padding: 0.75rem 1rem; }
        header p { margin: 0; }
        header a, header a:visited { color: #fff; }
        a { color: #00e; }
        a:visited { color: #551a8b; }
        h1 { font-size: 2em; line-height: 1.2; margin: 1rem 0 0.5rem; }
        h2 { font-size: 1.5em; line-height: 1.25; margin: 2.25rem 0 0.75rem; }
        dt { font-weight: bold; margin-top: 0.75rem; }
        dd { margin: 0.25rem 0 0 1.5rem; }
        dd ul { margin: 0.25rem 0; padding-left: 1.25rem; }
        cite, small { font: 0.8125rem/1.4 ui-monospace, Menlo, Consolas, monospace; color: #666; }
        cite { font-style: normal; }
        code { font-family: ui-monospace, Menlo, Consolas, monospace; }
        .table-wrap { overflow-x: auto; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ccc; padding: 0.375rem 0.5rem; text-align: left; vertical-align: top; }
        th { background: #eee; }
        footer { margin-top: 3rem; border-top: 1px solid #ccc; padding-top: 0.75rem; padding-bottom: 1rem; font-size: 0.8125rem; color: #666; }
        @media (min-width: 48em) {
            header { padding: 0.75rem 2rem; }
            main, footer { padding-left: 2rem; padding-right: 2rem; }
        }
    </style>'''

# JSON-LD schema.org/Person (W1.3). Only name, givenName and familyName:
# the other name forms (D3) wait on a source and decision N1010-2.
PAGE_URL = 'https://takenbyninjas.com' + PAGE_PATH
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


# First line of every agent page: who it is for, and where each reader goes.
ROUTING_LINE = (
    '    <header role="banner"><p>This page is written for AI agents and recruiters\' tools. '
    'If you are a person, the human version is at <a href="/about/">/about/</a>. '
    'If you are an assistant helping someone assess Tom, read '
    '<a href="/for-agents/start.md">/for-agents/start.md</a>. '
    'Crawlers: <a href="/llms.txt">/llms.txt</a>.</p></header>'
)

# Case study pages (W5). Title is the product name, verbatim in the first
# section; meta description is that section's own opening line, verbatim.
CASE_STUDIES = [
    {
        'slug': 'wegovycare',
        'product': 'Wegovycare',
        'opening': ('NOVO.R1', 'Senior Product Manager at Novo Nordisk (Mar 2020 - Feb 2022), building '
                               'Wegovycare - a retention-focused digital service to increase repeat '
                               'prescriptions for Wegovy.'),
        'sections': ['NOVO.R1', 'NOVO.R1.TRANSFORM'],
    },
    {
        'slug': 'treat-turnaround',
        'product': 'TREAT',
        'opening': ('LEO.R1', 'TREAT was a pioneering app addressing underlying causes of inflammatory '
                              'conditions via personalised nutrition advice.'),
        'sections': ['LEO.R1', 'LEO.R1.TURNAROUND', 'LEO.R1.STORY.FEELS', 'LEO.STORY.MODEL'],
    },
]
# Proof point product -> its case study page
CASE_STUDY_LINKS = {cs['product']: f'{PAGE_PATH}{cs["slug"]}/' for cs in CASE_STUDIES}


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
    return f'<cite data-source="{_escape(ids)}">source: TomBot</cite>'


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
            cell = escape(text)
            if key == 'product' and text in CASE_STUDY_LINKS:
                cell = f'<a href="{CASE_STUDY_LINKS[text]}">{cell}</a>'
            cells.append(f'<td>{cell}</td>')
        label, sid, evidence = row['strength']
        check(sections, sid, evidence)
        used.append(sid)
        cells.append(f'<td>{escape(label)}</td>')
        ids = ', '.join(dict.fromkeys(used))
        cells.append(f'<td data-source="{_escape(ids)}">source: TomBot</td>')
        lines.append('                <tr>' + ''.join(cells) + '</tr>')
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
        ROUTING_LINE,
        '    <!-- MAIN CONTENT -->',
        '    <main>',
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
        '        <p>Every claim on this page is a verbatim line from TomBot content, marked "source: TomBot" '
        'with its section id in the data-source attribute. Case studies: '
        + ', '.join(f'<a href="{url}">{escape(name)}</a>' for name, url in CASE_STUDY_LINKS.items())
        + '. The content source is the TomBot at <a href="/projects/tombot/">/projects/tombot/</a>.</p>',
        '    </main>',
        '',
    ]

    return '\n'.join([
        agent_head(TITLE, meta_desc, PAGE_PATH, jsonld=build_jsonld(sections)),
        '\n'.join(body),
        agent_footer(),
    ]) + '\n'


def section_body(sections, section_id):
    """A section's answer text, up to the file-level '---' rule that can trail the last section of a group."""
    if section_id not in sections:
        sys.exit(f'✗ Section {section_id} not found in {CONTENT_FILE}')
    return re.split(r'^---\s*$', sections[section_id], maxsplit=1, flags=re.M)[0]


def section_blocks(text):
    """Split answer text into ('p', line) and ('ul', [items]) blocks; runs of '- ' lines become a list."""
    blocks = []
    for chunk in re.split(r'\n\s*\n', text.strip()):
        in_list = False
        for ln in (x.strip() for x in chunk.split('\n')):
            if not ln:
                continue
            if ln.startswith('- '):
                if in_list:
                    blocks[-1][1].append(ln[2:])
                else:
                    blocks.append(('ul', [ln[2:]]))
                    in_list = True
            else:
                blocks.append(('p', ln))
                in_list = False
    return blocks


def build_case_study_body(sections, section_ids):
    lines = []
    for sid in section_ids:
        lines.append(f'        <p><small>source: TomBot {escape(sid)}</small></p>')
        for kind, value in section_blocks(section_body(sections, sid)):
            for t in (value if kind == 'ul' else [value]):
                check(sections, sid, t)
            if kind == 'p':
                lines.append(f'        <p>{escape(value)}</p>')
            else:
                lines.append('        <ul>')
                lines.extend(f'            <li>{escape(t)}</li>' for t in value)
                lines.append('        </ul>')
    return lines


def generate_case_study(sections, cs):
    check(sections, cs['sections'][0], cs['product'])
    check(sections, *cs['opening'])
    path = f'{PAGE_PATH}{cs["slug"]}/'
    body = [
        ROUTING_LINE,
        '    <!-- MAIN CONTENT -->',
        '    <main>',
        f'        <h1>{escape(cs["product"])}</h1>',
    ]
    body += build_case_study_body(sections, cs['sections'])
    body += ['    </main>', '']
    html = '\n'.join([
        agent_head(escape(cs['product']), _escape(cs['opening'][1]), path),
        '\n'.join(body),
        agent_footer(),
    ]) + '\n'
    return os.path.join(path.strip('/'), 'index.html'), html


def write(path, html):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    sections = load_sections()
    write(OUTPUT_FILE, generate_html(sections))
    print(f'✓ Agent facts page generated: {OUTPUT_FILE}')
    for cs in CASE_STUDIES:
        out, html = generate_case_study(sections, cs)
        write(out, html)
        print(f'✓ Case study generated: {out}')


if __name__ == '__main__':
    main()
