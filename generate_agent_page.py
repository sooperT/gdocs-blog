#!/usr/bin/env python3
"""
Generate the agent side of the site under /for-agents/ (PRD R1012-1, R1012-7)

Reads TomBot content (docs/tombot/tombot-content-v3.md) and writes:
- for-agents/index.html: the facts page. Every proof point in the content,
  grouped by role shape (R1012-12), each cell a verbatim line from a TomBot
  section cited by id. Who, behavioural facts, availability, JSON-LD.
- for-agents/<slug>/index.html: one page per role, product or theme (PAGES).
  Verbatim text of its sections; per section the direct answers and external
  links once Tom accepts them (parse_content.py reads those blocks); the
  section's drill-downs and follow-ups as links to the page that holds the
  target section, or to /ask?q= when none does. That is the spider: every
  node reachable from the facts page, every claim on its own URL with its
  sources beside it.
- for-agents/recommendations/index.html: every visible LinkedIn
  recommendation in full, grouped by the role and period it refers to
  (R1012-15: references for a role, never evidence for a claim). Both the
  title when written (Tom supplies it) and the current title, labelled
  (R1012-13).
- for-agents/working-style/index.html: the two Insights Discovery profiles
  (R1013-7): ideal environment, motivation, managing Tom, value to the team,
  dated and tier-labelled (self-reported assessment).
- for-agents/pages.json: the page manifest, read by agent-fetch (counting)
  and generate_sitemap.py (sitemap-agent.xml).

The generator fails if a configured line is no longer in its section, so
content drift breaks the build instead of the page.

Usage:
    python3 generate_agent_page.py
"""

import csv
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, date
from html import escape as _escape
from urllib.parse import quote

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
from pylib.story_facets import FACETS as STORY_FACETS, ROW_PRODUCTS as FACET_ROW_PRODUCTS, facet_json
from parse_content import parse_content_doc  # noqa: E402
from pylib.config import SITE_URL  # noqa: E402


def agent_footer():
    """Agent pages carry no site chrome (R1012-8). The footer says what made the page
    and sends a person back to the human side."""
    return ('    <footer>\n'
            f'        <p>Created by AI for AI. Generated {GENERATED}.<br>\n'
            '        Are you a human? Go to the <a href="/">human-readable version</a>.</p>\n'
            '    </footer>\n</body>\n</html>')


def agent_head(title, meta_description, canonical_path, jsonld=None, noindex=False):
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
    if noindex:
        parts.insert(-1, '    <meta name="robots" content="noindex, follow">')
    if jsonld:
        parts.append('    ' + jsonld)
    parts += ['</head>', '<body>']
    return '\n'.join(parts)

GENERATED = date.today().isoformat()
CONTENT_FILE = 'docs/tombot/tombot-content-v3.md'
# Section id -> {"strength": "Led", "phrase": verbatim}. Bundled by the
# functions (lib/strength.js); Led only where the section says so plainly.
STRENGTH_FILE = 'netlify/functions/lib/strength.json'
OUTPUT_FILE = 'for-agents/index.html'
MANIFEST_FILE = 'for-agents/pages.json'
# Period -> count and URL of the recommendations page group, read by the
# functions (lib/references.js) so /ask rows point at references per period.
REFERENCES_FILE = 'netlify/functions/lib/references.json'
PAGE_PATH = '/for-agents/'

TITLE = 'Tom Stenson, product, Copenhagen: facts for agents'
# Meta description (A2, Tom 2026-10-13): no single shape or engagement type; the four
# no list of shapes either (Tom, 2026-10-13 evening: any list boxes him in). Counts are filled in at build time.
META_DESC = ('Tom Stenson, product, Copenhagen: facts for AI agents. Who he is, career table, '
             '{points} proof points with sources, {refs} references.')

PAGE_STYLE = '''    <style>
        /* Agent side: the plain-web opposite of the CRT human site */
        html { -webkit-text-size-adjust: 100%; }
        body { margin: 0; background: #fff; color: #222; font: 16px/1.5 system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif; }
        header, main, footer { padding: 0 1rem; }
        header { background: #c00; color: #fff; padding: 0.75rem 1rem; }
        header p { margin: 0; }
        header ul { margin: 0.25rem 0 0; padding-left: 1.25rem; }
        header a, header a:visited { color: #fff; }
        a { color: #00e; }
        a:visited { color: #551a8b; }
        h1 { font-size: 2em; line-height: 1.2; margin: 1rem 0 0.5rem; }
        h2 { font-size: 1.5em; line-height: 1.25; margin: 2.25rem 0 0.75rem; }
        h3 { font-size: 1.125em; line-height: 1.3; margin: 1.5rem 0 0.5rem; }
        dt { font-weight: bold; margin-top: 0.75rem; }
        dd { margin: 0.25rem 0 0 1.5rem; }
        dd ul { margin: 0.25rem 0; padding-left: 1.25rem; }
        cite, small { font: 0.8125rem/1.4 ui-monospace, Menlo, Consolas, monospace; color: #666; }
        small.desc { font-family: inherit; }   /* a product's what-it-is line is prose, not metadata */
        cite { font-style: normal; }
        code { font-family: ui-monospace, Menlo, Consolas, monospace; }
        .table-wrap { overflow-x: auto; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ccc; padding: 0.375rem 0.5rem; text-align: left; vertical-align: top; }
        th[scope=row] { white-space: nowrap; }
        th { background: #eee; }
        blockquote { margin: 0.5rem 0 1rem; padding-left: 1rem; border-left: 3px solid #ccc; }
        footer { margin-top: 3rem; border-top: 1px solid #ccc; padding-top: 0.75rem; padding-bottom: 1rem; font-size: 0.8125rem; color: #666; }
        @media (min-width: 48em) {
            header { padding: 0.75rem 2rem; }
            main, footer { padding-left: 2rem; padding-right: 2rem; }
        }
    </style>'''

PAGE_URL = 'https://takenbyninjas.com' + PAGE_PATH
LINKEDIN_URL = 'https://www.linkedin.com/in/tomstenson/'

# JSON-LD schema.org/Person (W1.3, R1012-14: keywords, true only).
# jobTitle: every title Tom has held, verbatim in the section named.
JOB_TITLES = [
    ('NOVO.R2', 'Associate Product Director'),
    ('NOVO.R1', 'Senior Product Manager'),
    ('LEO.R1', 'PM/GM'),
    ('OPBEAT', 'Head of Marketing'),
    ('EURODNS', 'Marketing Director'),
    ('UK2', 'Head of Group Strategy'),
    ('HOST', 'Head of New Media'),
]
# hasOccupation: the shapes Tom is open to, in META.LOOKING's own words.
OCCUPATION_LINE = ('META.LOOKING', "I'm available for fractional & interim product management work, "
                                   "also open to the right permanent role.")
# knowsAbout: competency phrases (META.COMPETENCIES, verbatim) plus domain
# words that appear verbatim somewhere in the content (checked against the
# whole file, case-sensitive).
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
KNOWS_ABOUT_WORDS = [
    'GenAI', 'RAG', 'machine learning', 'computer vision', 'pharma', 'health-tech', 'healthcare',
    'SaaS', 'web hosting', 'domain registrar', 'developer tools', 'turnaround', 'discovery',
    'prototyping', 'remote teams', 'product operations', 'Claude Code',
]

# Screening facts register (R1012-22): one fact per question a screener asks,
# typed by that question. Everything that states a fact about Tom reads from
# here: the Who table below, the entry file's card, proof-points.json
# (`screening_facts`), the CV appendix and /ask/brief (lib/facts.json).
#   type   the kind of job-description line the fact settles
#   label  how it is printed
#   parts  [(fragment, section id or None)]: the core of the fact, always
#          true and always printed; verbatim in the section, None marks a fixed
#          fact; [] = Tom has not stated one, so a JD that asks gets "not
#          stated" and Tom gets the question
#   when   [(fragment, section id, pattern)]: a qualifier, printed only when
#          the JD line asks about it (Tom, 2026-10-12: "is remote across the
#          EU something they ask for?"). Answer what was asked, nothing else.
#          With no JD in play (facts page, entry file) the whole fact shows.
#   asks   case-insensitive patterns that mark a JD line as this question
#          (plain syntax only: both JavaScript and Python read them)
#   per_send  the standing fact cannot settle it for a given job (onsite at
#          that job's location): asked once per application
#   on_request  Tom answers this himself, per conversation (N1012-12, N1012-15):
#          a JD that asks gets ON_REQUEST; the fact is not listed on its own,
#          the Who table's "on request" row covers it
ON_REQUEST = 'On request: GET /ask?q=How%20can%20I%20contact%20Tom%3F'
FACTS = [
    {'type': 'name', 'label': 'Name', 'parts': [('Tom Stenson', None), ('also Thomas Traberg Stenson', None)], 'asks': []},
    {'type': 'last_role', 'label': 'Most recent role',
     'parts': [('Associate Product Director at Novo Nordisk (Feb 2022 - Feb 2026)', 'NOVO.R2')], 'asks': []},
    # Years per area are Tom's stated count (R1013-13), never summed from role spans;
    # no ask patterns: a "5+ years" line stays an experience requirement.
    {'type': 'years', 'label': 'Years of experience',
     'parts': [('10+ years building digital products', 'META.ARC'),
               ('2.5 years in AI (Diagnosis App machine learning, agentic MLR)', 'META.ARC'),
               ('10 years in growth roles', 'META.ARC'),
               ('10 years managing people, also happy as IC', 'META.ARC')], 'asks': []},
    # Before location: a salary line often says "based in" too (Danske, knockout audit P6).
    {'type': 'compensation', 'label': 'Compensation', 'on_request': True, 'parts': [(ON_REQUEST, None)],
     'asks': [r'\bsalary\b', r'\bcompensation (range|package)\b', r'\b(base|total) (pay|comp)']},
    {'type': 'location', 'label': 'Location', 'per_send': True,
     'parts': [('Copenhagen, Denmark', 'META.LOCATION')],
     'when': [('Onsite in Copenhagen up to four days a week, some flexibility preferred', 'META.LOCATION', r'^\s*location\b|\bbased in\b|\bon-?site\b|\bhybrid\b|\boffice\b'),
              ('remote roles across the EU and UK', 'META.LOCATION', r'\bremote(ly)?\b'),
              ('worked on-site, hybrid and remote, and across time zones', 'META.LOCATION',
               r'\bhybrid\b|\btime ?zones?\b|\bworking pattern\b|\bdays? ((a|per) week )?in (the )?office\b')],
     'asks': [r'^\s*location\b', r'^\s*(?:in |based in )?(?:copenhagen|denmark)[\s.,]*$', r'\bbased (in|within)\b', r'\bon-?site\b', r'\bhybrid\b', r'\brelocat', r'\bfully remote\b',
              r'\bremote (role|position|work|working|first)\b', r'\bdays? ((a|per) week )?in (the )?office\b']},
    {'type': 'work_permit', 'label': 'Nationality & work permit',
     'parts': [('British & French; Danish permanent resident; no work visa is required in EU and UK.', 'META.LOCATION')],
     'asks': [r'\bvisa\b', r'\bwork permit\b', r'\bright to work\b', r'\b(authori[sz]ed|eligible|permission) to work\b', r'\bwork authori[sz]ation\b']},
    {'type': 'education', 'label': 'Education',
     'parts': [('MA Information Technology — University of Nottingham, UK (2001-2002)', 'META.EDUCATION'),
               ('BSc (Hons) Biological Sciences — University of Birmingham, UK (1998-2001)', 'META.EDUCATION')],
     'asks': [r'\bph\.?\s?d\b', r'\bm\.?sc\b', r'\bb\.?sc\b', r'\bmba\b', r'\bbachelor', r"\bmaster'?s\b", r'\bmaster of\b', r'\bdegree\b']},
    {'type': 'languages', 'label': 'Languages',
     'parts': [('English (native)', 'META.EDUCATION'), ('Danish (intermediate)', 'META.EDUCATION'),
               ('Prøve i Dansk 3 (Danish language certification, 2012)', 'META.EDUCATION')],
     'when': [('no French: French citizen, but not a French speaker', 'META.EDUCATION', r'\b(french|fransk)\b')],
     'asks': [r'\b(english|danish|german|french|spanish|swedish|norwegian|dutch)\b', r'\b(spoken|written|foreign|second) languages?\b', r'\blanguage skills\b',
              # Danish forms (health case A25: "Flydende dansk i skrift og tale")
              r'\b(engelsk|dansk|tysk|fransk|spansk|svensk|norsk|hollandsk)\b', r'\bsprog(kundskaber|krav|kompetencer)?\b', r'\bflydende\b']},
    {'type': 'employment_type', 'label': 'Open to',
     'parts': [('fractional, interim and permanent roles.', 'META.LOOKING')],
     'asks': [r'full[- ]time\b', r'\bpart[- ]time\b', r'\bpermanent (position|role|contract)\b', r'\bfixed[- ]term\b', r'\btemporary (position|role|contract)\b']},
    {'type': 'start_date', 'label': 'Start date', 'on_request': True, 'parts': [(ON_REQUEST, None)],
     'asks': [r'\bnotice period\b', r'\bstart date\b', r'\bavailable to start\b', r'\bwhen (can|could|would) \w+ start\b', r'\bavailab(le|ility)\b']},
    {'type': 'travel', 'label': 'Travel', 'parts': [], 'asks': [r'\b(willing(ness)?|able|ability|required|expected) to travel\b', r'\btravel (days|up to|required)\b', r'\b\d+ ?% travel\b']},
]
# A JD line longer than this is an experience requirement that happens to
# mention a place or a language, not a yes/no question.
FACT_ASK_MAX_CHARS = 160

# The endpoints row, each a link: chat assistants follow printed URLs only (R1013-3).
# The entry file's paste URL is the HTML page (N1012-16); the markdown stays available.
ENDPOINTS = [
    ('GET /ask?q=<question>', 'https://takenbyninjas.com/ask'),
    ('POST /ask/brief', 'https://takenbyninjas.com/ask/brief'),
    ('GET /for-agents/start/', '/for-agents/start/'),
    ('markdown /for-agents/start.md', '/for-agents/start.md'),
]
# A register fact Tom has not stated shows as this in the Who table (principle 2:
# "a blank is shown as 'not yet stated', never filled"); the CV appendix leaves it out.
NOT_YET_STATED = 'not yet stated'

# Identity table (Tom, 2026-10-12: a table, terse, only what an agent needs).
# (term, [(fragment, section id or None)]): the facts of the register (unstated
# ones as "not yet stated"), then the rows that are not screening questions.
# Base facts only: the ask-triggered qualifiers (`when`) answer a brief, they are not notes for the table (Tom, 2026-10-13).
WHO = [(f['label'], f['parts'] or [(NOT_YET_STATED, None)])
       for f in FACTS if not f.get('on_request')] + [
    ('Target industries', [('B2B, B2C, SaaS, health-tech, pharma, fintech, developer tooling, ecommerce, regulated industries', 'META.LOOKING')]),
    ('Company size', [('Experience with Startup, Scaleup, Enterprise.', 'META.LOOKING')]),
    ('Availability, compensation, contact', [('On request: GET /ask?q=How can I contact Tom?', None)]),
    ('LinkedIn', [(LINKEDIN_URL, None)]),
    ('Endpoints', [(t, None) for t, _ in ENDPOINTS]),
]


def facts_register(sections):
    """The register as data: every part checked verbatim, value = the parts joined."""
    out = []
    for f in FACTS:
        for text, sid in f['parts']:
            check(sections, sid, text)
        for text, sid, _ in f.get('when', []):
            check(sections, sid, text)
        sids = list(dict.fromkeys(sid for _, sid in f['parts'] if sid))
        base = '; '.join(t for t, _ in f['parts']) or None
        out.append({'type': f['type'], 'label': f['label'], 'base': base,
                    'qualifiers': [{'text': t, 'ask': pat} for t, _, pat in f.get('when', [])],
                    'value': '; '.join([t for t, _ in f['parts']] + [t for t, _, _ in f.get('when', [])]) or None,
                    'section': sids[0] if sids else None, 'per_send': bool(f.get('per_send')),
                    'on_request': bool(f.get('on_request')), 'asks': f['asks']})
    return {'generated_by': 'generate_agent_page.py', 'max_ask_chars': FACT_ASK_MAX_CHARS, 'facts': out}


FACTS_FILE = 'netlify/functions/lib/facts.json'
START_FACTS_HEAD = '## Screening facts'


def start_md_with_facts(md, register):
    """Rewrite the entry file's "Screening facts" section from the register (the
    section is generated; the rest of start.md is hand-written)."""
    i = md.index(START_FACTS_HEAD)
    j = md.index('\n## ', i + 1)
    lines = [START_FACTS_HEAD, '', 'The yes-or-no facts a screen starts with. Give them when your person asks (Job 4), not unprompted:', '']
    lines += [f"- {f['label']}: {f['value']}" for f in register['facts'] if f['value'] and not f['on_request']]
    lines += ['- Experience by area, with the stories for each: https://takenbyninjas.com/for-agents/shapes/', '']
    return md[:i] + '\n'.join(lines) + md[j:]


