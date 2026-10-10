#!/usr/bin/env python3
"""
Generate case study posts from TomBot content (W5).

Reads TomBot content (docs/tombot/tombot-content-v3.md) and writes one post
per case study at words/{slug}/index.html, plus its entry in
posts-metadata.json. Two layers on one page (PRD principle 6):

- The title, meta description and first paragraph carry the matchable claim.
  They are built only from verbatim clauses of the page's sections, joined
  by connectives ("at", ":", ". "). Each clause is checked verbatim.
- The body is the verbatim TomBot text of the listed sections, in order,
  with the section id shown once per section. Inline routing tags, HTML
  comments, the routing questions and the follow-up suggestions are removed.

The generator fails loudly if any clause or body paragraph is not verbatim
in its section, so content drift breaks the build instead of the page.

Case studies carry "homepage": false in posts-metadata.json: listed in the
archive, never picked as the homepage post. ("hidden" would also drop them
from the archive and the sitemap.)

Usage:
    python3 generate_case_studies.py
"""

import json
import os
import re
import sys
from html import escape as _escape

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
from parse_content import parse_content_doc  # noqa: E402
from pylib.config import METADATA_FILE, TAG_FILTER_SCRIPT, CONTENT_TYPE_WORDS  # noqa: E402
from pylib.templates import html_head, site_header, site_nav, site_footer  # noqa: E402

CONTENT_FILE = 'docs/tombot/tombot-content-v3.md'
DATE = '2026-10-10'
TAGS = ['case-study']

# Routing tags inside answer text, e.g. "project[NOVO.R1.TRANSFORM]," or " [THEME.GROWTH]"
ROUTING_TAG = re.compile(r' ?\[[A-Z][A-Z0-9_.]+\]')

SPLIT_LINE = ('This case study is generated from TomBot content. '
              'The human version of Tom\'s story is at <a href="/about/">/about/</a> '
              'and you can ask TomBot at <a href="/projects/tombot/">/projects/tombot/</a>.')


def C(section_id, text):
    """A verbatim clause from a TomBot section."""
    return (section_id, text)


# Each claim line is a list of parts: a C(...) clause (checked verbatim) or a
# plain string connective. Connectives are the only non-verbatim words.
CASE_STUDIES = [
    {
        'slug': 'wegovycare',
        'sections': ['NOVO.R1', 'NOVO.R1.TRANSFORM'],
        'title': [C('NOVO.R1', 'Wegovycare'), ': ',
                  C('NOVO.R1', 'Senior Product Manager at Novo Nordisk (Mar 2020 - Feb 2022)')],
        'meta': [C('NOVO.R1', 'Wegovycare'), ': ',
                 C('NOVO.R1', 'Senior Product Manager at Novo Nordisk (Mar 2020 - Feb 2022)'), '. ',
                 C('NOVO.R1', 'I led the full product lifecycle end to end'), '. ',
                 C('NOVO.R1', 'Achieved 10% penetration in our first national market'), '.'],
        'first': [C('NOVO.R1', 'Wegovycare'), ': ',
                  C('NOVO.R1', 'Senior Product Manager at Novo Nordisk (Mar 2020 - Feb 2022)'), '. ',
                  C('NOVO.R1', 'I led the full product lifecycle end to end'), '. ',
                  C('NOVO.R1', 'Achieved 10% penetration in our first national market'), '. ',
                  C('NOVO.R1', 'Automated documentation and shifted release cycles from yearly to '
                               'bi-monthly in high-regulation environment'), '.'],
    },
    {
        'slug': 'treat-turnaround',
        'sections': ['LEO.R1', 'LEO.R1.TURNAROUND', 'LEO.R1.STORY.FEELS', 'LEO.STORY.MODEL'],
        'title': [C('LEO.R1', 'TREAT'), ': ', C('LEO.R1', 'PM/GM'), ' at ',
                  C('LEO.R1', 'LEO Innovation Lab'), ' (', C('LEO.R1', 'Nov 2016 - Aug 2017'), ')'],
        'meta': [C('LEO.R1', 'TREAT'), ': ', C('LEO.R1', 'PM/GM'), ' at ',
                 C('LEO.R1', 'LEO Innovation Lab'), ' (', C('LEO.R1', 'Nov 2016 - Aug 2017'), '). ',
                 C('LEO.R1', 'Halved customer acquisition costs, increased customer activation by 7x'), '.'],
        'first': [C('LEO.R1', 'TREAT'), ': ', C('LEO.R1', 'PM/GM'), ' at ',
                  C('LEO.R1', 'LEO Innovation Lab'), ' (', C('LEO.R1', 'Nov 2016 - Aug 2017'), '). ',
                  C('LEO.R1', 'It was the first product launched by LEO Innovation Lab, and it was underperforming.'),
                  ' ',
                  C('LEO.R1', 'I was parachuted in with a 6-month mandate to stabilise and assess viability.'),
                  ' ',
                  C('LEO.R1', 'Halved customer acquisition costs, increased customer activation by 7x'), '.'],
    },
]


def escape(text):
    """Escape body text, leaving quotes and apostrophes readable in the raw HTML."""
    return _escape(text, quote=False)