# Career table: city and ISO 3166-1 alpha-2 country per role, keyed by the
# META.JOBS Location cell, with Tom's corrections for the UK rows (2026-10-12).
CITY_COUNTRY = {
    'Copenhagen': ('Copenhagen', 'DK'),
    'Luxembourg/Copenhagen': ('Luxembourg / Copenhagen', 'LU / DK'),
    'London': ('London', 'GB'),
    'Nottingham': ('Nottingham', 'GB'),
    'UK': ('Nottingham', 'GB'),   # Web Designer, Group Design Manager, Co-founder, Freelance: all Nottingham (Tom)
}
CAREER_SECTION = 'META.JOBS'
# Career table links (Tom, 2026-10-24): company -> page slug; (role, company) -> role page slug;
# product named in brackets -> product page slug. Build fails if a target page is missing.
CAREER_COMPANY_PAGE = {
    'Novo Nordisk': 'novo-nordisk', 'LEO Innovation Lab': 'leo-innovation-lab', 'TwentyThree': 'twentythree',
    'Opbeat': 'opbeat', 'EuroDNS': 'eurodns', 'UK2 Group': 'uk2', 'Host Europe Group': 'host-europe',
    'Host Europe / Pipex': 'host-europe', 'Host Europe': 'host-europe', 'Pipex Internet': 'host-europe',
}
CAREER_ROLE_PAGE = {
    ('Associate Product Director', 'Novo Nordisk'): 'novo-nordisk/associate-product-director',
    ('Product Manager (Wegovycare)', 'Novo Nordisk'): 'novo-nordisk/senior-product-manager',
    ('PM/GM - Diagnosis App', 'LEO Innovation Lab'): 'leo-innovation-lab/pm-gm',
    ('PM/GM - Skincoach', 'LEO Innovation Lab'): 'leo-innovation-lab/pm-gm',
    ('PM/GM - TREAT', 'LEO Innovation Lab'): 'leo-innovation-lab/pm-gm',
    ('Head of Marketing (contract)', 'TwentyThree'): 'twentythree/head-of-marketing',
    ('Head of Marketing', 'Opbeat'): 'opbeat/head-of-marketing',
    ('Marketing Director', 'EuroDNS'): 'eurodns/marketing-director',
    ('Independent Consultant', 'Various'): 'independent-consulting/independent-consultant',
    ('Head of Group Strategy', 'UK2 Group'): 'uk2-group/head-of-group-strategy',
    ('Head of New Media', 'Host Europe Group'): 'host-europe-group/head-of-new-media',
    ('Web Designer', 'Host Europe / Pipex'): 'host-europe-group/web-designer',
}
# Title aliases (R1012-17): the same role under the names different CVs and LinkedIn use.
ROLE_ALIASES = {
    'Senior Product Manager at Novo Nordisk': ['Product Owner', 'Product Manager (Wegovycare)'],
    'PM/GM at LEO Innovation Lab': ['Product Owner', 'Product Lead', 'Product Lead / GM', 'Product Manager / GM'],
    'Associate Product Director at Novo Nordisk': ['Incubation Lead', 'Digital Product Operations Lead', 'Head of Patient Products', 'Head of Product Ops'],
    'Head of New Media': ['Head of New Media, Pipex Hosting / GX Networks'],
}
CAREER_PRODUCT_PAGE = {'Wegovycare': 'wegovycare', 'Diagnosis App': 'diagnosis-app', 'Skincoach': 'skincoach',
                       'TREAT': 'treat-turnaround'}
EMPLOYER_NOTE = ('One employer under several names: Pipex Communications acquired Host Europe in April 2004; the company '
                 'reverted to the GX Networks name in 2008 after selling Pipex, was renamed Host Europe Group in 2009, '
                 'and was acquired by GoDaddy in 2017.')
EMPLOYER_NOTE_SOURCE = ('Host Europe Group, Wikipedia', 'https://en.wikipedia.org/wiki/Host_Europe_Group')

# Role shapes (R1012-12): id, heading, the theme page that expands it (None
# when the content has no theme section). Order is what Tom wants next first.
SHAPES = [
    ('product-management', 'Product management', None),
    ('ai', 'AI', 'ai'),
    ('growth', 'Growth', 'growth'),
    ('zero-to-one', '0 to 1, incubation and new ways of working', 'building'),
    ('turnaround', 'Turnarounds', 'turnarounds'),
    ('regulated', 'Regulated and health', None),
    ('leadership', 'Leadership and management', 'management'),
    ('international', 'International and remote', 'international'),
]
SHAPES_PATH = f'{PAGE_PATH}shapes/'
# No "hired as" list on the page (Tom, 2026-10-13 evening): the shape groups below show
# every kind of work without choosing; any list of four boxes him in.
FACTS_ROWS_PER_SHAPE = 3   # the facts page shows this many per group; the shape page has all
# Which rows lead each group on the facts page (Claude's judgement, Tom 2026-10-12: strongest
# result and source first). Keyed by (product name, first words of the result); rows not listed
# follow in content order on the shape page only.
SHAPE_TOP = {
    'product-management': [('Wegovycare', 'Achieved 10%'), ('CagriSema', 'securing funding'), ('TREAT', 'Halved customer')],
    'ai': [('GenAI proof of concept for automating compliance reviews', 'the proof of concept'),
           ('Diagnosis App', 'Achieved >80%'), ('Wegovycare', 'later spun out')],
    'growth': [('Opbeat', 'Trebled traffic'), ('EuroDNS', 'reversed the decline'), ('domain search', 'Reinvented the domain search')],
    'zero-to-one': [('Wegovycare', 'Wegovycare launched on time'), ('Digital Incubation', 'shifted the organisation'),
                    ('Skincoach', 'Completed the full')],
    'turnaround': [('TREAT', 'Halved customer'), ('EuroDNS', 'reversed the decline'), ('US Marketing department', 'reduced bounce')],
    'regulated': [('Wegovycare', 'Achieved 10%'), ('GenAI proof of concept for automating compliance reviews', 'the proof of concept'),
                  ('Skincoach', 'Completed the full')],
    'leadership': [('Diagnosis App', 'Achieved >80%'), ('EuroDNS', 'The rhythm gave'), ('Wegovycare', 'Wegovycare launched on time')],
    'international': [('US Marketing department', 'reduced bounce'), ('Wegovy Pill launch', 'driving prescription'), ('Opbeat', 'Trebled traffic')],
}


def shape_rows(shape_id):
    """Rows for a shape: the SHAPE_TOP picks first, in pick order, then the rest in content order."""
    rows = [r for r in PROOF_POINTS if shape_id in row_shapes(r)]
    picked = []
    for name, frag in SHAPE_TOP.get(shape_id, []):
        hit = next((r for r in rows if r['product'][0] == name and ((r.get('_quote') or {}).get('result') or r['result'])[0].startswith(frag)), None)   # picks name the verbatim result
        if hit is None:
            sys.exit(f'✗ SHAPE_TOP: no row {name!r} / {frag!r} in shape {shape_id!r}')
        picked.append(hit)
    return picked + [r for r in rows if r not in picked]

# Proof points: every outcome in the content as a STAR row (Tom, 2026-10-12):
# situation, task, action, result, each (verbatim text, section id); None
# shows "not yet stated". 'product' is the name, 'desc' what it is. Each cell is (verbatim text, section id it is quoted from);
# 'problem' None shows "not yet stated" (R1012-6, phase 3 fills it).
# 'strength' names the section whose label is used (STRENGTH_FILE, shared
# with /ask): Contributed is said in the role cell, Led is the norm and is
# not shown (Tom, 2026-10-12). 'shapes' lists the groups the row sits in; the
# same row can sit in two. Within a group, rows are newest first.
PROOF_POINTS = [
    {
        'role': ('Senior Product Manager at Novo Nordisk', 'NOVO.R1'),
        'product': ('Wegovycare', 'NOVO.R1'),
        'desc': ('a retention-focused digital service to increase repeat prescriptions for Wegovy', 'NOVO.R1'),
        'situation': ('The brief I was given in my final-round interview was solution-first: a set of standalone features the business thought would help. Nobody had spoken to patients.', 'NOVO.R1'),
        'task': ('Identified a key growth lever.', 'NOVO.R1'),
        'action': ('Created a weight-loss prediction model in Excel', 'NOVO.R1'),
        'result': ('Achieved 10% penetration in our first national market', 'NOVO.R1'),
        'year': ('Mar 2020 - Feb 2022', 'NOVO.R1'),
        'strength': 'NOVO.R1',
        'shapes': ['zero-to-one', 'regulated'],
    },
    {
        'role': ('Senior Product Manager at Novo Nordisk', 'NOVO.R1'),
        'product': ('Wegovycare', 'NOVO.R1'),
        'desc': ('a weight-loss prediction algorithm', 'NOVO.R1'),
        'situation': ('everyone wants to know the same things - how much weight will I lose, is this normal, am I on track', 'NOVO.R1'),
        'task': ('Those three questions became the core loop, and the weight-loss prediction model answered the first.', 'NOVO.R1'),
        'action': ('Built a weight-loss prediction algorithm from concept to prototype', 'NOVO.R1'),
        'result': ('later spun out into a new API product', 'NOVO.R1'),
        'year': ('Mar 2020 - Feb 2022', 'NOVO.R1'),
        'strength': 'NOVO.R1',
        'shapes': ['ai'],
    },
    {
        'role': ('Senior Product Manager at Novo Nordisk', 'NOVO.R1'),
        'product': ('Wegovycare', 'NOVO.R1'),
        'desc': ('a retention-focused digital service to increase repeat prescriptions for Wegovy', 'NOVO.R1'),
        'situation': ('The brief I was given in my final-round interview was solution-first: a set of standalone features the business thought would help. Nobody had spoken to patients.', 'NOVO.R1'),
        'task': ('use this as a mandate to completely reinvent their ways of working', 'NOVO.R1.TRANSFORM'),
        'action': ('We were the first product team to interview patients, run discovery, make prototypes, co-create with markets and so on.', 'NOVO.R1.TRANSFORM'),
        'result': ('Wegovycare launched on time and on budget, with 10% penetration in the first national market.', 'NOVO.R1.TRANSFORM'),
        'year': ('Mar 2020 - Feb 2022', 'NOVO.R1'),
        'strength': 'NOVO.R1.TRANSFORM',
        'shapes': ['zero-to-one', 'regulated', 'leadership'],
    },
    {
        'role': ('Associate Product Director at Novo Nordisk', 'NOVO.R2'),
        'product': ('GenAI proof of concept for automating compliance reviews', 'NOVO.R2'),
        'desc': ('a RAG model that captured the various guidelines and regulations', 'NOVO.R2.GENAI'),
        'situation': ('significant delays (backlogs could mean months), huge documentation overhead, and an anti-pattern where you had to fully develop everything before getting sign-off', 'NOVO.R2.GENAI'),
        'task': ('automating compliance reviews', 'NOVO.R2'),
        'action': ('I used an internal LLM sandbox to create a RAG model that captured the various guidelines and regulations', 'NOVO.R2.GENAI'),
        'result': ('the proof of concept showed a clear path to dramatically faster release cycles', 'NOVO.R2.GENAI'),
        'year': ('Feb 2022 - Feb 2026', 'NOVO.R2'),
        'strength': 'NOVO.R2.GENAI',
        'shapes': ['ai', 'regulated'],
    },
    {
        'role': ('Consumer Lead', 'NOVO.R2.WEGOVY'),
        'product': ('Wegovy Pill launch', 'NOVO.R2.WEGOVY'),
        'desc': ('a company-critical initiative', 'NOVO.R2.WEGOVY'),
        'situation': ('Invited into company-critical Wegovy pill launch to challenge assumptions on digital, packaging, and direct distribution.', 'NOVO.R2.WEGOVY'),
        'task': ('Aligned silos to create unified physical-to-digital experience.', 'NOVO.R2.WEGOVY'),
        'action': ('Used subscription-model thinking to link packaging to digital fulfilment for biggest ever pharma launch.', 'NOVO.R2.WEGOVY'),
        'result': ('driving prescription growth', 'NOVO.R2'),
        'year': ('Feb 2022 - Feb 2026', 'NOVO.R2'),
        'strength': 'NOVO.R2.WEGOVY',
        'shapes': ['growth', 'regulated', 'international'],
    },
    {
        'role': ('Associate Product Director at Novo Nordisk', 'NOVO.R2'),
        'product': ('CagriSema', 'NOVO.R2'),
        'desc': ("a six-month discovery programme for the company's top drug asset", 'NOVO.R2'),
        'situation': ('CagriSema was the first drug to span two therapy areas, diabetes and obesity, that had never collaborated. Nobody had authority over both, so the discovery programme ran on influence.', 'NOVO.R2'),
        'task': ("Led a six-month discovery programme for the company's top drug asset", 'NOVO.R2'),
        'action': ('128 candidate ideas, a shortlist of 5, assumption-tested, 4 recommended and funded, each with a funding-gated rollout', 'NOVO.R2'),
        'result': ('securing funding for a portfolio of digital initiatives', 'NOVO.R2'),
        'year': ('Feb 2022 - Feb 2026', 'NOVO.R2'),
        'strength': 'NOVO.R2',
        'shapes': ['zero-to-one', 'regulated'],
    },
    {
        'role': ('Associate Product Director at Novo Nordisk', 'NOVO.R2'),
        'product': ('Digital Incubation', 'NOVO.R2'),
        'desc': ('a digital product incubation unit, evaluating build, buy and partner solutions', 'NOVO.R2'),
        'situation': ('The organisational reflex was solution-first and siloed: output and theatre over outcomes.', 'NOVO.R2'),
        'task': ('Secured funding, managed resourcing and cross-charges for incubation teams.', 'NOVO.R2'),
        'action': ('Designed portfolio model and gated incubation pipeline for branded digital engagement.', 'NOVO.R2'),
        'result': ('shifted the organisation from output to outcomes', 'NOVO.R2'),
        'year': ('Feb 2022 - Feb 2026', 'NOVO.R2'),
        'strength': 'NOVO.R2',
        'shapes': ['zero-to-one', 'leadership'],
    },
    {
        'role': ('Associate Product Director at Novo Nordisk', 'NOVO.R2'),
        'product': ('Product Operations', 'NOVO.R2'),
        'desc': ('standards, artefacts, ways of working', 'NOVO.R2'),
        'situation': ('Given a wider remit to work across the product pipeline and complete the transition to a product operating model.', 'NOVO.R2'),
        'task': ('Established metrics across a diverse portfolio (12 products).', 'NOVO.R2'),
        'action': ('Established product artefacts & quality standards across the product org, eg: gate model & deliverables, product-ops metrics, portfolio reports, business case templates, problem/north-star statements.', 'NOVO.R2'),
        'result': ('Helped product teams connect work to commercial outcomes.', 'NOVO.R2'),
        'year': ('Feb 2022 - Feb 2026', 'NOVO.R2'),
        'strength': 'NOVO.R2',
        'shapes': ['leadership'],
    },
    {
        'role': ('Associate Product Director at Novo Nordisk', 'NOVO.R2'),
        'product': ('Head of Patient Products', 'NOVO.R2'),
        'desc': ('consumer engagement products', 'NOVO.R2'),
        'situation': ('Interim reorg of product teams before the Wegovy Pill project.', 'NOVO.R2'),
        'task': ('led 6 experienced PMs building consumer engagement products, for a period, before moving into the pill team where the need was greatest. Management by outcomes.', 'NOVO.R2'),
        'action': ('Individual coaching and weekly experiment sharing; made individual product metrics public.', 'NOVO.R2'),
        'result': ('Broke product silos, established weekly demos and experiment sharing, encouraged learning loops.', 'NOVO.R2'),
        'year': ('Feb 2022 - Feb 2026', 'NOVO.R2'),
        'strength': 'NOVO.R2',
        'shapes': ['leadership'],
    },
    {
        'role': ('Associate Product Director at Novo Nordisk', 'NOVO.R2'),
        'product': ('project steercos', 'NOVO.R2'),
        'desc': ('Chaired project steercos. Flipped the format from status updates to interactive co-creation', 'NOVO.R2'),
        'situation': ('Steercos were project management checklists: project not product focused, and unsuited for high-uncertainty discovery-stage products.', 'NOVO.R2'),
        'task': ('Chaired project steercos.', 'NOVO.R2'),
        'action': ('Flipped the format from status updates to interactive co-creation', 'NOVO.R2'),
        'result': ('shifting cross-functional VPs from product sceptics to advocates', 'NOVO.R2'),
        'year': ('Feb 2022 - Feb 2026', 'NOVO.R2'),
        'strength': 'NOVO.R2',
        'shapes': ['leadership'],
    },
    {
        'role': ('Senior Product Manager at Novo Nordisk', 'NOVO.R1'),
        'product': ('Wegovycare', 'NOVO.R1'),
        'desc': ('risk-profiling engine combining clinical data, usage signals, & PROMs', 'NOVO.R1'),
        'situation': ('Through research identified every user-journey is different.', 'NOVO.R1'),
        'task': ('identify drop-off risks', 'NOVO.R1'),
        'action': ('Applied consumer marketing playbook to act on risks, personalising experience for each patient. Built profiling and customisation engine to create an interactive magazine.', 'NOVO.R1'),
        'result': ('First digital Novo product to successfully scale.', 'NOVO.R1'),
        'year': ('Mar 2020 - Feb 2022', 'NOVO.R1'),
        'strength': 'NOVO.R1',
        'shapes': ['ai', 'growth'],
    },
    {
        'role': ('Senior Product Manager at Novo Nordisk', 'NOVO.R1'),
        'product': ('Wegovycare', 'NOVO.R1'),
        'desc': ('Digital patient platform for obesity medicine, built to scale.', 'NOVO.R1'),
        'situation': ('release cycles were yearly, with heavy documentation in a high-regulation environment, and every market needed its own version', 'NOVO.R1'),
        'task': ('Led cross-functional team of 10.', 'NOVO.R1'),
        'action': ('Designed for scaling: modular architecture, feature flags, integrated CMS & translation pipeline, and systematised cocreation with markets.', 'NOVO.R1'),
        'result': ("Made Novo's first digital health product adopted by multiple markets; automated the documentation, and release cycles went from yearly to bi-monthly", 'NOVO.R1'),
        'year': ('Mar 2020 - Feb 2022', 'NOVO.R1'),
        'strength': 'NOVO.R1',
        'shapes': ['zero-to-one', 'international', 'leadership'],
    },
    {
        'role': ('PM/GM at LEO Innovation Lab', 'LEO.R3'),
        'product': ('Diagnosis App', 'LEO'),
        'desc': ('a prototype diagnosis app using machine learning', 'LEO.R3'),
        'situation': ('Led a team of AI engineers all wired for logic and certainty through the deep uncertainty of product discovery', 'LEO.R3'),
        'task': ('to rethink how a smartphone camera could diagnose skin conditions', 'LEO.R3'),
        'action': ('Worked with derms to redesign closed-loop diagnosis and ML training platform. Bootstrapped ML engine with clinical decision trees.', 'LEO.R3'),
        'result': ('Achieved >80% accuracy across 3 skin conditions, doubled labelling throughput', 'LEO.R3'),
        'year': ('Nov 2018 - Jan 2020', 'LEO.R3'),
        'strength': 'LEO.R3',
        'shapes': ['ai', 'leadership'],
    },
    {
        'role': ('PM/GM at LEO Innovation Lab', 'LEO.R2'),
        'product': ('Skincoach', 'LEO'),
        'desc': ('a patient-support app for terminally ill cancer patients in partnership with Amgen', 'LEO.R2'),
        'situation': ('The app was designed to help patients manage side effects from their treatment.', 'LEO.R2'),
        'task': ('Worked with oncologists to reimagine patient care between appointments. Interviewed terminally ill patients.', 'LEO.R2'),
        'action': ('Dynamically spliced video to simulate personalised dermatology consultations for terminally ill cancer patients, designed for simplicity and trust.', 'LEO.R2'),
        'result': ('Completed the full product lifecycle in 8 months, on time and on budget', 'LEO.R2'),
        'year': ('Feb 2018 - Oct 2018', 'LEO.R2'),
        'strength': 'LEO.R2',
        'shapes': ['zero-to-one', 'regulated'],
    },
    {
        'role': ('PM/GM at LEO Innovation Lab', 'LEO.R3'),
        'product': ('TREAT', 'LEO.R1'),
        'desc': ('a pioneering app addressing underlying causes of inflammatory conditions via personalised nutrition advice', 'LEO.R1'),
        'situation': ('massive tech debt, no prioritisation, flaky metrics, no roadmap, unclear reporting structure, massive churn, no pathway to profitability', 'LEO.R1.TURNAROUND'),
        'task': ('I was parachuted in with a 6-month mandate to stabilise and assess viability.', 'LEO.R1'),
        'action': ('rebuilt from the ground-up, established metrics', 'LEO.R1'),
        'result': ('Halved customer acquisition costs, increased customer activation by 7x', 'LEO.R1'),
        'year': ('Nov 2016 - Aug 2017', 'LEO.R1'),
        'strength': 'LEO.R1.TURNAROUND',
        'shapes': ['turnaround', 'growth', 'regulated'],
    },
    {
        'role': ('Head of Marketing', 'T23'),
        'product': ('TwentyThree', 'T23'),
        'desc': ('an integrated video marketing platform built for digital marketers', 'T23'),
        'situation': ('I joined as Head of Marketing on a short-term contract, initially six weeks and extended to the end of the year, to rescue a global launch.', 'T23'),
        'task': ('to rescue a global launch', 'T23'),
        'action': ('Implemented OKRs, produced video content, crystalised USPs, introduced reporting structure.', 'T23'),
        'result': ('Rescued global launch on a 6-week deadline', 'T23'),
        'year': ('2016', 'META.JOBS'),
        'strength': 'T23',
        'shapes': ['turnaround'],
    },
    {
        'role': ('Head of Marketing', 'OPBEAT'),
        'product': ('Opbeat', 'OPBEAT'),
        'desc': ('a developer tools SaaS startup providing application performance monitoring', 'OPBEAT'),
        'situation': ('The founders had a good product and famous backers, and believed that if they built it, customers would come. They launched into silence.', 'OPBEAT'),
        'task': ('built the brand, marketing strategy, team and channels from scratch', 'OPBEAT'),
        'action': ('Blended experimentation, growth hacks and activation tactics.', 'OPBEAT.R1.GROWTH'),
        'result': ('Trebled traffic and sign-ups in 12 months', 'OPBEAT'),
        'year': ('2014-2016', 'META.JOBS'),
        'strength': 'OPBEAT',
        'shapes': ['growth', 'zero-to-one', 'international'],
    },
    {
        'role': ('Marketing Director', 'EURODNS'),
        'product': ('EuroDNS', 'EURODNS'),
        'desc': ('an ICANN-accredited international domain registrar', 'EURODNS'),
        'situation': ('The business had been in decline for 4 years when I joined. Traffic was dropping, online sales were down, and the website was legacy.', 'EURODNS.R1.TURNAROUND'),
        'task': ('A turnaround project.', 'EURODNS'),
        'action': ('I restructured the marketing department, implemented KPIs, and rebooted all marketing channels including the website - all in under 8 months.', 'EURODNS.R1.TURNAROUND'),
        'result': ('reversed the decline, doubled organic traffic, halved bounce rate', 'EURODNS.R1.TURNAROUND'),
        'year': ('2013-2014', 'META.JOBS'),
        'strength': 'EURODNS.R1.TURNAROUND',
        'shapes': ['turnaround', 'growth'],
    },
    {
        'role': ('Marketing Director', 'EURODNS'),
        'product': ('EuroDNS', 'EURODNS'),
        'desc': ('an ICANN-accredited international domain registrar', 'EURODNS'),
        'situation': ('based in Copenhagen while the team was in Luxembourg', 'EURODNS.R1.STORY.REMOTE'),
        'task': ('mostly managing the team from Copenhagen', 'EURODNS'),
        'action': ('I created a natural cadence: fortnightly face-to-face meetings and plenum discussions when I was in the office, then space to focus and get on with it in-between.', 'EURODNS.R1.STORY.REMOTE'),
        'result': ('The rhythm gave structure without micromanagement. The team had clarity on direction and autonomy on execution.', 'EURODNS.R1.STORY.REMOTE'),
        'year': ('2013-2014', 'META.JOBS'),
        'strength': 'EURODNS.R1.STORY.REMOTE',
        'shapes': ['international', 'leadership'],
    },
    {
        'role': ('Acting Marketing Manager US', 'UK2'),
        'product': ('US Marketing department', 'UK2.R1.USTURNAROUND'),
        'desc': ('Managed all online and marketing activity across 5 web properties', 'UK2.R1.USTURNAROUND'),
        'situation': ("The challenge was doing this remotely from the UK, with a team I'd never met in person.", 'UK2.R1.USTURNAROUND'),
        'task': ('Rebuilt the underperforming US Marketing department before recruiting a US-based successor', 'UK2.R1.USTURNAROUND'),
        'action': ('Created marketing strategy, implemented reporting structure, set and met budget targets.', 'UK2.R1.USTURNAROUND'),
        'result': ('reduced bounce rate by ~15%, nearly doubled sales conversion, created product roadmap and launched 8 products in 10 months', 'UK2.R1.USTURNAROUND'),
        'year': ('Feb 2009 - Feb 2010', 'UK2.R1.USTURNAROUND'),
        'strength': 'UK2.R1.USTURNAROUND',
        'shapes': ['turnaround', 'international'],
    },
    {
        'role': ('Head of Group Strategy', 'UK2'),
        'product': ('new domain platform', 'UK2'),
        'desc': ('One platform replaced them', 'UK2'),
        'situation': ('we had 6 brands using 3 different providers, and in some cases going direct to the registry, each with different APIs, rules and management fees', 'UK2'),
        'task': ('Managed development of new domain platform', 'UK2'),
        'action': ('I owned the business case, budget, specifications, contracts and migration strategy.', 'UK2'),
        'result': ('(500,000+ customer domains)', 'UK2'),
        'year': ('2008-2010', 'META.JOBS'),
        'strength': 'UK2',
        'shapes': ['zero-to-one'],
    },
    {
        'role': ('Head of New Media', 'HOST'),
        'product': ('GX Networks', 'HOST.R1.REBRAND'),
        'desc': ('The company was renamed GX Networks', 'HOST.R1.REBRAND'),
        'situation': ('Due to a sale we needed to rename the company. We had 5 weeks.', 'HOST.R1.REBRAND'),
        'task': ('rename the company', 'HOST.R1.REBRAND'),
        'action': ('brand identity, corporate website, campaigns, office signage, stationery, email signatures, lawyers, and pushed the change through', 'HOST.R1.REBRAND'),
        'result': ('we got it done in 5 weeks', 'HOST.R1.REBRAND'),
        'year': ('Jan 2006 - Jun 2008', 'HOST'),
        'strength': 'HOST.R1.REBRAND',
        'shapes': ['leadership'],
    },
    {
        'role': ('Head of New Media', 'HOST'),
        'product': ('New Media', 'HOST'),
        'desc': ('responsible for all online touchpoints, ecommerce, digital campaigns, email marketing and SaaS dashboards', 'HOST'),
        'situation': ('Managed all online channels (2M+ monthly visits)', 'HOST'),
        'task': ('Created department from scratch', 'HOST'),
        'action': ('introduced self-service support, pioneered site-building tools, optimised support centre, led ecommerce, dominated SEO rankings', 'HOST'),
        'result': ('member of Senior Management Team', 'HOST'),
        'year': ('Jan 2006 - Jun 2008', 'HOST'),
        'strength': 'HOST',
        'shapes': ['zero-to-one', 'leadership'],
    },
    {
        'role': ('PM/GM at LEO Innovation Lab', 'LEO.R3'),
        'product': ('BetterVisitBot', 'LEO'),
        'desc': ('a pre-briefing chatbot for doctor consultations', 'LEO'),
        'situation': ("Patients sometimes get intimidated by the doctor, and don't get the most out of their consultation, or forget what was said.", 'LEO'),
        'task': ('Worked with GPs to prototype it.', 'LEO'),
        'action': ('I hid a dermatologist in an adjacent room to simulate a consultation chatbot.', 'LEO'),
        'result': ("Right idea, too early. Now it isn't.", 'LEO'),
        'year': ('2016 to 2020', 'LEO'),
        'strength': 'LEO.R3',
        'shapes': ['ai', 'regulated'],
    },
    {
        'role': ('Head of Marketing', 'OPBEAT'),
        'product': ('Opbeat', 'OPBEAT'),
        'desc': ('B2B devops startup backed by Balderton Capital and the cofounders of Facebook & Instagram.', 'OPBEAT'),
        'situation': None,
        'task': ('Introduced KPIs, reporting & budgeting.', 'OPBEAT'),
        'action': ('Grew grassroots meetups and created video engine to connect with developers', 'OPBEAT'),
        'result': ('creating the traction that enabled a $2M bridge-funding round', 'OPBEAT'),
        'year': ('2014-2016', 'META.JOBS'),
        'strength': 'OPBEAT',
        'shapes': ['growth', 'zero-to-one'],
    },
    {
        'role': ('Independent Consultant', 'META.JOBS'),
        'product': ('independent consultant', 'META.JOBS'),
        'desc': ('freelance internet consultant', 'META.JOBS'),
        'situation': ('worked as a freelance internet consultant to finance my relocation to Denmark', 'META.JOBS'),
        'task': ('Clients included Host Europe (UK), EuroDNS (LUX), & Everplaces (DK).', 'META.JOBS'),
        'action': ('Content creation & SEO including interviews with MailChimp, Creative Commons, EFF, Rand Fishkin & Michael Palin.', 'META.JOBS'),
        'result': ('Spotted RaspberryPi before launch & created a partnership.', 'META.JOBS'),
        'year': ('2010-2013', 'META.JOBS'),
        'strength': 'META.JOBS',
        'shapes': ['growth', 'international'],
    },
    {
        'role': ('Web Designer', 'HOST'),
        'product': ('domain search', 'HOST.R2.STORY.DOMAIN'),
        'desc': ('a simple text field that interpreted whatever the user entered and searched all endings asynchronously', 'HOST.R2.STORY.DOMAIN'),
        'situation': ('Users could only search for one domain at a time and kept running into domains that were already taken. Frustrating experience, poor conversion.', 'HOST.R2.STORY.DOMAIN'),
        'task': ('Nobody asked for it. I thought it was a poor experience at the top of the sales funnel, the shop window of the business, and worth fixing.', 'HOST.R2.STORY.DOMAIN'),
        'action': ('I reinvented the process: a simple text field that interpreted whatever the user entered and searched all endings asynchronously. First use of AJAX in our stack.', 'HOST.R2.STORY.DOMAIN'),
        'result': ('Reinvented the domain search process - first use of AJAX - revenue up 20% overnight. Became industry standard.', 'META.ARC'),
        'year': ('Feb 2004 - Aug 2005', 'HOST'),
        'strength': 'HOST.R2.STORY.DOMAIN',
        'shapes': ['growth'],
    },
    # Solo projects, 2026: one story told as three rows (R1013-4). The result is that it is live, no forced metric.
    {
        'role': ('Solo projects, building with AI', 'SOLO'),
        'product': ('TomBot', 'SOLO'),
        'desc': ('a prototype AI trained on my CV', 'SOLO'),
        'situation': ("I learn by doing, and I love building. So I shipped three products with AI to find out first-hand what it can and can't do.", 'SOLO'),
        'task': ('build something real with AI and ship it', 'SOLO'),
        'action': ('Built with Claude API, RAG vector store, eval suite & guard-rails.', 'SOLO'),
        'result': ('Live January 2026', 'SOLO'),
        'year': ('2026', 'SOLO'),
        'strength': 'SOLO',
        'shapes': ['ai', 'zero-to-one'],
        'not_skills': ['team-leadership'],
    },
    {
        'role': ('Solo projects, building with AI', 'SOLO'),
        'product': ('kittenpm.com', 'SOLO'),
        'desc': ('a product training SIM inspired by Lemmings', 'SOLO'),
        'situation': ("I learn by doing, and I love building. So I shipped three products with AI to find out first-hand what it can and can't do.", 'SOLO'),
        'task': ('build something real with AI and ship it', 'SOLO'),
        'action': ('Built with React, TypeScript & Phaser. Used Claude as my engineering team.', 'SOLO'),
        'result': ('Live July 2026', 'SOLO'),
        'year': ('2026', 'SOLO'),
        'strength': 'SOLO',
        'shapes': ['ai', 'zero-to-one'],
        'not_skills': ['team-leadership'],
    },
    {
        'role': ('Solo projects, building with AI', 'SOLO'),
        'product': ('deathspiralorgoldenage.org', 'SOLO'),
        'desc': ('A public poll, live sentiment tracker, and open economic model with CC0 data', 'SOLO'),
        'situation': ("I learn by doing, and I love building. So I shipped three products with AI to find out first-hand what it can and can't do.", 'SOLO'),
        'task': ('build something real with AI and ship it', 'SOLO'),
        'action': ('Researched & built with AI.', 'SOLO'),
        'result': ('Live September 2026', 'SOLO'),
        'year': ('2026', 'SOLO'),
        'strength': 'SOLO',
        'shapes': ['ai', 'zero-to-one'],
        'not_skills': ['team-leadership'],
    },
    # Rows for the unplaced story facets (item 47, K22): appended so PP.1 to PP.31 keep their numbers.
    # R32 the alternative website (U1, facets FU1-1 and FU1-2): every cell from HOST.R3.STORY.ALTSITE and HOST.
    {
        'role': ('Sales Executive', 'HOST'),
        'product': ('alternative website', 'HOST.R3.STORY.ALTSITE'),
        'desc': ('made an alternative website in my free time', 'HOST'),
        'situation': ('The existing website was dated. The marketing material did a poor job of explaining the "why" of the product, it was busy and cluttered, and it lacked focus and a core funnel.', 'HOST.R3.STORY.ALTSITE'),
        'task': ('I thought I could do better.', 'HOST.R3.STORY.ALTSITE'),
        'action': ("In evenings and weekends, I built an alternative version. Then I reached out to the brand manager and booked a meeting. I made my pitch and showed her what I'd made and why.", 'HOST.R3.STORY.ALTSITE'),
        'result': ('Sales went up. Next week I was in the web design team. Six months later, I was leading it.', 'HOST.R3.STORY.ALTSITE'),
        'year': ('Mar 2003 - Feb 2004', 'HOST'),
        'strength': 'HOST.R3.STORY.ALTSITE',
        'shapes': ['growth'],
    },
    # R33 the all-hands changed (U7, facets FU7-1 and FU7-2): every cell from LEO.R1.STORY.FEELS; the
    # section sits under LEO.R1, so the row takes the TREAT dates (section_years.json agrees).
    {
        'role': ('PM/GM at LEO Innovation Lab', 'LEO.R3'),
        'product': ('company all-hands', 'LEO.R1.STORY.FEELS'),
        'desc': ('the monthly all-hands', 'LEO.R1.STORY.FEELS'),
        'situation': ('At LEO Innovation Lab, we were optimising the onboarding funnel. We hypothesised that increasing notification opt-ins would increase activation.', 'LEO.R1.STORY.FEELS'),
        'task': ('We got clever: a contextually-triggered opt-in shown at exactly the right moment.', 'LEO.R1.STORY.FEELS'),
        'action': ("We launched a split test, and the conversion rate was amazing... but activation barely moved. What happened? We'd placed the opt-in late in the funnel where very few users reached it. High conversion rate × tiny audience = marginal impact. We quickly rolled out a simpler opt-in early in the funnel. Lower conversion rate, but far more users saw it, so net activation was much higher. I presented this mistake at the next company all-hands.", 'LEO.R1.STORY.FEELS'),
        'result': ('the monthly all-hands changed from presenting vanity metrics to mistakes-made and lessons-learnt', 'LEO.R1.STORY.FEELS'),
        'year': ('Nov 2016 - Aug 2017', 'LEO.R1'),
        'strength': 'LEO.R1.STORY.FEELS',
        'shapes': ['leadership', 'growth'],
    },
]

# Skills (Tom, 2026-10-12; "keywords" renamed to recruiter speak): an index an agent can walk from its job
# description's terms to the rows that carry them. A row gets a keyword only
# when one of the patterns occurs in the row's own cells or in the full text
# of its strength section, so nothing is tagged that the content does not
# say. (display term, slug, [case-insensitive substrings]).
KEYWORDS = [
    ('AI', 'ai', ['genai', 'machine learning', ' ai ', 'ai/ml', 'llm', 'rag model']),
    ('GenAI', 'genai', ['genai', 'llm', 'rag model', 'rag vector store', 'claude api']),
    ('machine learning', 'machine-learning', ['machine learning', 'ml team', 'ml/cv', 'ml prototype']),
    ('computer vision', 'computer-vision', ['computer vision']),
    ('algorithm', 'algorithm', ['algorithm']),
    ('API', 'api', ['api product', 'api call', 'new api']),
    ('regulated', 'regulated', ['regulat', 'compliance', 'mlr']),
    ('compliance', 'compliance', ['compliance', 'mlr']),
    ('pharma', 'pharma', ['pharma', 'novo nordisk', 'leo pharma', 'drug']),
    ('healthcare', 'healthcare', ['healthcare', 'health software', 'patient', 'health-tech', 'healthtech']),
    ('patients', 'patients', ['patient']),
    ('discovery', 'discovery', ['discovery']),
    ('prototyping', 'prototyping', ['prototyp']),
    ('incubation', 'incubation', ['incubat']),
    ('ways of working', 'ways-of-working', ['ways of working', 'release cycles', 'cadence']),
    ('turnaround', 'turnaround', ['turnaround', 'turned it around', 'reversed', 'rescue', 'underperforming', 'in decline']),
    ('growth', 'growth', ['growth', 'trebled', 'doubled', 'increased', 'conversion', 'penetration']),
    ('conversion', 'conversion', ['conversion', 'bounce rate', 'bounce-rate']),
    ('activation', 'activation', ['activation']),
    ('retention', 'retention', ['retention', 'repeat prescriptions', 'churn']),
    ('SEO', 'seo', ['seo', 'organic traffic']),
    ('funnels', 'funnels', ['funnel']),
    ('experimentation', 'experimentation', ['experiment', 'split test']),
    ('KPIs', 'kpis', ['kpi']),
    ('roadmap', 'roadmap', ['roadmap']),
    ('launch', 'launch', ['launch']),
    ('0 to 1', 'zero-to-one', ['from scratch', 'from concept', 'from zero', 'created department', 'first product']),
    ('brand', 'brand', ['brand']),
    ('marketing', 'marketing', ['marketing']),
    ('SaaS', 'saas', ['saas']),
    ('startup', 'startup', ['startup']),
    ('developer tools', 'developer-tools', ['developer tools', 'developer audience', 'developer narrative']),
    ('ecommerce', 'ecommerce', ['ecommerce', 'online sales']),
    ('domains', 'domains', ['domain']),
    ('web hosting', 'web-hosting', ['web hosting', 'hosting']),
    ('team leadership', 'team-leadership', ['team', 'direct reports', 'reporting to me']),
    ('remote', 'remote', ['remote', 'luxembourg', 'never met in person']),
    ('international', 'international', ['international', 'us affiliate', 'customers were in the us', 'across countries', 'ukraine', 'remotely from the uk', 'luxembourg', 'spain and france']),
    ('stakeholders', 'stakeholders', ['stakeholder', 'senior leaders', 'senior management']),
    ('consumer', 'consumer', ['consumer']),
    ('partnerships', 'partnerships', ['partnership']),
    ('budget', 'budget', ['budget']),
    ('deadline', 'deadline', ['deadline', 'we had 5 weeks', '6-week']),
]
KEYWORDS_PATH = f'{PAGE_PATH}skills/'