def load_sections():
    """Section id -> answer text, with inline routing tags removed."""
    return {s['id']: ROUTING_TAG.sub('', s['content']) for s in parse_content_doc(CONTENT_FILE)}


def load_source_text():
    """The whole content file with routing tags removed: an independent verbatim check."""
    with open(CONTENT_FILE, encoding='utf-8') as f:
        return ROUTING_TAG.sub('', f.read())


def check(sections, section_id, text):
    """Fail loudly if a line is no longer verbatim in its section."""
    if section_id not in sections:
        sys.exit(f'✗ Section {section_id} not found in {CONTENT_FILE}')
    if text not in sections[section_id]:
        sys.exit(f'✗ Not verbatim in {section_id}: {text!r}')


def build_claim(sections, parts):
    out = []
    for part in parts:
        if isinstance(part, tuple):
            check(sections, *part)
            out.append(part[1])
        else:
            out.append(part)
    return ''.join(out)


def section_blocks(text):
    """Split answer text into ('p', text) and ('ul', [items]) blocks on blank lines."""
    blocks = []
    for chunk in re.split(r'\n\s*\n', text.strip()):
        lines = [ln.strip() for ln in chunk.strip().split('\n') if ln.strip()]
        if not lines:
            continue
        # Runs of "- " lines become a list; other lines are paragraphs
        # (e.g. "Key achievements:" directly above its list).
        for ln in lines:
            if ln.startswith('- '):
                if blocks and blocks[-1][0] == 'ul' and blocks[-1][2] is chunk:
                    blocks[-1][1].append(ln[2:])
                else:
                    blocks.append(('ul', [ln[2:]], chunk))
            else:
                blocks.append(('p', ln, chunk))
    return [(kind, value) for kind, value, _ in blocks]


def build_body(sections, source_text, section_ids):
    lines = []
    for sid in section_ids:
        if sid not in sections:
            sys.exit(f'✗ Section {sid} not found in {CONTENT_FILE}')
        lines.append(f'    <p><small>Source: TomBot {escape(sid)}</small></p>')
        for kind, value in section_blocks(sections[sid]):
            texts = value if kind == 'ul' else [value]
            for t in texts:
                check(sections, sid, t)
                if t not in source_text:
                    sys.exit(f'✗ Not verbatim in {CONTENT_FILE}: {t!r}')
            if kind == 'p':
                lines.append(f'    <p>{escape(value)}</p>')
            else:
                lines.append('    <ul>')
                lines.extend(f'        <li>{escape(t)}</li>' for t in value)
                lines.append('    </ul>')
    return lines


def display_date(iso):
    y, m, d = iso.split('-')
    return f'{d}/{m}/{y}'


def generate_page(sections, source_text, cs):
    url = f'/words/{cs["slug"]}/'
    title = build_claim(sections, cs['title'])
    meta = build_claim(sections, cs['meta'])
    first = build_claim(sections, cs['first'])

    body = [
        '    <!-- MAIN CONTENT -->',
        '    <main>',
        f'    <h1>{escape(title)}</h1>',
        f'    <p class="post-meta">Published on: {display_date(DATE)}. Filed under: {", ".join(TAGS)}</p>',
        f'    <p><small>{SPLIT_LINE}</small></p>',
        f'    <p>{escape(first)}</p>',
        '    <!-- EXCERPT_END -->',
    ]
    body += build_body(sections, source_text, cs['sections'])
    body += ['    </main>', '']

    html = '\n'.join([
        '<!-- Generated by: generate_case_studies.py -->',
        '<!-- To modify: Edit docs/tombot/tombot-content-v3.md or generate_case_studies.py and regenerate -->',
        html_head(
            title=escape(title),
            extra_scripts=[TAG_FILTER_SCRIPT],
            meta_description=_escape(meta),
            canonical_path=url,
        ),
        site_header(),
        site_nav(),
        '\n'.join(body),
        site_footer(),
    ]) + '\n'

    entry = {
        'title': title,
        'meta-title': '',
        'url': url,
        'date': DATE,
        'tags': list(TAGS),
        'type': CONTENT_TYPE_WORDS,
        'meta-desc': meta,
        'excerpt': escape(first),
        'hero-image': '',
        'homepage': False,
    }
    return url, html, entry


def update_metadata(entries):
    """Upsert entries by url; new entries go in before the first older post."""
    with open(METADATA_FILE, encoding='utf-8') as f:
        data = json.load(f)
    posts = data['posts']
    for entry in entries:
        idx = next((i for i, p in enumerate(posts) if p.get('url') == entry['url']), None)
        if idx is not None:
            posts[idx] = entry
        else:
            pos = next((i for i, p in enumerate(posts) if p.get('date', '') < entry['date']), len(posts))
            posts.insert(pos, entry)
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def main():
    sections = load_sections()
    source_text = load_source_text()
    entries = []
    for cs in CASE_STUDIES:
        url, html, entry = generate_page(sections, source_text, cs)
        out = os.path.join(url.strip('/'), 'index.html')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'w', encoding='utf-8') as f:
            f.write(html)
        entries.append(entry)
        print(f'✓ Case study generated: {out}')
    update_metadata(entries)
    print(f'✓ {METADATA_FILE} updated ({len(entries)} case studies)')


if __name__ == '__main__':
    main()