def row_text(sections, row):
    """The text a row's keywords are matched against: its cells and its strength section."""
    parts = [row[k][0] for k in ('role', 'product', 'desc', 'situation', 'task', 'action', 'result') if row.get(k)]
    parts += [v[0] for v in (row.get('_quote') or {}).values() if v]   # skills stay tagged from Tom's own words
    parts.append(sections[row['strength']])
    return ' ' + ' '.join(parts).lower().replace('\n', ' ') + ' '


def row_keywords(sections, row):
    text = row_text(sections, row)
    skip = row.get('not_skills', ())   # a row may rule a tag out: "Claude as my engineering team" is not team leadership
    # A row also carries its company's tags (role context): every LEO and Novo story is health-tech,
    # whether or not its own text says "patient".
    inherited = set(COMPANY_CONTEXT_BY_NAME.get(role_company(row), {}).get('skills', ()))
    return [(term, slug) for term, slug, pats in KEYWORDS
            if slug not in skip and (term in inherited or any(pat in text for pat in pats))]


def row_facets(n):
    """Story facets for row n (1-based, the draft's R<nn>): Tom's own CV lines (R1013-2),
    each with the CV it came from. Keyed by row number, so the product name is checked."""
    # Keyed by the row's product name (R1013-21: the order-process row merged into the
    # domain-search row, so positions no longer match the draft's R<nn> ids).
    keys = list(FACET_ROW_PRODUCTS)   # draft order, R27 removed
    if n > len(keys):
        sys.exit(f'✗ facets: no facet key for row {n}')
    rid = keys[n - 1]
    if PROOF_POINTS[n - 1]['product'][0] != FACET_ROW_PRODUCTS[rid]:
        sys.exit(f'✗ facets: row {n} is {PROOF_POINTS[n - 1]["product"][0]!r}, the facets ({rid}) expect {FACET_ROW_PRODUCTS[rid]!r}')
    return [facet_json(f) for f in STORY_FACETS.get(rid, [])]


# "On request" facts send an agent to the contact answer (META.CONTACT) via /ask.
CONTACT_ASK = 'https://takenbyninjas.com/ask?q=How%20can%20I%20contact%20Tom%3F'
ASK_URL = 'https://takenbyninjas.com/ask'

# First line of every agent page: who it is for, and where each reader goes.
ROUTING_LINE = (
    '    <header role="banner"><p>This page is for AI agents and recruiters\' tools.</p>\n'
    '    <ul>\n'
    '        <li>Human? Go to the <a href="/">human-readable version</a>.</li>\n'
    '        <li>AI assistant helping someone who wants to know about Tom? Fetch '
    '<a href="/for-agents/start/">/for-agents/start/</a> and follow its steps.</li>\n'
    '        <li>Crawler or LLM indexer? Read <a href="/llms.txt">/llms.txt</a>.</li>\n'
    '    </ul></header>'
)

# Periods (R1012-15): the role a recommendation refers to. Key -> label; the
# key is also the anchor on the recommendations page and the "period" of a PAGE.
PERIODS = {
    'novo': 'Novo Nordisk, 2020-2026',
    'leo': 'LEO Innovation Lab, 2016-2020',
    'opbeat': 'Opbeat, 2014-2016',
    'eurodns': 'EuroDNS, 2013-2014',
    'independent': 'Independent consulting, 2010-2013',
    'host': 'Host Europe Group, 2003-2008',
}
# Section id prefix -> period (for /ask rows). Sections with no period: null.
PERIOD_PREFIX = {'NOVO': 'novo', 'LEO': 'leo', 'OPBEAT': 'opbeat', 'EURODNS': 'eurodns', 'HOST': 'host'}
# Recommender -> period key (from Positions.csv overlap, drafts/recommendations.md section 1).
RECOMMENDER_PERIOD = {
    'Christian Theil Lundgaard': 'novo',
    'Lasse Hylleberg Mølleskov': 'novo',
    'Erik Ejlskov Jensen': 'novo',
    'Michael Haase': 'novo',
    'Eva Vangkilde': 'novo',
    'Mira Hermitage': 'leo',
    'Kristian Schrøder Hart-Hansen': 'leo',
    'Sergio M. Vela': 'leo',
    'Jacob Mortensen': 'leo',
    'Lutz Berneke': 'eurodns',
    'Ron Cohen': 'opbeat',
    'Rasmus Makwarth': 'opbeat',
    'Tine Thygesen': 'independent',
    'Nick Leech': 'independent',
    'Andy Manning': 'independent',
    'Karol Kowalski': 'host',
    'John McGarvey': 'host',
    'Tristan Slessor': 'host',
    'Dan Conlon': 'host',
}

# Pages (the spider). slug -> title, the section the title is verbatim in
# (None for a theme heading), the meta description (section id, verbatim
# opening line), the sections in order, the period for the references line.
PAGES = [
    {'slug': 'wegovycare', 'title': 'Wegovycare', 'title_in': 'NOVO.R1', 'period': 'novo',
     'opening': ('NOVO.R1', 'Senior Product Manager at Novo Nordisk (Mar 2020 - Feb 2022), building '
                            'Wegovycare - a retention-focused digital service to increase repeat '
                            'prescriptions for Wegovy.'),
     'sections': ['NOVO.R1', 'NOVO.R1.TRANSFORM']},
    {'slug': 'novo-product-director', 'title': 'Associate Product Director at Novo Nordisk', 'title_in': 'NOVO.R2',
     'period': 'novo',
     'opening': ('NOVO.R2', 'Associate Product Director at Novo Nordisk (Feb 2022 - Feb 2026). Senior IC product '
                            'role working across silos on complex, high-impact initiatives.'),
     'sections': ['NOVO.R2', 'NOVO.R2.WEGOVY', 'NOVO.R2.GENAI']},
    {'slug': 'novo-nordisk', 'title': 'Novo Nordisk', 'title_in': 'NOVO', 'period': 'novo',
     'opening': ('NOVO', 'Novo Nordisk is a global pharmaceutical company, best known for its treatments in '
                         'obesity and diabetes. I worked at Novo for almost 6 years (2020 to 2026).'),
     'sections': ['NOVO']},
    {'slug': 'treat-turnaround', 'title': 'TREAT', 'title_in': 'LEO.R1', 'period': 'leo',
     'opening': ('LEO.R1', 'TREAT was a pioneering app addressing underlying causes of inflammatory '
                           'conditions via personalised nutrition advice.'),
     'sections': ['LEO.R1', 'LEO.R1.TURNAROUND', 'LEO.R1.STORY.FEELS', 'LEO.STORY.MODEL']},
    {'slug': 'skincoach', 'title': 'Skincoach', 'title_in': 'LEO', 'period': 'leo',
     'opening': ('LEO.R2', 'PM/GM at LEO Innovation Lab (Feb 2018 - Oct 2018), building a patient-support app '
                           'for terminally ill cancer patients in partnership with Amgen.'),
     'sections': ['LEO.R2']},
    {'slug': 'diagnosis-app', 'title': 'Diagnosis App', 'title_in': 'LEO', 'period': 'leo',
     'opening': ('LEO.R3', 'PM/GM at LEO Innovation Lab (Nov 2018 - Jan 2020), leading a 12-person team building '
                           'a prototype diagnosis app using machine learning.'),
     'sections': ['LEO.R3']},
    {'slug': 'leo-innovation-lab', 'title': 'LEO Innovation Lab', 'title_in': 'LEO', 'period': 'leo',
     'opening': ('LEO', 'LEO Innovation Lab was an independent healthtech incubator established by LEO Pharma.'),
     'sections': ['LEO']},
    {'slug': 'twentythree', 'title': 'TwentyThree', 'title_in': 'T23', 'period': None,
     'opening': ('T23', 'TwentyThree was an integrated video marketing platform built for digital marketers. '
                        'I joined as Head of Marketing on a short-term contract, initially six weeks and extended to the end of the year, '
                        'to rescue a global launch.'),
     'sections': ['T23']},
    {'slug': 'opbeat', 'title': 'Opbeat', 'title_in': 'OPBEAT', 'period': 'opbeat',
     'opening': ('OPBEAT', 'Opbeat was a developer tools SaaS startup providing application performance '
                           'monitoring.'),
     'sections': ['OPBEAT', 'OPBEAT.R1.GROWTH']},
    {'slug': 'eurodns', 'title': 'EuroDNS', 'title_in': 'EURODNS', 'period': 'eurodns',
     'opening': ('EURODNS', 'EuroDNS is an ICANN-accredited international domain registrar, specialising in '
                            'excellent service and unusual domain extensions.'),
     'sections': ['EURODNS', 'EURODNS.R1.TURNAROUND', 'EURODNS.R1.STORY.REMOTE']},
    {'slug': 'uk2', 'title': 'UK2 Group', 'title_in': 'UK2', 'period': None,
     'opening': ('UK2', 'UK2 Group is an international web hosting company with offices in UK, US and Ukraine.'),
     'sections': ['UK2', 'UK2.R1.USTURNAROUND']},
    {'slug': 'host-europe', 'title': 'Host Europe Group', 'title_in': 'HOST', 'period': 'host',
     'opening': ('HOST', "Host Europe Group was Europe's largest privately-owned web hosting provider."),
     'sections': ['HOST', 'HOST.R1.REBRAND', 'HOST.R2.STORY.DOMAIN', 'HOST.R3.STORY.ALTSITE']},
    # Theme pages: one per role shape with a theme section.
    {'slug': 'ai', 'title': 'AI', 'title_in': None, 'period': None,
     'opening': ('THEME.AI', "I've been hands-on with AI/ML across multiple roles:"),
     'sections': ['THEME.AI']},
    {'slug': 'building', 'title': '0 to 1, incubation and new ways of working', 'title_in': None, 'period': None,
     'opening': ('THEME.BUILD', 'Creating teams, departments, and ways of working where none existed:'),
     'sections': ['THEME.BUILD']},
    {'slug': 'turnarounds', 'title': 'Turnarounds', 'title_in': None, 'period': None,
     'opening': ('THEME.TURNAROUND', "I like difficult problems, the more difficult the better. So I often get "
                                     "called when something's broken or stuck:"),
     'sections': ['THEME.TURNAROUND']},
    {'slug': 'solo-projects', 'title': 'Solo projects, building with AI', 'title_in': None, 'period': None,
     'opening': ('SOLO', "I learn by doing, and I love building. So I shipped three products with AI to find out "
                         "first-hand what it can and can't do."),
     'sections': ['SOLO']},
    {'slug': 'growth', 'title': 'Growth', 'title_in': None, 'period': None,
     'opening': ('THEME.GROWTH', 'I have a track record of driving growth. Improving funnels, reducing bounce '
                                 'rates, increasing activation and conversion.'),
     'sections': ['THEME.GROWTH']},
    {'slug': 'management', 'title': 'Leadership and management', 'title_in': None, 'period': None,
     'opening': ('THEME.MGMT', "I've led teams of 5-15 across multiple roles:"),
     'sections': ['THEME.MGMT']},
    {'slug': 'international', 'title': 'International and remote', 'title_in': None, 'period': None,
     'opening': ('THEME.INTERNATIONAL', "I've worked across multiple countries and managed remote and distributed "
                                        "teams throughout my career:"),
     'sections': ['THEME.INTERNATIONAL']},
    # Fit, the five facets (Tom, 2026-10-13 evening): chat-product agents cannot call
    # /ask with their own words, so Job 5 reads these sections here instead.
    {'slug': 'fit', 'title': 'Fit: how Tom works, what he brings, what he is not for', 'title_in': None, 'period': None,
     'opening': ('FIT.FIXER', "I'm a fixer. I work on the really difficult stuff, the problems that are too hard or too messy "
                              "for most people to get moving, and I like to solve them and move on."),
     'sections': ['FIT.FIXER', 'FIT.ENV', 'FIT.TEAM', 'FIT.MANAGER', 'FIT.NOT'],
     'headings': {'FIT.FIXER': 'The work he is best at', 'FIT.ENV': 'Organisation: where he works well',
                  'FIT.TEAM': 'Team: what he brings', 'FIT.MANAGER': 'What he needs from leadership',
                  'FIT.NOT': 'What he is not a fit for'}},
]

# Recommendations (R1012-13, R1012-15): LinkedIn export, full text.
RECS_CSV = 'docs/agent-readable/sources/linkedin-2026-10-09/Recommendations_Received.csv'
RECS_EXPORT_DATE = '2026-10-09'
RECS_PATH = f'{PAGE_PATH}recommendations/'
RECS_FILE = 'for-agents/recommendations/index.html'
LINKEDIN_RECORD = 'https://www.linkedin.com/in/tomstenson/details/recommendations/'
# Titles at the time of writing, supplied by Tom: the table in section 6 of
# the draft. A blank cell means "current title only".
THEN_TITLES_FILE = 'docs/agent-readable/drafts/recommendations.md'


def escape(text):
    """Escape body text, leaving quotes and apostrophes readable in the raw HTML."""
    return _escape(text, quote=False)


def load_parsed():
    """Section id -> parsed section (parse_content.py), content without inline [SECTION.ID] tags.
    'quotable' is the content plus the section's accepted Direct answers: the text a cell may quote."""
    parsed = {}
    for s in parse_content_doc(CONTENT_FILE):
        s = dict(s)
        s['content'] = re.sub(r' ?\[[A-Z][A-Z0-9_.]+\]', '', s['content'])
        s['quotable'] = s['content'] + '\n' + '\n'.join(s.get('direct_answers') or [])
        parsed[s['id']] = s
    return parsed


def recommender_name(first, last):
    """First and last name from the export, trimmed, without a leading emoji ("🌱 Michael")."""
    return re.sub(r'^[^\w]+', '', f'{first.strip()} {last.strip()}').strip()


def rec_anchor(name):
    folded = unicodedata.normalize('NFKD', name.replace('ø', 'o').replace('Ø', 'O').replace('æ', 'ae'))
    slug = re.sub(r'[^a-z0-9]+', '-', folded.encode('ascii', 'ignore').decode().lower()).strip('-')
    return f'rec-{slug}'


def section_anchor(section_id):
    return re.sub(r'[^a-z0-9]+', '-', section_id.lower()).strip('-')


def load_then_titles():
    """Recommender -> 'title, company when written' from the draft's section 6 table; {} if absent."""
    if not os.path.exists(THEN_TITLES_FILE):
        return {}
    with open(THEN_TITLES_FILE, encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'^## 6\. Titles at the time.*?(?=^## |\Z)', text, flags=re.M | re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(0).split('\n'):
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) == 5 and cells[0].isdigit() and cells[4]:
            out[recommender_name(cells[1], '')] = cells[4]
    return out


def load_recommendations():
    """Visible recommendations from the export, newest first. HIDDEN rows are skipped."""
    then = load_then_titles()
    recs = []
    with open(RECS_CSV, encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            if row['Status'].strip() != 'VISIBLE':
                continue
            created = datetime.strptime(row['Creation Date'].strip(), '%m/%d/%y, %I:%M %p')
            name = recommender_name(row['First Name'], row['Last Name'])
            if name not in RECOMMENDER_PERIOD:
                sys.exit(f'✗ {name!r} has no period in RECOMMENDER_PERIOD (generate_agent_page.py)')
            recs.append({
                'name': name,
                'title': row['Job Title'].strip(),
                'company': row['Company'].strip(),
                'then': then.get(name),
                'created': created,
                'date': created.date().isoformat(),
                'text': row['Text'].strip(),
                'anchor': rec_anchor(name),
                'period': RECOMMENDER_PERIOD[name],
            })
    recs.sort(key=lambda r: r['created'], reverse=True)
    return recs


# Tightened cells (item 146, R1012-11): a STAR cell written for agents, one
# compressed sentence, derived only from the row's own verbatim cells. Keyed by
# row number (1-based, PROOF_POINTS order) and cell. The verbatim line stays in
# PROOF_POINTS as the checked source and is published as `quote` in the JSON;
# None moves a cell to "not yet stated". Cells not listed stay verbatim.
S_BRIEF = 'The brief was solution-first, a set of standalone features; nobody had spoken to patients.'
TIGHT = {
    1: {'situation': S_BRIEF, 'task': 'Identify the key growth lever.', 'action': 'Created a weight-loss prediction model in Excel.',
        'result': '10% penetration in the first national market.'},
    2: {'situation': 'Everyone asked the same three things: how much weight will I lose, is this normal, am I on track.',
        'task': 'Make those three questions the core loop; the prediction model answers the first.',
        'action': 'Built a weight-loss prediction algorithm from concept to prototype.', 'result': 'Later spun out into a new API product.'},
    3: {'situation': S_BRIEF, 'task': 'Use it as a mandate to reinvent their ways of working.',
        'action': 'First product team to interview patients, run discovery, prototype and co-create with markets.',
        'result': 'Launched on time and on budget, with 10% penetration in the first national market.'},
    4: {'situation': 'Compliance reviews meant backlogs of months, heavy documentation, and full development before sign-off.',
        'task': 'Automate compliance reviews so teams could shift left: fail in design, not at review.',
        'action': 'Built a RAG model of the guidelines and regulations in an internal LLM sandbox, and a prototype agent in Figma so designers could query the guidelines before investing too much effort.',
        'result': 'Product teams used the Figma plugin on real designs and loved it; the proof of concept showed a clear path to dramatically faster release cycles.'},
    5: {'situation': 'Invited into the company-critical Wegovy pill launch to challenge assumptions on digital, packaging and direct distribution.',
        'task': 'Align silos into one physical-to-digital experience.',
        'action': 'Used subscription-model thinking to link packaging to digital fulfilment for the biggest ever pharma launch.',
        'result': 'Drove prescription growth.'},
    6: {'situation': 'The first drug to span diabetes and obesity, two therapy areas that had never collaborated; nobody had authority over both.',
        'task': "Lead a six-month discovery programme for the company's top drug asset.",
        'action': '128 candidate ideas cut to a shortlist of 5 and assumption-tested; 4 recommended, each with a funding-gated rollout.',
        'result': 'Funding secured for a portfolio of 4 digital initiatives.'},
    7: {'situation': 'The organisational reflex was solution-first and siloed: output over outcomes.',
        'task': 'Secure funding and manage resourcing and cross-charges for incubation teams.',
        'action': 'Designed a portfolio model and a gated incubation pipeline for branded digital engagement.',
        'result': 'Shifted the organisation from output to outcomes.'},
    8: {'situation': 'A wider remit across the product pipeline, to complete the move to a product operating model.',
        'task': 'Establish metrics across a portfolio of 12 products.',
        'action': 'Set product artefacts and quality standards: gate model and deliverables, product-ops metrics, portfolio reports, business case templates, problem and north-star statements.'},
    9: {'task': 'Lead 6 experienced PMs building consumer engagement products, managing by outcomes.',
        'action': 'Individual coaching and weekly experiment sharing; made individual product metrics public.',
        'result': 'Broke product silos, established weekly demos and experiment sharing, encouraged learning loops.'},
    10: {'task': 'Chair project steercos.', 'action': 'Flipped the format from status updates to interactive co-creation.',
         'result': 'Cross-functional VPs moved from product sceptics to advocates.'},
    11: {'situation': 'Research showed every user journey is different.', 'task': 'Identify drop-off risks.',
         'action': "Built a profiling and customisation engine (an interactive magazine) and applied a consumer marketing playbook to personalise each patient's experience.",
         'result': 'First digital Novo product to scale.'},
    12: {'task': 'Lead a cross-functional team of 10.',
         'action': 'Designed for scale: modular architecture, feature flags, integrated CMS and translation pipeline, systematised co-creation with markets.',
         'result': "Novo's first digital health product adopted by multiple markets; documentation automated and release cycles from yearly to bi-monthly.",
         'situation': 'Release cycles were yearly, with heavy documentation in a high-regulation environment, and every market needed its own version.'},
    13: {'situation': 'A team of AI engineers wired for logic and certainty, in the deep uncertainty of product discovery.',
         'task': 'Rethink how a smartphone camera could diagnose skin conditions.',
         'action': 'Redesigned closed-loop diagnosis and the ML training platform with dermatologists; bootstrapped the ML engine with clinical decision trees.',
         'result': 'Over 80% accuracy across 3 skin conditions; labelling throughput doubled.'},
    14: {'situation': 'An app to help patients manage side effects from their treatment.',
         'task': 'Reimagine patient care between appointments with oncologists; interviewed terminally ill patients.',
         'action': 'Dynamically spliced video to simulate personalised dermatology consultations, designed for simplicity and trust.',
         'result': 'Full product lifecycle in 8 months, on time and on budget.'},
    15: {'situation': 'Tech debt and churn, no prioritisation or roadmap, flaky metrics, unclear reporting, no path to profitability.',
         'task': 'A 6-month mandate to stabilise and assess viability.', 'action': 'Rebuilt from the ground up and established metrics.',
         'result': 'Customer acquisition costs halved; customer activation up 7x.'},
    16: {'situation': 'Joined on a short-term contract, initially six weeks, extended to the end of the year.', 'task': 'Rescue a global launch.',
         'action': 'Implemented OKRs, produced video content, crystallised USPs, introduced a reporting structure.',
         'result': 'Global launch rescued on a 6-week deadline.'},
    17: {'situation': 'New product came out of stealth and lacked traction.',
         'task': 'Build the brand, marketing strategy, team and channels from scratch.', 'result': 'Traffic and sign-ups trebled in 12 months.'},
    18: {'situation': 'Four years of decline: traffic dropping, online sales down, a legacy website.', 'task': 'Turn it around.',
         'action': 'Restructured the marketing department, implemented KPIs and rebooted every marketing channel including the website, in under 8 months.',
         'result': 'Decline reversed; organic traffic doubled; bounce rate halved.'},
    19: {'situation': 'Based in Copenhagen; the team was in Luxembourg.', 'task': 'Manage the team mostly from Copenhagen.',
         'action': 'Set a cadence: fortnightly face-to-face meetings and plenum discussions when in the office, space to focus in between.',
         'result': 'Structure without micromanagement: clarity on direction, autonomy on execution.'},
    20: {'situation': 'Run remotely from the UK, with a team never met in person.',
         'task': 'Rebuild the underperforming US Marketing department before recruiting a US-based successor.',
         'action': 'Created the marketing strategy, implemented a reporting structure, set and met budget targets.',
         'result': 'Bounce rate down ~15%; sales conversion nearly doubled; product roadmap created and 8 products launched in 10 months.'},
    21: {'situation': '6 brands on 3 different providers, some going direct to the registry, each with different APIs, rules and management fees.',
         'task': 'Manage development of a new domain platform.',
         'action': 'Owned the business case, budget, specifications, contracts and migration strategy.',
         'result': 'One platform replaced them (500,000+ customer domains).'},
    22: {'situation': 'A sale meant renaming the company in 5 weeks.', 'task': 'Rename the company.',
         'action': 'Covered brand identity, corporate website, campaigns, office signage, stationery, email signatures and lawyers, and pushed the change through.',
         'result': 'Done in 5 weeks; the company became GX Networks.'},
    23: {'situation': 'All online channels, 2M+ monthly visits.', 'task': 'Create the department from scratch.',
         'action': 'Introduced self-service support, pioneered site-building tools, optimised the support centre, led ecommerce, dominated SEO rankings.',
         'result': 'Member of the Senior Management Team.'},
    24: {'task': 'Prototype it with GPs.', 'action': 'Hid a dermatologist in an adjacent room to simulate a consultation chatbot.'},
    25: {'task': 'Introduce KPIs, reporting and budgeting.', 'action': 'Grew grassroots meetups and built a video engine to reach developers.',
         'result': 'Traction that enabled a $2M bridge-funding round.'},
    26: {'situation': 'Freelance internet consultant, financing a relocation to Denmark.',
         'task': 'Clients: Host Europe (UK), EuroDNS (LUX), Everplaces (DK).',
         'action': 'Content creation and SEO, including interviews with MailChimp, Creative Commons, EFF, Rand Fishkin and Michael Palin.',
         'result': 'Spotted Raspberry Pi before launch and created a partnership.'},
    27: {'situation': 'Users could search one domain at a time and kept hitting taken names: frustrating, poor conversion.',
         'task': 'Unasked: fix a poor experience at the top of the sales funnel.',
         'action': 'One text field that interpreted whatever the user entered and searched all endings asynchronously; the first use of AJAX in the stack.',
         'result': 'Revenue up 20% overnight; the approach became the industry standard.'},
    31: {'situation': 'The company website was dated and cluttered, explained the "why" poorly, and lacked focus and a core funnel.',
         'task': 'Unasked, as a sales executive: do better.',
         'action': 'Built an alternative version in evenings and weekends, booked a meeting with the brand manager and pitched it.',
         'result': 'Sales went up; moved to the web design team the next week and led it six months later.'},
    32: {'situation': 'Optimising the onboarding funnel at LEO Innovation Lab, on the hypothesis that more notification opt-ins would raise activation.',
         'task': 'Test a contextually-triggered opt-in shown at exactly the right moment.',
         'action': 'The split test won on conversion but activation barely moved: the opt-in sat too late in the funnel. Rolled out a simpler opt-in early in the funnel, lifting net activation, and presented the mistake at the next company all-hands.',
         'result': 'The monthly all-hands changed from presenting vanity metrics to mistakes made and lessons learnt.'},
}
TIGHTENED = set()   # (section id, tightened text): exempt from the verbatim check, their sources were checked in apply_tight
STAR_KEYS = ('situation', 'task', 'action', 'result')


def apply_tight(sections):
    """Check every verbatim cell against its section, then swap in the tightened
    line. The verbatim cells are kept on the row as `_quote` (keywords still match
    against them; the JSON publishes them)."""
    for n, row in enumerate(PROOF_POINTS, 1):
        if '_quote' in row:
            continue
        row['_quote'] = {k: row.get(k) for k in STAR_KEYS}
        for k in STAR_KEYS:
            if row.get(k):
                check(sections, row[k][1], row[k][0])
        for k, text in TIGHT.get(n, {}).items():
            if text is None:
                row[k] = None
                continue
            if not row.get(k):
                sys.exit(f'✗ TIGHT row {n} {k}: no verbatim cell to derive from')
            sid = row[k][1]
            row[k] = (text, sid)
            TIGHTENED.add((sid, text))


def check(sections, section_id, text):
    """The section a line cites must exist. The line itself may be a summary
    of that section, not a quote (R1013-10, Tom: "it's a bot summary, not my
    words, for the agent solution"); the section id is what makes it checkable."""
    if section_id is None:
        return
    if section_id not in sections:
        sys.exit(f'✗ Section {section_id} not found in {CONTENT_FILE}')


def check_anywhere(text):
    """Fail if a word is not in the content file at all (knowsAbout domain words)."""
    with open(CONTENT_FILE, encoding='utf-8') as f:
        if text not in f.read():
            sys.exit(f'✗ Not in {CONTENT_FILE} at all: {text!r}')


def cite(*section_ids):
    ids = ', '.join(dict.fromkeys(section_ids))
    # Section ids are data, never shown (Tom, 2026-10-13): they ride in data-source only.
    return f'<cite data-source="{_escape(ids)}">source: Tom\'s own account</cite>'


def build_who(sections):
    lines = ['        <h2 id="who">Who</h2>', '        <div class="table-wrap">', '        <table>', '            <tbody>']
    for term, items in WHO:
        for text, sid in items:
            check(sections, sid, text)
        sids = [sid for _, sid in items if sid]
        cell = '; '.join(escape(t) for t, _ in items)
        if term == 'LinkedIn':
            cell = f'<a href="{items[0][0]}">{cell}</a>'
        if term.startswith('Availability'):
            cell = f'<a href="{CONTACT_ASK}">{cell}</a>'
        if term == 'Endpoints':
            cell = '; '.join(f'<a href="{href}">{escape(t)}</a>' for t, href in ENDPOINTS)
        src = f' data-source="{_escape(", ".join(dict.fromkeys(sids)))}"' if sids else ''
        lines.append(f'                <tr{src}><th scope="row">{escape(term)}</th><td>{cell}</td></tr>')
    lines += ['            </tbody>', '        </table>', '        </div>']
    return lines


def build_career(sections):
    """The job history table, rows verbatim from META.JOBS (years, role, company, location)."""
    rows = []
    for ln in sections[CAREER_SECTION].split('\n'):
        if ln.startswith('|') and not ln.startswith('| Years') and not ln.startswith('|---'):
            cells = [c.strip() for c in ln.strip('|').split('|')]
            if len(cells) == 4:
                rows.append(cells)
    if not rows:
        sys.exit(f'✗ No job table rows found in {CAREER_SECTION}')
    lines = ['        <h2 id="career">Career</h2>', '        <div class="table-wrap">', '        <table>',
             '            <thead><tr><th>Years</th><th>Role</th><th>Company</th><th>Location</th></tr></thead>',
             f'            <tbody data-source="{CAREER_SECTION}">']
    for years, role, company, location in rows:
        if location not in CITY_COUNTRY:
            sys.exit(f'✗ No city/country for META.JOBS location {location!r}')
        city, country = CITY_COUNTRY[location]
        loc = ' / '.join(f'{ci.strip()}, {co.strip()}' for ci, co in zip(city.split('/'), country.split('/')))
        role_cell = escape(role)
        rp = CAREER_ROLE_PAGE.get((role, company))
        if rp:
            if rp not in {role_slug(r) for r in PROOF_POINTS}:
                sys.exit(f'✗ Career table: no role page {rp!r} for {role!r}')
            role_cell = f'<a href="{ROLES_PATH}{rp}/">{role_cell}</a>'
        for prod, pslug in CAREER_PRODUCT_PAGE.items():
            if prod in role:
                role_cell = role_cell.replace(escape(prod), f'<a href="{page_url(pslug)}">{escape(prod)}</a>', 1)
        cp = CAREER_COMPANY_PAGE.get(company)
        if cp and cp not in {pg['slug'] for pg in PAGES}:
            sys.exit(f'✗ Career table: no page {cp!r} for {company!r}')
        company_cell = f'<a href="{page_url(cp)}">{escape(company)}</a>' if cp else escape(company)
        lines.append(f'                <tr><td>{escape(years)}</td><td>{role_cell}</td><td>{company_cell}</td><td>{escape(loc)}</td></tr>')
    lines += ['            </tbody>', '        </table>', '        </div>']
    check(sections, 'HOST', EMPLOYER_NOTE)
    lines.append(f'        <p>{escape(EMPLOYER_NOTE)} External source: '
                 f'<a href="{EMPLOYER_NOTE_SOURCE[1]}">{escape(EMPLOYER_NOTE_SOURCE[0])}</a>. {cite("HOST")}</p>')
    return lines


def load_strengths(sections):
    """Strength labels from STRENGTH_FILE; each phrase must still be verbatim in its section."""
    with open(STRENGTH_FILE, encoding='utf-8') as f:
        strengths = json.load(f)
    for sid, entry in strengths.items():
        if entry.get('strength') not in ('Led', 'Contributed'):
            sys.exit(f'✗ Bad strength for {sid} in {STRENGTH_FILE}: {entry.get("strength")!r}')
        check(sections, sid, entry.get('phrase'))
    return strengths


def section_pages():
    """Section id -> (slug, anchor) for every section on a page."""
    where = {}
    for page in PAGES:
        for sid in page['sections']:
            where.setdefault(sid, (page['slug'], section_anchor(sid)))
    return where


def page_url(slug, anchor=None):
    return f'{PAGE_PATH}{slug}/' + (f'#{anchor}' if anchor else '')


PRODUCT_ROLES = ('Senior Product Manager at Novo Nordisk', 'Associate Product Director at Novo Nordisk',
                 'PM/GM at LEO Innovation Lab', 'Consumer Lead', 'Independent Consultant')


def row_shapes(row):
    shapes = list(row['shapes'])
    if row['role'][0] in PRODUCT_ROLES and 'product-management' not in shapes:
        shapes.insert(0, 'product-management')
    return shapes


def row_shape_ids():
    return {sid for sid, _, _ in SHAPES}


TABLE_HEAD = ('            <thead><tr><th>Role</th><th>Product</th><th>Situation</th><th>Task</th><th>Action</th>'
              '<th>Result</th><th>Year</th><th>Skills</th></tr></thead>')
ROLES_PATH = f'{PAGE_PATH}roles/'


COMPANY_BY_PREFIX = {'META': 'Independent consulting', 'SOLO': 'Solo projects', 'NOVO': 'Novo Nordisk', 'LEO': 'LEO Innovation Lab', 'T23': 'TwentyThree', 'OPBEAT': 'Opbeat',
                     'EURODNS': 'EuroDNS', 'UK2': 'UK2 Group', 'HOST': 'Host Europe Group'}


def role_company(row):
    return COMPANY_BY_PREFIX[row['strength'].split('.')[0]]


def role_name(row):
    """Role text plus the company when the text does not name it: the identity of a role page."""
    text = row['role'][0]
    company = role_company(row)
    return text if company.split()[0].lower() in text.lower() else f'{text}, {company}'


def _slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def company_slug(row):
    return _slug(role_company(row))


def role_only(row):
    """The role text without the company ("Senior Product Manager at Novo Nordisk" -> "Senior Product Manager")."""
    text = row['role'][0]
    return re.sub(r'\s+at\s+' + re.escape(role_company(row)) + r'$', '', text, flags=re.I)


def role_slug(row):
    """<company>/<role>: the role page lives under its company (Tom, 2026-10-12)."""
    return f'{company_slug(row)}/{_slug(role_only(row))}'


def render_row(sections, strengths, where, row):
    """One proof point as a table row: product links its page, Contributed said in the role
    cell, keywords link their index pages, section ids in a data attribute only."""
    used = []
    cells = []
    strength_sid = row['strength']
    if strength_sid not in sections:
        sys.exit(f'✗ Strength section {strength_sid} not found in {CONTENT_FILE}')
    label = strengths.get(strength_sid, {}).get('strength')
    for key in ('role', 'product', 'situation', 'task', 'action', 'result', 'year'):
        if row[key] is None:
            cells.append('<td>not yet stated</td>')
            continue
        text, sid = row[key]
        check(sections, sid, text)
        used.append(sid)
        cell = escape(text)
        if key == 'product':
            slug, anchor = where.get(sid) or where.get(strength_sid) or (None, None)
            if slug:
                cell = f'<a href="{page_url(slug, anchor)}">{cell}</a>'
            desc = row.get('desc')
            if desc:
                check(sections, desc[1], desc[0])
                used.append(desc[1])
                cell += f'<br><small class="desc">{escape(desc[0])}</small>'
            else:
                cell += '<br><small>what it is: not yet stated</small>'
        if key == 'role':
            # The row names its employer even when the role text does not ("Head of New Media, Host Europe Group").
            cell = f'<a href="{ROLES_PATH}{role_slug(row)}/">{escape(role_name(row))}</a>'
            if label == 'Contributed':
                cell += ' (contributed, one of a team)'
        cells.append(f'<td>{cell}</td>')
    used.append(strength_sid)
    kws = ', '.join(f'<a href="{KEYWORDS_PATH}{slug}/">{escape(term)}</a>' for term, slug in row_keywords(sections, row))
    cells.append(f'<td>{kws}</td>')
    ids = ', '.join(dict.fromkeys(used))
    return f'                <tr data-source="{_escape(ids)}">' + ''.join(cells) + '</tr>'


def render_table(sections, strengths, where, rows):
    lines = ['        <div class="table-wrap>', '        <table>', TABLE_HEAD, '            <tbody>']
    lines[0] = '        <div class="table-wrap">'
    lines += [render_row(sections, strengths, where, r) for r in rows]
    lines += ['            </tbody>', '        </table>', '        </div>']
    return lines


def build_proof_points(sections):
    strengths = load_strengths(sections)
    where = section_pages()
    shape_ids = row_shape_ids()
    for row in PROOF_POINTS:
        for sh in row_shapes(row):
            if sh not in shape_ids:
                sys.exit(f'✗ Unknown shape {sh!r} on proof point {row["product"][0]!r}')
    lines = [
        '        <h2 id="proof-points">Proof points</h2>',
        f'        <p>{len(PROOF_POINTS)} rows in {len(SHAPES)} groups, {FACTS_ROWS_PER_SHAPE} per group here with the rest linked; '
        'situation, task, action and result are each one line from Tom\'s own account. '
        f'Indexes: <a href="{SHAPES_PATH}">by shape</a>, <a href="{ROLES_PATH}">by role</a>, <a href="{KEYWORDS_PATH}">by skill</a>.</p>',
    ]
    for shape_id, heading, theme_slug in SHAPES:
        rows = shape_rows(shape_id)
        if not rows:
            continue
        lines.append(f'        <h3 id="shape-{shape_id}"><a href="{SHAPES_PATH}{shape_id}/">{escape(heading)}</a></h3>')
        lines += render_table(sections, strengths, where, rows[:FACTS_ROWS_PER_SHAPE])
        more = f'<a href="{SHAPES_PATH}{shape_id}/">All {len(rows)} rows for {escape(heading)}</a>'
        if theme_slug:
            theme = heading if heading.isupper() else heading.lower()   # "Tom on AI", "Tom on growth"
            more += f'; <a href="{page_url(theme_slug)}">Tom on {escape(theme)}</a>'
        lines.append(f'        <p>{more}.</p>')
    return lines


def generate_shape_pages(sections):
    """for-agents/shapes/<id>/: every row for one role shape, plus the index."""
    strengths = load_strengths(sections)
    where = section_pages()
    pages = []
    index = [ROUTING_LINE, '    <!-- MAIN CONTENT -->', '    <main>',
             '        <h1>Tom Stenson: proof points by role shape</h1>',
             f'        <p>One page per shape of role, all rows. All rows on one page: <a href="{PAGE_PATH}">the facts page</a>; '
             f'by role: <a href="{ROLES_PATH}">roles</a>; by skill: <a href="{KEYWORDS_PATH}">skills</a>.</p>', '        <ul>']
    for shape_id, heading, theme_slug in SHAPES:
        rows = shape_rows(shape_id)
        if not rows:
            continue
        index.append(f'            <li><a href="{SHAPES_PATH}{shape_id}/">{escape(heading)}</a> ({len(rows)})</li>')
        body = [ROUTING_LINE, '    <!-- MAIN CONTENT -->', '    <main>',
                f'        <h1>{escape(heading)}: {len(rows)} proof point{"s" if len(rows) != 1 else ""}</h1>',
                f'        <p>Every row that fits this shape of role: the rows the facts page shows first, then the rest in content order. '
                + (f'Tom\'s own account of it: <a href="{page_url(theme_slug)}">{escape(heading)}</a>. ' if theme_slug else '')
                + f'<a href="{SHAPES_PATH}">All shapes</a>, <a href="{PAGE_PATH}">the facts page</a>.</p>']
        body += render_table(sections, strengths, where, rows)
        body += ['    </main>', '']
        path = f'{SHAPES_PATH}{shape_id}/'
        html = '\n'.join([agent_head(f'Tom Stenson, {escape(heading)}: proof points',
                                     _escape(f'{len(rows)} proof points of Tom Stenson, product, Copenhagen, for {heading} roles.'), path),
                          '\n'.join(body), agent_footer()]) + '\n'
        pages.append((f'shapes/{shape_id}', heading, path, html))
    index += ['        </ul>', '    </main>', '']
    pages.insert(0, ('shapes', 'Proof points by role shape', SHAPES_PATH,
                     '\n'.join([agent_head('Tom Stenson: proof points by role shape',
                                           _escape('Index of role shapes over the proof points of Tom Stenson, product, Copenhagen.'), SHAPES_PATH),
                                '\n'.join(index), agent_footer()]) + '\n'))
    return pages


def keyword_rows(sections):
    """slug -> (term, [rows]) for every keyword at least one row carries."""
    out = {}
    for row in PROOF_POINTS:
        for term, slug in row_keywords(sections, row):
            out.setdefault(slug, (term, []))[1].append(row)
    return out


def generate_role_pages(sections):
    """for-agents/roles/: the index, and one page per role listing every row held in it."""
    strengths = load_strengths(sections)
    where = section_pages()
    roles = {}
    for row in PROOF_POINTS:
        roles.setdefault(role_name(row), []).append(row)
    pages = []
    index = [
        ROUTING_LINE, '    <!-- MAIN CONTENT -->', '    <main>',
        '        <h1>Tom Stenson: proof points by role</h1>',
        '        <p>Every company, newest first, and under it every role held there that has a proof point, with the '
        f'number of rows. Open a role for everything done in it. All rows: <a href="{PAGE_PATH}">the facts page</a>; '
        f'by skill: <a href="{KEYWORDS_PATH}">skills</a>.</p>',
        '        <ul>',
    ]
    by_company = {}
    for role, rows in roles.items():
        by_company.setdefault(role_company(rows[0]), []).append((role, rows))
    company_pages = {pg['title']: pg['slug'] for pg in PAGES}
    for company, items in by_company.items():
        cslug = company_pages.get(company)
        head = f'<a href="{page_url(cslug)}">{escape(company)}</a>' if cslug else escape(company)
        index.append(f'            <li>{head}<ul>')
        for role, rows in items:
            index.append(f'                <li><a href="{ROLES_PATH}{role_slug(rows[0])}/">{escape(role_only(rows[0]))}</a> ({len(rows)})</li>')
        index.append('            </ul></li>')
    for role, rows in roles.items():
        slug = role_slug(rows[0])
        aliases = ROLE_ALIASES.get(rows[0]['role'][0])
        body = [
            ROUTING_LINE, '    <!-- MAIN CONTENT -->', '    <main>',
            f'        <h1>{escape(role)}: {len(rows)} proof point{"s" if len(rows) != 1 else ""}</h1>',
            f'        <p>Everything in the content done in this role. The product name links the page with the '
            f'full text. <a href="{ROLES_PATH}">All roles</a>, <a href="{PAGE_PATH}">the facts page</a>.</p>',
        ]
        if aliases:
            body.append(f'        <p>Also called: {escape(", ".join(aliases))}. Same role; titles differ between CVs and LinkedIn.</p>')
        body += render_table(sections, strengths, where, rows)
        body += ['    </main>', '']
        path = f'{ROLES_PATH}{slug}/'
        html = '\n'.join([
            agent_head(f'Tom Stenson, {escape(role)}: proof points',
                       _escape(f'{len(rows)} proof points of Tom Stenson, product, Copenhagen, as {role}.'), path),
            '\n'.join(body), agent_footer(),
        ]) + '\n'
        pages.append((f'roles/{slug}', role, path, html))
    index += ['        </ul>', '    </main>', '']
    index_html = '\n'.join([
        agent_head('Tom Stenson: proof points by role',
                   _escape('Index of the roles of Tom Stenson, product, Copenhagen: one page per role with its proof points.'), ROLES_PATH),
        '\n'.join(index), agent_footer(),
    ]) + '\n'
    pages.insert(0, ('roles', 'Proof points by role', ROLES_PATH, index_html))
    return pages


def generate_keyword_pages(sections):
    """for-agents/keywords/: the index, and one page per keyword listing its rows."""
    strengths = load_strengths(sections)
    where = section_pages()
    by_kw = keyword_rows(sections)
    pages = []
    index = [
        ROUTING_LINE, '    <!-- MAIN CONTENT -->', '    <main>',
        '        <h1>Tom Stenson: proof points by skill</h1>',
        '        <p>Every skill that at least one proof point carries, with the number of rows. A row carries a '
        'skill only when its own text or its source section does; match these against the terms in a job description, then open '
        f'the skill for the rows. All rows: <a href="{PAGE_PATH}">the facts page</a>.</p>',
        '        <ul>',
    ]
    for term, slug, _ in KEYWORDS:
        if slug not in by_kw:
            continue
        rows = by_kw[slug][1]
        index.append(f'            <li><a href="{KEYWORDS_PATH}{slug}/">{escape(term)}</a> ({len(rows)})</li>')
        body = [
            ROUTING_LINE, '    <!-- MAIN CONTENT -->', '    <main>',
            f'        <h1>{escape(term)}: {len(rows)} proof point{"s" if len(rows) != 1 else ""}</h1>',
            f'        <p>Rows on <a href="{PAGE_PATH}">the facts page</a> whose own text or source section carries "{escape(term)}". '
            f'The product name links the page with the full text. <a href="{KEYWORDS_PATH}">All skills</a>.</p>',
        ]
        body += render_table(sections, strengths, where, rows)
        body += ['    </main>', '']
        path = f'{KEYWORDS_PATH}{slug}/'
        html = '\n'.join([
            agent_head(f'Tom Stenson, {escape(term)}: proof points', _escape(f'{len(rows)} proof points of Tom Stenson, product, Copenhagen, that carry the skill {term}.'), path, noindex=True),
            '\n'.join(body), agent_footer(),
        ]) + '\n'
        pages.append((f'skills/{slug}', term, path, html))
    index += ['        </ul>', '    </main>', '']
    index_html = '\n'.join([
        agent_head('Tom Stenson: proof points by skill', _escape('Index of skills over the proof points of Tom Stenson, product, Copenhagen: one page per skill.'), KEYWORDS_PATH),
        '\n'.join(index), agent_footer(),
    ]) + '\n'
    pages.insert(0, ('skills', 'Proof points by skill', KEYWORDS_PATH, index_html))
    return pages


def build_jsonld(sections):
    """schema.org/Person as a JSON-LD script tag; quoted phrases are checked verbatim (R1012-14)."""
    for sid, title in JOB_TITLES:
        check(sections, sid, title)
    check(sections, *OCCUPATION_LINE)
    kb_sid, kb_items = KNOWS_ABOUT
    for item in kb_items:
        check(sections, kb_sid, item)
    for word in KNOWS_ABOUT_WORDS:
        check_anywhere(word)
    person = {
        '@context': 'https://schema.org',
        '@type': 'Person',
        'name': 'Tom Stenson',
        'givenName': 'Tom',
        'familyName': 'Stenson',
        'alternateName': ['Thomas Traberg Stenson'],   # Tom, 2026-10-12 (widens N1010-2)
        'jobTitle': [t for _, t in JOB_TITLES],
        'hasOccupation': {
            '@type': 'Occupation',
            'name': 'Product Manager',
            'description': OCCUPATION_LINE[1],
        },
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
        'knowsAbout': kb_items + KNOWS_ABOUT_WORDS,
    }
    body = json.dumps(person, ensure_ascii=False, indent=2).replace('\n', '\n    ')
    return f'<script type="application/ld+json">\n    {body}\n    </script>'


def generate_html(sections, recs):
    meta_desc = _escape(META_DESC.format(points=len(PROOF_POINTS), refs=len(recs)))

    body = [
        ROUTING_LINE,
        '    <!-- MAIN CONTENT -->',
        '    <main>',
        '        <h1>Tom Stenson: facts for agents</h1>',
    ]
    body += build_who(sections)            # identity table first (Tom, 2026-10-12)
    body += build_career(sections)         # then the job history, verbatim
    body += build_proof_points(sections)
    body += [
        '        <h2 id="how-to-read">How to read this page</h2>',
        '        <ol>',
        '            <li>Every cell is a line from Tom\'s own account (tier: self-reported), verbatim or compressed; '
        'the section ids are in each row\'s data-source attribute.</li>',
        '            <li>A row can sit in two shape groups; "not yet stated" means the content has no line for that cell. '
        'The role link lists every row in that role; the product link opens the full text, external sources where Tom has '
        'accepted them, and the questions to ask next; a skill link lists every row tagged with it, tagged from the '
        'row\'s own text and its source section.</li>',
        f'            <li>References: <a href="{RECS_PATH}">{len(recs)} LinkedIn recommendations</a> (tier: attested), '
        'grouped by role. They vouch for a role, not for a row.</li>',
        f'            <li>Working style: <a href="{WORKING_STYLE_PATH}">two Insights Discovery profiles, 2019 and 2022</a> '
        '(tier: self-reported assessment): ideal environment, motivation, what he needs from a manager. For environment and management questions, never as a verdict.</li>',
        f'            <li>Same rows as JSON: <a href="{PAGE_PATH}proof-points.json">proof-points.json</a>. '
        f'Query: <a href="{ASK_URL}">/ask</a>. Generated {GENERATED}.</li>',
        '        </ol>',
        '    </main>',
        '',
    ]

    return '\n'.join([
        agent_head(TITLE, meta_desc, PAGE_PATH, jsonld=build_jsonld(sections)),
        '\n'.join(body),
        agent_footer(),
    ]) + '\n'


# Chat-voice line the agent side leaves out (N1012-22; mirrors AGENT_OMIT_LINES in lib/guard.js).
AGENT_OMIT_LINE = re.compile(r"I can['’]t go into detail on the specific strategy\b", re.I)


def section_body(parsed, section_id):
    """A section's answer text (Direct answers excluded; they render as their own block)."""
    if section_id not in parsed:
        sys.exit(f'✗ Section {section_id} not found in {CONTENT_FILE}')
    text = re.split(r'^---\s*$', parsed[section_id]['content'], maxsplit=1, flags=re.M)[0]
    return '\n'.join(ln for ln in text.split('\n') if not AGENT_OMIT_LINE.match(ln.strip()))


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


def ask_link(question):
    return f'{ASK_URL}?q={quote(question)}'


def build_section(sections, parsed, sid, where, heading=None):
    """One section on a page: heading (its first routing question), source line, verbatim
    body, accepted direct answers and external links, and the questions to ask next."""
    p = parsed[sid]
    heading = heading or (p['questions'][0] if p['questions'] else sid)
    lines = [
        f'        <h2 id="{section_anchor(sid)}">{escape(heading)}</h2>',
        f'        <p><small data-source="{_escape(sid)}">source: Tom\'s own account</small></p>',
    ]
    for kind, value in section_blocks(section_body(parsed, sid)):
        for t in (value if kind == 'ul' else [value]):
            check(sections, sid, t)
        if kind == 'p':
            lines.append(f'        <p>{escape(value)}</p>')
        else:
            lines.append('        <ul>')
            lines.extend(f'            <li>{escape(t)}</li>' for t in value)
            lines.append('        </ul>')
    if p.get('direct_answers'):
        lines.append('        <h3>Direct answers</h3>')
        lines.append('        <ul>')
        lines.extend(f'            <li>{escape(d)}</li>' for d in p['direct_answers'])
        lines.append(f'        </ul>\n        <p><small data-source="{_escape(sid)}">source: Tom\'s own account, direct answers</small></p>')
    if p.get('external'):
        lines.append('        <h3>External sources</h3>')
        lines.append('        <ul>')
        lines.extend(f'            <li><a href="{_escape(e["url"])}">{escape(e["label"])}</a></li>'
                     for e in p['external'])
        lines.append('        </ul>')
    # Ask next: drill-downs and follow-ups, as links into the spider or to /ask.
    nexts = []
    seen = set()
    for f in p.get('follow_ups', []):
        if f['target'] in seen:
            continue
        seen.add(f['target'])
        nexts.append((f['text'], f['target']))
    for target in p.get('drill_downs', []):
        if target in seen or target not in parsed:
            continue
        seen.add(target)
        q = parsed[target]['questions'][0] if parsed[target]['questions'] else target
        nexts.append((q, target))
    if nexts:
        titles = {pg['slug']: pg['title'] for pg in PAGES}
        lines.append('        <h3>Related</h3>')
        lines.append('        <ul>')
        for text, target in nexts:
            if target in where:
                slug, anchor = where[target]
                href = page_url(slug, anchor)
                label = f'{titles[slug]}: {text}'
            else:
                href = ask_link(text)
                label = f'Ask: {text}'
            lines.append(f'            <li><a href="{_escape(href)}">{escape(label)}</a> <small>{escape(target)}</small></li>')
        lines.append('        </ul>')
    return lines


def generate_page(sections, parsed, page, recs):
    if page['title_in']:
        check(sections, page['title_in'], page['title'])
    check(sections, *page['opening'])
    where = section_pages()
    path = page_url(page['slug'])
    body = [
        ROUTING_LINE,
        '    <!-- MAIN CONTENT -->',
        '    <main>',
        f'        <h1>{escape(page["title"])}</h1>',
    ]
    if page['period']:
        n = sum(1 for r in recs if r['period'] == page['period'])
        if n:
            body.append(f'        <p>References from this period: <a href="{RECS_PATH}#{page["period"]}">{n} LinkedIn '
                        f'recommendation{"s" if n != 1 else ""}</a>, full text. They vouch for the role, not for any '
                        'one claim.</p>')
    top = page['sections'][0]
    if '.' not in top:   # company overview page: every row of that company
        rows = [r for r in PROOF_POINTS if r['strength'].split('.')[0] == top]
    else:
        rows = [r for r in PROOF_POINTS if r['strength'] in page['sections'] or r['product'][1] in page['sections']]
    if rows and not page['slug'] in {t for _, _, t in SHAPES if t}:
        body.append(f'        <h2 id="proof-points">Proof points: {len(rows)}</h2>')
        body += render_table(sections, load_strengths(sections), where, rows)
    for sid in page['sections']:
        body += build_section(sections, parsed, sid, where, heading=page.get('headings', {}).get(sid))
    body += [f'        <p><a href="{PAGE_PATH}">All proof points</a></p>', '    </main>', '']
    html = '\n'.join([
        agent_head(escape(page['title']), _escape(page['opening'][1]), path),
        '\n'.join(body),
        agent_footer(),
    ]) + '\n'
    return os.path.join(path.strip('/'), 'index.html'), html


def generate_recommendations(recs):
    """for-agents/recommendations/: every visible recommendation, full text, grouped by period."""
    n = len(recs)
    title = 'Tom Stenson: LinkedIn recommendations, full text'
    meta_desc = (f'{n} LinkedIn recommendations of Tom Stenson, product, Copenhagen: full text, grouped by '
                 'the role they refer to, each with the recommender\'s title when written and now.')
    body = [
        ROUTING_LINE,
        '    <!-- MAIN CONTENT -->',
        '    <main>',
        f'        <h1>{escape(title)}</h1>',
        f'        <p>Every recommendation visible on Tom Stenson\'s LinkedIn profile: {n}, each text verbatim, '
        'grouped by the role and period it refers to, newest first within a group. They are references for a '
        'role, not evidence for any one claim. '
        f'Source: LinkedIn data export, {RECS_EXPORT_DATE}. '
        f'Record of truth: <a href="{LINKEDIN_RECORD}">LinkedIn recommendations</a>. '
        f'Facts page: <a href="{PAGE_PATH}">{PAGE_PATH}</a>. '
        f'Tom\'s own self-report on environment and management, two Insights Discovery profiles: <a href="{WORKING_STYLE_PATH}">{WORKING_STYLE_PATH}</a>.</p>',
    ]
    for key, label in PERIODS.items():
        group = [r for r in recs if r['period'] == key]
        if not group:
            continue
        body.append(f'        <h2 id="{key}">{escape(label)}</h2>')
        for r in group:
            year = r['date'][:4]
            now = f'{escape(r["title"])}, {escape(r["company"])}'
            if r['then']:
                title_line = f'{escape(r["then"])} when written ({year}); now {now}'
            else:
                title_line = f'{now} (current title; title when written not recorded)'
            body += [
                f'        <article id="{r["anchor"]}">',
                f'            <h3>{escape(r["name"])}</h3>',
                '            <dl>',
                '                <dt>Title and company</dt>',
                f'                <dd>{title_line}</dd>',
                '                <dt>Date</dt>',
                f'                <dd><time datetime="{r["date"]}">{r["date"]}</time></dd>',
                '                <dt>Source</dt>',
                f'                <dd><a href="{LINKEDIN_RECORD}">LinkedIn record</a></dd>',
                '            </dl>',
                f'            <blockquote><p>{escape(r["text"])}</p></blockquote>',
                '        </article>',
            ]
    body += ['    </main>', '']
    return '\n'.join([
        agent_head(escape(title), _escape(meta_desc), RECS_PATH),
        '\n'.join(body),
        agent_footer(),
    ]) + '\n'


# Working style (R1013-7, evals/fit-questions.md 1b, O5 default): the two Insights
# Discovery profiles as a source. Four lists per profile, the wheel position and a
# one-line delta; strengths, weaknesses, blind spots, management style and the colour
# percentages stay in the private extracts. Tier: self-reported assessment, dated.
WORKING_STYLE_PATH = f'{PAGE_PATH}working-style/'
WORKING_STYLE_FILE = 'for-agents/working-style/index.html'
INSIGHTS_PROFILES = [
    {'year': '2019', 'date': '2019-01-15', 'when': '15 January 2019', 'where': 'LEO Innovation Lab',
     'file': 'docs/agent-readable/sources/insights-2019/extract.md'},
    {'year': '2022', 'date': '2022-01-20', 'when': '20 January 2022', 'where': 'Novo Nordisk',
     'file': 'docs/agent-readable/sources/insights-2022/extract.md'},
]
# Extract heading -> page heading and anchor. Only these four lists are published.
INSIGHTS_LISTS = [
    ('Ideal environment', 'Ideal environment', 'environment'),
    ('Motivated by', 'Motivated by', 'motivated-by'),
    ('Managing Tom, what he needs', 'Managing Tom: what he needs', 'managing'),
    ('Value to the team', 'Value to the team', 'value'),
]
INSIGHTS_TIER = ('Insights Discovery, a self-report questionnaire scored by Insights Learning and Development: '
                 'what Tom ticked, not what colleagues say (tier: self-reported assessment).')
# One line, drawn from the 2022 extract's delta section; the weaknesses rule (R1013-8) keeps
# the profile-only lines out of it.
INSIGHTS_DELTA = ('Same in both: loses interest once the work is routine, initiates more than he finishes, big '
                  'picture over procedure, a fast pace, freedom of action, dislikes ceremony and imposed process, '
                  'delegates administration and concentrates on outcomes. Moved: from Motivator in 2019 (yellow-led, '
                  'infectious enthusiasm) toward Director in 2022 (red-led: takes charge, decisive, wants control and '
                  'recognition, a cause to believe in); the 2022 lists add help with planning and preparation, and '
                  'someone around to bring up overlooked facts and take care of the details.')


def load_insights(profile):
    """The published lists and the wheel position from one extract. Fails if a list is
    missing, so a changed extract breaks the build rather than the page."""
    with open(profile['file'], encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'Conscious wheel position: (.+?)\. Less conscious', text)
    if not m:
        sys.exit(f'ERROR: no wheel position in {profile["file"]}')
    lists = {}
    for src_heading, _, _ in INSIGHTS_LISTS:
        m2 = re.search(r'^## ' + re.escape(src_heading) + r' \(p[\d, p-]+\)\n(.+?)(?=\n## |\Z)', text, re.M | re.S)
        if not m2:
            sys.exit(f'ERROR: no "{src_heading}" list in {profile["file"]}')
        para = ' '.join(m2.group(1).split())
        items = [t.strip() for t in re.split(r'(?<=\.)\s+(?=["A-Z])', para) if t.strip()]
        if len(items) < 5:
            sys.exit(f'ERROR: "{src_heading}" in {profile["file"]} split into {len(items)} items')
        lists[src_heading] = items
    return {'position': m.group(1), 'lists': lists}


def generate_working_style():
    """for-agents/working-style/: the two Insights profiles, four lists each, dated and tier-labelled."""
    title = 'Tom Stenson: working style, Insights Discovery profiles 2019 and 2022'
    meta_desc = ('Two Insights Discovery profiles of Tom Stenson, product, Copenhagen, 2019 and 2022: ideal '
                 'environment, motivation, what he needs from a manager, value to a team. Self-reported, dated.')
    body = [
        ROUTING_LINE,
        '    <!-- MAIN CONTENT -->',
        '    <main>',
        f'        <h1>{escape(title)}</h1>',
        '        <p>Two Insights Discovery profiles three years apart, each with its ideal environment, motivation, '
        'what he needs from a manager and value to a team, in the profile\'s wording. '
        f'{escape(INSIGHTS_TIER)} '
        f'Colleagues\' view: <a href="{RECS_PATH}">{RECS_PATH}</a>. '
        f'Facts page: <a href="{PAGE_PATH}">{PAGE_PATH}</a>.</p>',
        '        <h2 id="how-to-use">How to use this</h2>',
        '        <ol>',
        '            <li>Cite as "Insights profile, 2019" or "Insights profile, 2022", with this URL.</li>',
        '            <li>Use it for questions about environment, team and management (Job 5 in '
        '<a href="/for-agents/start/">/for-agents/start/</a>), beside a named recommendation. Never as a verdict: '
        'it says what Tom ticked, not whether he fits.</li>',
        '            <li>The profiles\' strengths, weaknesses, blind spots and management style sections are not on '
        'this page; the lines two sources agree on are in the fit answers from <a href="' + ASK_URL + '">/ask</a>. '
        'Colour percentages are left out.</li>',
        '        </ol>',
    ]
    for profile in INSIGHTS_PROFILES:
        data = load_insights(profile)
        y = profile['year']
        body += [
            f'        <h2 id="{y}">{y}: {escape(profile["when"])}, {escape(profile["where"])}</h2>',
            f'        <p>Wheel position: {escape(data["position"])}. '
            f'<small>source: Insights Discovery profile, <time datetime="{profile["date"]}">{escape(profile["when"])}</time>, '
            f'completed at {escape(profile["where"])}; extract without personal details.</small></p>',
        ]
        for src_heading, heading, anchor_id in INSIGHTS_LISTS:
            body.append(f'        <h3 id="{anchor_id}-{y}">{escape(heading)}, {y}</h3>')
            body.append('        <ul>')
            body.extend(f'            <li>{escape(t)}</li>' for t in data['lists'][src_heading])
            body.append('        </ul>')
    body += [
        '        <h2 id="delta">2019 to 2022, the delta</h2>',
        f'        <p>{escape(INSIGHTS_DELTA)}</p>',
        '    </main>',
        '',
    ]
    main_text = '\n'.join(body)
    if re.search(r'[\w.+-]+@[\w-]+\.\w', main_text) or re.search(r'\d{8,}', main_text):
        sys.exit('ERROR: working-style page carries an email or a long number; the extracts must stay de-identified')
    return '\n'.join([agent_head(escape(title), _escape(meta_desc), WORKING_STYLE_PATH), main_text, agent_footer()]) + '\n'


def proof_points_json(sections):
    """The rows as JSON: the same cells as the table, each with its section id, plus keywords, shapes, page, facets."""
    strengths = load_strengths(sections)
    where = section_pages()
    rows = []
    for n, row in enumerate(PROOF_POINTS, 1):
        slug, anchor = where.get(row['product'][1]) or where.get(row['strength']) or (None, None)
        r = {}
        for key in ('role', 'product', 'desc', 'situation', 'task', 'action', 'result', 'year'):
            v = row.get(key)
            r[key] = None if v is None else {'text': v[0], 'section': v[1]}
            q = (row.get('_quote') or {}).get(key)
            if v is not None and q and q[0] != v[0]:
                r[key]['quote'] = q[0]      # Tom's verbatim line the cell is derived from
        r['company'] = role_company(row)
        r['strength'] = strengths.get(row['strength'], {}).get('strength')
        r['tier'] = 'self-reported'
        r['shapes'] = row_shapes(row)
        r['skills'] = [t for t, _ in row_keywords(sections, row)]
        r['page'] = f'https://takenbyninjas.com{page_url(slug, anchor)}' if slug else None
        r['role_page'] = f'https://takenbyninjas.com{ROLES_PATH}{role_slug(row)}/'
        r['role_aliases'] = ROLE_ALIASES.get(row['role'][0], [])
        r['facets'] = row_facets(n)
        rows.append(r)
    data = {'generated': GENERATED, 'source': 'Tom\'s own account (tier: self-reported); each row cites its TomBot section id',
            'facets': 'Each row\'s `facets` are lines from CVs Tom sent, verbatim (tier: self-reported; `source` names the CV). '
                      'A brief returns the facet that matched a requirement as its evidence; the row\'s result cell stays the outcome.',
            'roles_note': 'Domain, company type, size and level are answered from `roles`, not from one story: each company with its sectors, '
                          'environments, size and products, each role with its title, aliases and scope in effect. Count every role that matches.',
            'human_version': 'https://takenbyninjas.com/about/', 'facts_page': PAGE_URL,
            'references': f'https://takenbyninjas.com{RECS_PATH}', 'shapes': [{'id': i, 'label': l} for i, l, _ in SHAPES],
            'screening_facts': facts_register(sections)['facts'],
            'skill_pages': {term: f'https://takenbyninjas.com{KEYWORDS_PATH}{slug}/' for term, slug, _ in KEYWORDS},
            'roles': roles_register(sections)['companies'], 'count': len(rows), 'proof_points': rows}
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


# CV appendix (PRD J4, W6; Tom 2026-10-12): a one-page machine-readable summary
# to sit at the end of the human CV, flagged for agents and ATS, with links
# to fetch more. Same rows, same sources; the strongest picks, once each.
CV_APPENDIX_ROWS = 8
CV_APPENDIX_MD = 'for-agents/cv-appendix.md'
CV_APPENDIX_PATH = f'{PAGE_PATH}cv-appendix/'


def cv_appendix_rows(sections):
    seen, rows = set(), []
    for shape_id, _, _ in SHAPES:
        for row in shape_rows(shape_id)[:FACTS_ROWS_PER_SHAPE]:
            key = (row['product'][0], row['result'][0])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
            if len(rows) == CV_APPENDIX_ROWS:
                return rows
    return rows


def cv_line(row):
    """One STAR line: Role, Product (what it is): situation; task; action; result (year)."""
    def t(k):
        return row[k][0] if row.get(k) else None
    bits = [b for b in (t('situation'), t('task'), t('action')) if b]
    story = '; '.join(bits)
    out = f"{t('role')}, {t('product')}"
    if t('desc') and t('desc') != t('product'):
        out += f" ({t('desc')})"
    out += ': ' + (story + '. ' if story else '') + f"Result: {t('result')} ({t('year')})."
    return out


def build_cv_appendix(sections, recs):
    rows = cv_appendix_rows(sections)
    for row in rows:
        for k in ('role', 'product', 'desc', 'situation', 'task', 'action', 'result', 'year'):
            if row.get(k):
                check(sections, row[k][1], row[k][0])
    who = []
    for term, items in WHO:
        if term in ('Availability, compensation, contact', 'Endpoints') or items == [(NOT_YET_STATED, None)]:
            continue
        for text, sid in items:
            check(sections, sid, text)
        who.append((term, '; '.join(t for t, _ in items)))
    career = []
    for ln in sections[CAREER_SECTION].split('\n'):
        if ln.startswith('|') and not ln.startswith('| Years') and not ln.startswith('|---'):
            cells = [c.strip() for c in ln.strip('|').split('|')]
            if len(cells) == 4 and cells[3] in CITY_COUNTRY:
                city, country = CITY_COUNTRY[cells[3]]
                loc = ' / '.join(f'{ci.strip()}, {co.strip()}' for ci, co in zip(city.split('/'), country.split('/')))
                career.append((cells[0], cells[1], cells[2], loc))
    skills = []
    for row in PROOF_POINTS:
        for term, _ in row_keywords(sections, row):
            if term not in skills:
                skills.append(term)
    base = 'https://takenbyninjas.com'
    md = [
        '## For AI agents and applicant tracking systems',
        '',
        'This page is a machine-readable summary of the CV above, generated from the same record, with a source for every line. '
        f'If you can fetch URLs, start at {base}/for-agents/start/: it lists the jobs it can do (how Tom fits a role, '
        'explore his background, what he has done, the basics, fit for a team or organisation) and the endpoints for each. '
        f'Every proof point with its sources: {base}/for-agents/proof-points.json. Facts page: {base}/for-agents/. '
        f'Ask one question: GET {base}/ask?q=<question>. Post a job description: POST {base}/ask/brief. '
        f'Generated {GENERATED}.',
        '',
        '### Identity',
        '',
    ]
    md += [f'- {term}: {val}' for term, val in who]
    md += ['', '### Career', '', '| Years | Role | Company | Location |', '|---|---|---|---|']
    md += [f'| {y} | {r} | {c} | {l} |' for y, r, c, l in career]
    md += ['', f'### Proof points, strongest {len(rows)} of {len(PROOF_POINTS)} (situation; task; action; result)', '']
    md += [f'{i}. {cv_line(row)} source: Tom\'s own account; more: {base}{page_url(*(section_pages().get(row["product"][1]) or section_pages().get(row["strength"]) or (None, None))) if (section_pages().get(row["product"][1]) or section_pages().get(row["strength"])) else PAGE_PATH}'
           for i, row in enumerate(rows, 1)]
    md += ['', '### Skills (each tagged from the proof points that carry it)', '', ', '.join(skills) + '.',
           '', '### References', '',
           f'{len(recs)} LinkedIn recommendations, full text, grouped by role: {base}{RECS_PATH}. They vouch for a role, not for a claim.',
           '', '### How this was put together', '',
           'Every line above is Tom Stenson\'s own account (tier: self-reported) with a section id; the pages link external sources where accepted. '
           'Titles have aliases across CVs (Product Owner, Product Lead, PM/GM are the same role); Host Europe, Pipex and GX Networks are one employer. '
           'Where the record is silent it says so. Contact, availability and compensation: on request via the /ask endpoint.', '']
    md_text = '\n'.join(md)
    # HTML page: the same text, plain
    body = [ROUTING_LINE, '    <!-- MAIN CONTENT -->', '    <main>', '        <h1>Tom Stenson: CV appendix for agents</h1>',
            f'        <p>{escape(md[2])}</p>', '        <h2>Identity</h2>', '        <dl>']
    for term, val in who:
        body += [f'            <dt>{escape(term)}</dt>', f'            <dd>{escape(val)}</dd>']
    body += ['        </dl>', '        <h2>Career</h2>', '        <div class="table-wrap"><table>',
             '            <thead><tr><th>Years</th><th>Role</th><th>Company</th><th>Location</th></tr></thead><tbody>']
    body += ['                <tr>' + ''.join(f'<td>{escape(c)}</td>' for c in r) + '</tr>' for r in career]
    body += ['            </tbody></table></div>', f'        <h2>Proof points, strongest {len(rows)} of {len(PROOF_POINTS)}</h2>', '        <ol>']
    for row in rows:
        slug_anchor = section_pages().get(row['product'][1]) or section_pages().get(row['strength'])
        href = page_url(*slug_anchor) if slug_anchor else PAGE_PATH
        body.append(f'            <li>{escape(cv_line(row))} <small data-source="{_escape(row["result"][1])}">source: Tom\'s own account</small> <a href="{href}">more</a></li>')
    body += ['        </ol>', '        <h2>Skills</h2>', f'        <p>{escape(", ".join(skills))}.</p>',
             '        <h2>References</h2>', f'        <p>{len(recs)} LinkedIn recommendations, full text, grouped by role: <a href="{RECS_PATH}">{RECS_PATH}</a>. They vouch for a role, not for a claim.</p>',
             '        <h2>How this was put together</h2>', f'        <p>{escape(md[-2])}</p>',
             f'        <p>Markdown of this page, to append to a CV: <a href="/for-agents/cv-appendix.md">/for-agents/cv-appendix.md</a>.</p>',
             '    </main>', '']
    html = '\n'.join([agent_head('Tom Stenson: CV appendix for agents',
                                 _escape('One-page machine-readable summary of Tom Stenson\'s CV for AI agents and applicant tracking systems, with links to fetch the evidence.'), CV_APPENDIX_PATH),
                      '\n'.join(body), agent_footer()]) + '\n'
    return md_text, html


START_MD = 'for-agents/start.md'
START_PAGE = 'for-agents/start/index.html'


def start_page_html():
    """The entry file as an HTML page (the paste URL): ChatGPT's reader rejects .md
    URLs; the same text in a pre block fetched first time (paste-test run 2)."""
    with open(START_MD, encoding='utf-8') as f:
        md = f.read()
    return '\n'.join([
        '<!DOCTYPE html>',
        '<!-- GENERATED FILE - DO NOT EDIT MANUALLY: the entry file for-agents/start.md as a page -->',
        '<html lang="en">', '<head>', '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        '    <title>Tom Stenson: start here, agent</title>',
        '    <meta name="description" content="Entry file for AI assistants helping someone who wants to know about Tom Stenson: five jobs, the endpoints, and how to use what comes back.">',
        f'    <link rel="canonical" href="{SITE_URL}/for-agents/start/">',
        '    <style>body{margin:0;background:#fff;color:#222;font:16px/1.5 system-ui,sans-serif;padding:1rem}pre{white-space:pre-wrap;word-wrap:break-word;font:14px/1.5 ui-monospace,Menlo,Consolas,monospace}</style>',
        '</head>', '<body>',
        '<p>This page is the agent entry file as plain text. Markdown source: <a href="/for-agents/start.md">/for-agents/start.md</a>. Human? Go to the <a href="/">human-readable version</a>.</p>',
        '<pre>' + _escape(md) + '</pre>',
        f'<p><small>Created by AI for AI. Generated {GENERATED}.</small></p>',
        '</body>', '</html>', '',
    ])


def manifest(extra=()):
    """Page manifest for agent-fetch and the agent sitemap: slug -> {path, file, title}."""
    pages = {p['slug']: {'path': page_url(p['slug']), 'file': f'for-agents/{p["slug"]}/index.html',
                         'title': p['title']} for p in PAGES}
    for slug, title, path, _ in extra:
        pages[slug] = {'path': path, 'file': f'for-agents/{slug}/index.html', 'title': title}
    # Per-send fit pages (scripts/cv_appendix.py --tag) survive a regenerate.
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, encoding='utf-8') as f:
            for slug, entry in json.load(f).get('pages', {}).items():
                if slug.startswith('fit/') and os.path.exists(entry.get('file', '')):
                    pages[slug] = entry
    return json.dumps({'generated_by': 'generate_agent_page.py', 'pages': pages}, ensure_ascii=False, indent=2) + '\n'


SECTION_YEARS_FILE = 'netlify/functions/lib/section_years.json'


# Spans the content does not state, ruled by Tom (N1012-23; LinkedIn export, confirmed 2026-10-13).
COMPANY_SPANS = {'UK2': 'Sep 2008 - Sep 2010'}
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
MONTH_SPAN = r'((?:%s) \d{4}) - ((?:%s) \d{4})' % ('|'.join(MONTHS), '|'.join(MONTHS))
# A role line names its story: "- Sales Executive (Mar 2003 - Feb 2004): ... [HOST.R3.STORY.ALTSITE]".
ROLE_LINE = re.compile(r'\(' + MONTH_SPAN + r'\)[^\n]*?\[([A-Z][A-Z0-9_]*(?:\.[A-Z0-9_]+)+)\]')


def month_key(text):
    mon, year = text.split()
    return int(year) * 12 + MONTHS.index(mon)


def section_years_json(sections):
    """Section id -> year text (N1012-23: the rule, not the values).
    1. A story takes the dates of the role its content line names, when that line
       sits in the story's own company section.
    2. Else a section gets the year of the rows that cite it; a drill-down
       (NOVO.R2.GENAI) inherits its role section's (NOVO.R2).
    3. A company section (HOST, LEO) spans its roles: Tom's ruled span if there is
       one, else first start to last end of its month-dated sections.
    META sections are not periods and carry no year.
    Read by calibrate.js so a section match is not stuck at partial for lack of a year."""
    named, top = {}, None
    with open(CONTENT_FILE, encoding='utf-8') as f:   # the raw file: the parser strips [SECTION.ID] markers
        for line in f:
            if line.startswith('## '):
                top = line[3:].strip().split('.')[0]
            for start, end, target in ROLE_LINE.findall(line):
                if top and target.startswith(top + '.') and target in sections:
                    named.setdefault(target, f'{start} - {end}')
    years = dict(named)
    for row in PROOF_POINTS:
        if not row.get('year'):
            continue
        y = row['year'][0]
        for key in ('role', 'product', 'situation', 'task', 'action', 'result'):
            if row.get(key):
                years.setdefault(row[key][1], y)
        years.setdefault(row['strength'], y)
    for sid in list(sections):
        if sid in years:
            continue
        parts = sid.split('.')
        for n in range(len(parts) - 1, 0, -1):
            parent = '.'.join(parts[:n])
            if parent in years:
                years[sid] = years[parent]
                break
    for top in {sid.split('.')[0] for sid in years if '.' in sid}:
        if top not in sections:
            continue
        spans = [re.fullmatch(MONTH_SPAN, y) for sid, y in years.items() if sid.startswith(top + '.')]
        if top in COMPANY_SPANS:
            years[top] = COMPANY_SPANS[top]
        elif spans and all(spans):
            start = min((m.group(1) for m in spans), key=month_key)
            end = max((m.group(2) for m in spans), key=month_key)
            years[top] = f'{start} - {end}'
    years = {sid: y for sid, y in years.items() if not sid.startswith('META.') and sid in sections}
    return json.dumps({'generated_by': 'generate_agent_page.py', 'years': dict(sorted(years.items()))}, ensure_ascii=False, indent=2) + '\n'


# Role context (Tom, 2026-10-13: "startup and health tech not giving hits are just symptoms").
# A domain, an environment or a level is a property of a role and its company, and it adds up
# over a career: one story cannot answer "health-tech experience". Each company carries its
# sectors, environments and size, each role its level and scope in effect, all in Tom's words
# (text verbatim in the cited section). Written to lib/roles.json for /ask/brief (lib/coverage.js)
# and to proof-points.json as `roles`. A company can sit in several at once (LEO: startup
# incubator, pharma, health-tech and enterprise).
ROLES_FILE = 'netlify/functions/lib/roles.json'
ROLE_DIMENSIONS = {
    'sector': [
        ('health', 'Health-tech', [r'\bhealth[- ]?tech\b', r'\bdigital health\b', r'\bhealth ?care\b', r'\bmed[- ]?tech\b',
                                   r'\bhealth (software|company|companies|sector|industry|domain|space|products?)\b', r'\bpatient[- ]facing\b']),
        ('pharma', 'Pharma', [r'\bpharma(ceuticals?)?\b', r'\blife sciences?\b']),
        ('saas', 'SaaS', [r'\bsaas\b']),
        ('developer-tools', 'Developer tools', [r'\bdeveloper tool(s|ing)\b', r'\bdev ?tools\b']),
        ('hosting', 'Web hosting and domains', [r'\b(web )?hosting\b', r'\bdomain (names?|industry|registrar)\b']),
        ('ecommerce', 'Ecommerce', [r'\be-?commerce\b']),
    ],
    'environment': [
        ('founder-led', 'Founder-led', [r'\bfounder[- ]led\b', r'\b(with|to|alongside) (the |a |our )?(co-?)?founders?\b']),
        ('startup', 'Startup', [r'\bstart-?ups?\b', r'\bearly[- ]stage\b', r'\bseed\b', r'\bseries a\b', r'\bventure[- ]backed\b', r'\bvc[- ]backed\b']),
        ('scale-up', 'Scale-up', [r'\bscale-?ups?\b', r'\bhigh[- ]growth\b', r'\bhyper-?growth\b', r'\bseries [b-e]\b']),
        ('incubator', 'Innovation lab or incubator', [r'\bincubat', r'\binnovation (lab|unit|hub|team)\b', r'\bventure (studio|building)\b']),
        ('corporate', 'Corporate', [r'\bcorporate\b', r'\blarge (organi[sz]ations?|compan(y|ies)|enterprises?)\b', r'\bmatrix(ed)?\b',
                                    r'\bmultinational\b', r'\bglobal (organi[sz]ation|company|enterprise)\b']),
    ],
    'level': [
        ('head-of-product', 'Head of product', [r'\bhead of product\b', r'\bvp,? (of )?product\b', r'\bvice president,? (of )?product\b',
                                                r'\bchief product officer\b', r'\bcpo\b', r'\bproduct director\b', r'\bdirector of product\b',
                                                r'\bproduct lead(er|ership)?\b', r'\b(sole|first|only) product (lead|leader|hire|person|manager)\b',
                                                r'\b(lead|leading|led|own|owning|owned|run|running|ran) (the |a )?product (function|organi[sz]ation|team|department)\b']),
    ],
}
# A headcount in a requirement ("40-person company") gets every company's size, nearest first.
ROLE_SIZE_ASK = r'\b(\d{1,3}(?:,\d{3})+|\d+)\+?[- ]?(?:person|people|employees?|staff|fte)\b'
COMPANY_CONTEXT = [
    {'company': 'Novo Nordisk', 'section': 'NOVO', 'sectors': ['health', 'pharma'], 'environments': ['corporate'],
     'size': ('Novo Nordisk is about 70,000 people globally. I worked in the digital health unit, about 100 people; the Wegovycare product team was around 10.', 'NOVO', [70000, 100, 10]),
     'skills': ['healthcare'],
     'products': ['Wegovycare', 'Wegovy Pill launch', 'CagriSema', 'GenAI proof of concept for automating compliance reviews', 'Digital Incubation', 'Product Operations'],
     'roles': [{'role': 'Associate Product Director at Novo Nordisk', 'levels': ['head-of-product'],
                'scope': ('Head of Patient Products: led 6 experienced PMs building consumer engagement products, for a period, before moving into the pill team where the need was greatest.', 'NOVO.R2')},
               {'role': 'Senior Product Manager at Novo Nordisk', 'levels': [],
                'scope': ('Led cross-functional team of 10.', 'NOVO.R1')}]},
    {'company': 'LEO Innovation Lab', 'section': 'LEO', 'sectors': ['health', 'pharma'], 'environments': ['startup', 'incubator', 'corporate'],
     'context': ("the Lab was a startup incubator at arm's length from LEO Pharma, a 12,000-person pharma company.", 'LEO'),
     'size': ('I joined when the Lab was 30 people and it was 130 when I left. Multiple startup teams of around 3 to 15 people each.', 'LEO', [30, 130, 15]),
     'skills': ['healthcare'],
     'products': ['TREAT', 'Skincoach', 'Diagnosis App', 'BetterVisitBot'],
     'roles': [{'role': 'PM/GM at LEO Innovation Lab', 'levels': ['head-of-product'],
                'scope': ('each team had one product owner, who was in effect a mini-CEO and head of product. I was the sole product lead on mine.', 'LEO')}]},
    {'company': 'TwentyThree', 'section': 'T23', 'sectors': [], 'environments': ['founder-led', 'startup'],
     'context': ('a founder-led startup.', 'T23'), 'size': ('About 30 people.', 'T23', [30]), 'skills': ['startup'], 'products': [],
     'roles': [{'role': 'Head of Marketing', 'levels': [], 'scope': ('Stabilised a 10-12 person marketing team', 'T23')}]},
    {'company': 'Opbeat', 'section': 'OPBEAT', 'sectors': ['saas', 'developer-tools'], 'environments': ['founder-led', 'startup'],
     'context': ('a founder-led startup.', 'OPBEAT'),
     'size': ('12 people in the company, 4 in marketing including design.', 'OPBEAT', [12]), 'products': [],
     'roles': [{'role': 'Head of Marketing', 'levels': [],
                'scope': ('I joined as Head of Marketing and built the brand, marketing strategy, team and channels', 'OPBEAT')}]},
    {'company': 'EuroDNS', 'section': 'EURODNS', 'sectors': ['hosting', 'ecommerce'], 'environments': ['founder-led'],
     'context': ('founder-led.', 'EURODNS'), 'size': ('Probably about 50 people.', 'EURODNS', [50]), 'products': [],
     'roles': [{'role': 'Marketing Director', 'levels': [],
                'scope': ('Marketing Director by title; the product work was mine: discount ladders, management panels, bundling features, product strategy.', 'EURODNS')}]},
    {'company': 'UK2 Group', 'section': 'UK2', 'sectors': ['hosting'], 'environments': [],
     'size': ('UK2 grew from about 100 to about 200 people while I was there.', 'UK2', [100, 200]), 'products': ['new domain platform'],
     'roles': [{'role': 'Head of Group Strategy', 'levels': ['head-of-product'],
                'scope': ('in effect head of product for the US parts of the business I worked on.', 'UK2')}]},
    {'company': 'Host Europe Group', 'section': 'HOST', 'sectors': ['hosting', 'ecommerce'], 'environments': ['founder-led', 'startup', 'scale-up'],
     'context': ('a founder-led startup at the beginning.', 'HOST'),
     'size': ('About 150 people when I started, about 500 later, and 2,000 as part of Pipex broadband.', 'HOST', [150, 500, 2000]),
     'products': ['domain search'],
     'roles': [{'role': 'Head of New Media', 'levels': [],
                'scope': ('Created department from scratch, member of Senior Management Team.', 'HOST')}]},
]
COMPANY_CONTEXT_BY_NAME = {c['company']: c for c in COMPANY_CONTEXT}


def short_years(text):
    """'Nov 2016 - Jan 2020' -> '2016-2020'; '2016' stays."""
    ys = re.findall(r'\b(?:19|20)\d{2}\b', text or '')
    return text if not ys else (ys[0] if ys[0] == ys[-1] else f'{ys[0]}-{ys[-1]}')


def roles_register(sections):
    """Role context as data. Every quoted line must be verbatim in its section; every role and
    product named must be a proof-point row, so each entry links to a page that exists."""
    years = json.loads(section_years_json(sections))['years']
    dim_ids = {d: {i for i, _, _ in entries} for d, entries in ROLE_DIMENSIONS.items()}

    def quoted(pair, what):
        text, sid = pair
        if sid not in sections or text not in sections[sid]:
            sys.exit(f'✗ Role context {what}: not verbatim in {sid}: {text!r}')
        return {'text': text, 'section': sid}

    companies = []
    for c in COMPANY_CONTEXT:
        name = c['company']
        rows = [r for r in PROOF_POINTS if role_company(r) == name]
        if not rows or c['section'] not in years:
            sys.exit(f'✗ Role context: no rows or no years for {name!r}')
        for key, dim in (('sectors', 'sector'), ('environments', 'environment')):
            if set(c[key]) - dim_ids[dim]:
                sys.exit(f'✗ Role context {name}: unknown {dim} in {c[key]!r}')
        for prod in c['products']:
            if prod not in {r['product'][0] for r in rows}:
                sys.exit(f'✗ Role context {name}: product {prod!r} is not a proof-point row')
        roles = []
        for role in c['roles']:
            row = next((r for r in rows if r['role'][0] == role['role']), None)
            if row is None or set(role['levels']) - dim_ids['level']:
                sys.exit(f'✗ Role context {name}: role {role["role"]!r} is not a proof-point row, or has an unknown level')
            roles.append({'role': role_name(row), 'aliases': ROLE_ALIASES.get(role['role'], []), 'levels': role['levels'],
                          'scope': quoted(role['scope'], f'{name} scope'),
                          'years': short_years(years.get(role['scope'][1], years[c['section']])),
                          'page': f'https://takenbyninjas.com{ROLES_PATH}{role_slug(row)}/'})
        size = c.get('size')
        slug = CAREER_COMPANY_PAGE[name]
        companies.append({
            'company': name, 'section': c['section'], 'period': years[c['section']], 'years': short_years(years[c['section']]),
            'page': f'https://takenbyninjas.com{page_url(slug)}',
            'sectors': c['sectors'], 'environments': c['environments'],
            'context': quoted(c['context'], f'{name} context') if c.get('context') else None,
            'size': dict(quoted(size[:2], f'{name} size'), people=size[2]) if size else None,
            'products': c['products'], 'roles': roles, 'tier': 'self-reported'})
    return {'generated_by': 'generate_agent_page.py',
            'note': "Role context, Tom's own account (tier: self-reported): what kind of company each role sat in, how big it was, "
                    'and the scope of the role in effect next to its title. A company can carry several sectors and environments at once.',
            'dimensions': {d: [{'id': i, 'label': l, 'asks': a} for i, l, a in entries] for d, entries in ROLE_DIMENSIONS.items()},
            'size_ask': ROLE_SIZE_ASK, 'companies': companies}


def references_json(recs):
    periods = {}
    for key, label in PERIODS.items():
        n = sum(1 for r in recs if r['period'] == key)
        if n:
            periods[key] = {'label': label, 'count': n, 'url': f'https://takenbyninjas.com{RECS_PATH}#{key}'}
    data = {'generated_by': 'generate_agent_page.py', 'prefixes': PERIOD_PREFIX, 'periods': periods}
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def write(path, html):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    parsed = load_parsed()
    sections = {sid: s['quotable'] for sid, s in parsed.items()}
    apply_tight(sections)
    recs = load_recommendations()
    write(OUTPUT_FILE, generate_html(sections, recs))
    print(f'✓ Agent facts page generated: {OUTPUT_FILE} ({len(PROOF_POINTS)} proof points, {len(SHAPES)} shapes)')
    write(RECS_FILE, generate_recommendations(recs))
    print(f'✓ Recommendations page generated: {RECS_FILE} ({len(recs)} recommendations)')
    ws_html = generate_working_style()
    write(WORKING_STYLE_FILE, ws_html)
    print(f'✓ Working style page generated: {WORKING_STYLE_FILE} ({len(INSIGHTS_PROFILES)} Insights profiles)')
    for page in PAGES:
        out, html = generate_page(sections, parsed, page, recs)
        write(out, html)
    print(f'✓ {len(PAGES)} pages generated under for-agents/')
    kw_pages = generate_keyword_pages(sections)
    role_pages = generate_role_pages(sections)
    shape_pages = generate_shape_pages(sections)
    for slug, _, _, html in kw_pages + role_pages + shape_pages:
        write(f'for-agents/{slug}/index.html', html)
    print(f'✓ {len(kw_pages) - 1} skill, {len(role_pages) - 1} role and {len(shape_pages) - 1} shape pages generated, each with an index')
    write('for-agents/proof-points.json', proof_points_json(sections))
    print(f'✓ for-agents/proof-points.json written ({sum(len(STORY_FACETS.get(f"R{n:02d}", [])) for n in range(1, len(PROOF_POINTS) + 1))} facets on {sum(1 for n in range(1, len(PROOF_POINTS) + 1) if STORY_FACETS.get(f"R{n:02d}"))} rows)')
    md_text, cv_html = build_cv_appendix(sections, recs)
    write(CV_APPENDIX_MD, md_text)
    write('for-agents/cv-appendix/index.html', cv_html)
    print(f'✓ CV appendix written: {CV_APPENDIX_MD} and for-agents/cv-appendix/ ({len(md_text.split())} words)')
    register = facts_register(sections)
    write(FACTS_FILE, json.dumps(register, ensure_ascii=False, indent=2) + '\n')
    with open(START_MD, encoding='utf-8') as f:
        start_md = f.read()
    write(START_MD, start_md_with_facts(start_md, register))
    print(f'✓ Screening facts register written: {FACTS_FILE} ({len(register["facts"])} facts); entry file card refreshed')
    write(START_PAGE, start_page_html())
    print(f'✓ Entry page written: {START_PAGE}')
    write(MANIFEST_FILE, manifest(kw_pages + role_pages + shape_pages + [('cv-appendix', 'CV appendix for agents', CV_APPENDIX_PATH, cv_html), ('working-style', 'Working style, Insights Discovery profiles 2019 and 2022', WORKING_STYLE_PATH, ws_html)]))
    print(f'✓ Manifest written: {MANIFEST_FILE}')
    write(REFERENCES_FILE, references_json(recs))
    print(f'✓ References table written: {REFERENCES_FILE}')
    write(SECTION_YEARS_FILE, section_years_json(sections))
    write(ROLES_FILE, json.dumps(roles_register(sections), ensure_ascii=False, indent=2) + '\n')
    print(f'✓ Role context written: {ROLES_FILE} ({len(COMPANY_CONTEXT)} companies)')
    print(f'✓ Section years written: {SECTION_YEARS_FILE}')


if __name__ == '__main__':
    main()
