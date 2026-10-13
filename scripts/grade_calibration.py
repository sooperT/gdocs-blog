#!/usr/bin/env python3
"""
Grading pages for the calibration set (slice-status 2026-10-13, section 4 item 6).

Tom has 56 to 69 `?` rows to tick in evals/health/calibration.md. This tool
puts everything he needs for one tick in one block, per ad:

    python3 scripts/grade_calibration.py --all                 # one page per ad
    python3 scripts/grade_calibration.py --ad gravy-product    # one ad
    python3 scripts/grade_calibration.py --all --run <runs/<date>.md> --run <briefs dir or stub json>
    python3 scripts/grade_calibration.py --apply docs/agent-readable/evals/health/grading/gravy-product.md

Pages go to evals/health/grading/<slug>.md. Each requirement row shows:
the ad's line verbatim; the expected value today and its basis (the content
line the proposal rests on); the row the endpoint returned in the last run,
if any run data holds it; the closest lines from Tom's own application text
(keyword overlap, a heuristic); and one tick line.

`--run` is repeatable and takes three shapes. A run page (`runs/<date>.md`,
written by agent_health.py) gives per-row pass / fail / unmatched and the
grader's reason; it does not store returned rows. A directory of
`<slug>.json` brief responses (`briefs-<date>/`) or a stub file with `cases`
(`stubs/run1.json`) gives the returned rows themselves. With no --run, the
latest run page and the latest `briefs-*` directory are used. The returned
row is paired to the expected row with agent_health.match_rows, the same
pairing the grader uses.

`--apply` reads one grading page back. A row counts as graded when exactly
one of its four boxes is `[x]`. For those rows only, `ok` becomes `[x]` and
`met` becomes the ticked value; a row ticked `not met` gets section `-`;
a row ticked `fact/not stated` takes `fact:<type>` or `not stated:<type>` from
its note line when one is written there, else keeps its current met value if
that already is a fact or not-stated value, else becomes `not stated`. Every
other byte of calibration.md is left as it was, including the Counts lines
and the Summary table (they go stale; the diff summary says so). No network.
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent_health import match_rows, MET_VALUES  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEALTH = os.path.join(ROOT, 'docs', 'agent-readable', 'evals', 'health')
CALIBRATION = os.path.join(HEALTH, 'calibration.md')
GRADING = os.path.join(HEALTH, 'grading')
RUNS = os.path.join(HEALTH, 'runs')

GRADE_LINE = '- grade: [ ] met  [ ] partial  [ ] not met  [ ] fact/not stated'
GRADE_BOXES = ('met', 'partial', 'not met', 'fact/not stated')
TICK = re.compile(r'\[([ xX])\]\s*(met|partial|not met|fact/not stated)')
ROW_ID = re.compile(r'^[A-Z]{2}\d+$')
STOP = set('a an the and or of to in for with on at by is are be as that this you your youve youll we our it its from '
           'have has had not no but into across who what which their they them he his i my me was were will would can '
           'about also than then there these those more most such up out so if when where how all any each other'.split())


# --- calibration.md, line-aware ---------------------------------------------

def split_cells_raw(line):
    """The raw cell strings of a table line, between the leading and trailing
    pipes, with their surrounding spaces kept (so the line can be rebuilt byte
    for byte)."""
    s = line.rstrip('\n')
    assert s.startswith('|') and s.endswith('|'), line
    inner = s[1:-1]
    return re.split(r'(?<!\\)\|', inner)


def join_cells_raw(cells):
    return '|' + '|'.join(cells) + '|'


def parse_calibration(text):
    """Ads from calibration.md with line numbers kept: [{slug, meta, header,
    rows: [{id, ok, conf, requirement, met, section, content_line,
    application_line, line}]}]. Mirrors agent_health.load_calibration's table
    test (header starts id | ok | conf | requirement | met)."""
    lines = text.splitlines()
    ads, slug, meta = [], None, {}
    i = 0
    while i < len(lines):
        line = lines[i]
        h = re.match(r'^#{1,6}\s+(.*)$', line)
        if h:
            slug, meta = h.group(1).strip().split()[0], {}
        m = re.match(r'^-\s+([a-z_]+):\s*(.+)$', line)
        if m:
            meta[m.group(1)] = m.group(2).strip().strip('`')
        if line.startswith('|') and i + 1 < len(lines) and re.match(r'^\s*\|[\s:|-]+\|\s*$', lines[i + 1]):
            header = [c.strip().lower() for c in split_cells_raw(line)]
            if header[:5] == ['id', 'ok', 'conf', 'requirement', 'met']:
                rows = []
                i += 2
                while i < len(lines) and lines[i].startswith('|'):
                    cells = [c.strip() for c in split_cells_raw(lines[i])]
                    if len(cells) == len(header) and ROW_ID.match(cells[0]):
                        r = dict(zip(header, cells))
                        rows.append({'id': r['id'], 'ok': r['ok'], 'conf': r['conf'], 'requirement': r['requirement'],
                                     'met': r['met'], 'section': r['section'], 'content_line': r.get('content line', ''),
                                     'application_line': r.get('application line', ''), 'line': i})
                    i += 1
                ads.append({'slug': slug, 'meta': dict(meta), 'header': header, 'rows': rows})
                continue
        i += 1
    return ads


# --- run data -----------------------------------------------------------------

def parse_run_page(text):
    """{id: (result, why)} from a runs/<date>.md page. The Failures table has
    the reason; Case results has every id."""
    out = {}
    section = None
    for line in text.splitlines():
        h = re.match(r'^##\s+(.*)$', line)
        if h:
            section = h.group(1).strip().lower()
            continue
        if not line.startswith('|') or re.match(r'^\|[\s:|-]+\|$', line):
            continue
        cells = [c.strip() for c in line.strip()[1:-1].split('|')]
        if section == 'failures' and len(cells) == 4 and cells[1] == 'calibration':
            out[cells[0]] = (cells[2], cells[3].replace('\\|', '|'))
        elif section == 'case results' and len(cells) == 3 and cells[1] == 'calibration':
            out.setdefault(cells[0], (cells[2], ''))
    return out


def load_run_sources(paths):
    """Returns (grades: {id: (result, why)}, returned: {slug: ([rows], source label)}, used: [labels])."""
    grades, returned, used = {}, {}, []
    for p in paths:
        if os.path.isdir(p):
            n = 0
            for f in sorted(glob.glob(os.path.join(p, '*.json'))):
                with open(f, encoding='utf-8') as fh:
                    d = json.load(fh)
                rows = d.get('rows') if isinstance(d, dict) else None
                if isinstance(rows, list):
                    returned[os.path.basename(f)[:-5]] = (rows, os.path.basename(p))
                    n += 1
            used.append(f'{os.path.relpath(p, ROOT)} ({n} ads)')
        elif p.endswith('.json'):
            with open(p, encoding='utf-8') as fh:
                d = json.load(fh)
            n = 0
            for key, entry in (d.get('cases') or {}).items():
                e = entry[0] if isinstance(entry, list) else entry
                rows = (e.get('json') or {}).get('rows') if isinstance(e, dict) else None
                if isinstance(rows, list) and not re.match(r'^[A-Z]\d+$', key):
                    returned[key] = (rows, os.path.basename(p))
                    n += 1
            used.append(f'{os.path.relpath(p, ROOT)} ({n} ads)')
        else:
            with open(p, encoding='utf-8') as fh:
                g = parse_run_page(fh.read())
            grades.update(g)
            used.append(f'{os.path.relpath(p, ROOT)} ({len(g)} graded rows)')
    return grades, returned, used


def default_run_sources():
    out = []
    pages = sorted(f for f in glob.glob(os.path.join(RUNS, '*.md')) if not f.endswith('-brief.md'))
    if pages:
        out.append(pages[-1])
    briefs = sorted(d for d in glob.glob(os.path.join(HEALTH, 'briefs-*')) if os.path.isdir(d))
    if briefs:
        out.append(briefs[-1])
    return out


# --- application text ---------------------------------------------------------

def tokens(s):
    out = []
    for t in re.findall(r'[a-z0-9]+', s.lower().replace("'", '').replace('’', '')):
        if t in STOP or len(t) < 3:
            continue
        for suf in ('ing', 'ed', 'es', 's'):   # crude stem so "experiments" meets "experiment"
            if len(t) > 4 and t.endswith(suf):
                t = t[:-len(suf)]
                break
        out.append(t)
    return out


def application_lines(text):
    """Readable fragments of a pdftotext -layout file: columns split at runs
    of three or more spaces, short fragments dropped."""
    frags = []
    for line in text.splitlines():
        for part in re.split(r'\s{3,}', line.strip()):
            part = re.sub(r'\s+', ' ', part).strip('​ ').strip()
            if len(tokens(part)) >= 3:
                frags.append(part)
    return frags


def application_files(meta, health=HEALTH):
    """Paths named in the `- application:` line ("none on disk" gives [])."""
    spec = meta.get('application', '')
    paths = []
    for m in re.finditer(r'jds/[\w.-]+\.txt', spec):
        p = os.path.join(health, m.group(0))
        if os.path.exists(p):
            paths.append(p)
    return paths


def closest_lines(requirement, frags, n=3, floor=2):
    """Up to n fragments sharing at least `floor` stems with the requirement;
    when none does, up to two sharing one distinctive stem (6+ letters)."""
    want = set(tokens(requirement))
    scored, weak = [], []
    for f in frags:
        hit = want & set(tokens(f))
        if len(hit) >= floor:
            scored.append((len(hit), f))
        elif any(len(t) >= 6 for t in hit):
            weak.append((max(len(t) for t in hit), f))
    scored.sort(key=lambda x: -x[0])
    if scored:
        return [f for _, f in scored[:n]]
    weak.sort(key=lambda x: -x[0])
    return [f for _, f in weak[:2]]


# --- render -------------------------------------------------------------------

def rel(path):
    """Path relative to the repo when it is inside it, else as given."""
    r = os.path.relpath(path, ROOT)
    return path if r.startswith('..') else r


def one_line(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def render_row(row, grade, got, app_lines, run_label, got_label):
    L = [f"### {row['id']}" + ('  (?)' if '?' in row['conf'] else ''), '']
    L.append(f"- ad: {one_line(row['requirement'])}")
    basis = one_line(row['content_line'])
    L.append(f"- expected today: `{row['met']}` | section {row['section'] or '-'} | basis: {basis}")
    if grade:
        result, why = grade
        L.append(f"- last run ({run_label}): {result}" + (f", {why}" if why else ''))
    if got:
        ev = one_line(got.get('evidence'))
        sc = got.get('score')
        L.append(f"- returned ({got_label}): `{got.get('met')}` | section {got.get('section') or '-'} | score {sc if sc is not None else '-'}"
                 + (f" | kind {got['kind']}" if got.get('kind') else '')
                 + f" | split as: {one_line(got.get('requirement'))}")
        L.append(f"  evidence: {ev or '-'}")
    elif got_label:
        L.append(f'- returned ({got_label}): no row paired with this requirement')
    elif grade:
        L.append(f'- returned: the {run_label} page stores verdicts only, and no briefs or stub file holds this ad')
    else:
        L.append('- returned: no run data for this ad')
    app_prior = one_line(row['application_line'])
    if app_prior and app_prior.lower() not in ('none', 'none on disk'):
        L.append(f"- application (from calibration.md): {app_prior}")
    if app_lines:
        L.append('- application, closest lines (keyword overlap, a heuristic, not a judgement):')
        L += [f'  - {a}' for a in app_lines]
    elif app_prior.lower() in ('', 'none', 'none on disk'):
        L.append('- application, closest lines: none found')
    L += [GRADE_LINE, '- note: ', '']
    return L


def render_ad(ad, grades, returned, used, health=HEALTH):
    frags = []
    for p in application_files(ad['meta'], health):
        with open(p, encoding='utf-8') as fh:
            frags += application_lines(fh.read())
    rows = ad['rows']
    got_by_id, got_label = {}, ''
    if ad['slug'] in returned:
        got_rows, got_label = returned[ad['slug']]
        pairs, _, _ = match_rows([{'requirement': r['requirement'], 'id': r['id']} for r in rows], got_rows)
        got_by_id = {e['id']: g for e, g in pairs}
    low = [r for r in rows if '?' in r['conf']]
    rest = [r for r in rows if '?' not in r['conf']]
    run_label = next((u.split(' ')[0].split('/')[-1].replace('.md', '') for u in used if u.endswith('graded rows)')), 'run')
    L = [f"# Grading: {ad['slug']}", '',
         f"Generated {datetime.date.today().isoformat()} by `scripts/grade_calibration.py` from `evals/health/calibration.md`. "
         "Tick one box per row, write a note if the box needs one, then "
         f"`python3 scripts/grade_calibration.py --apply docs/agent-readable/evals/health/grading/{ad['slug']}.md`.", '',
         f"- brief: {ad['meta'].get('brief', 'requirements')}",
         f"- application: {ad['meta'].get('application', 'none on disk')}",
         f"- run data: {'; '.join(used) if used else 'none'}",
         f"- returned rows for this ad: {len(returned[ad['slug']][0]) if ad['slug'] in returned else 'none'}"
         + (f" from {got_label} (an earlier run than the {run_label} verdicts when the dates differ), paired to {len(got_by_id)} expected rows" if got_label else ''),
         f"- rows: {len(rows)}, low confidence (`?`): {len(low)}, already ticked: {sum(r['ok'].lower().startswith('[x]') for r in rows)}",
         '',
         'Rule (N1010-13 a): `met` needs a year and an outcome in the content; `partial` is content with no year or no outcome; '
         '`not met` is nothing in the content (your own application line is content debt, not a grading error); '
         '`fact/not stated` is a screening line answered from the facts register. '
         'Grade what the content holds, not how well you fit.', '']
    if low:
        L += [f'## Low confidence rows ({len(low)})', '']
        for r in low:
            L += render_row(r, grades.get(r['id']), got_by_id.get(r['id']), closest_lines(r['requirement'], frags), run_label, got_label)
    if rest:
        L += [f'## Other rows ({len(rest)})', '']
        for r in rest:
            L += render_row(r, grades.get(r['id']), got_by_id.get(r['id']), closest_lines(r['requirement'], frags), run_label, got_label)
    return '\n'.join(L).rstrip('\n') + '\n'


# --- apply --------------------------------------------------------------------

def parse_grading(text):
    """{id: {'value': ticked value or None, 'ticks': n, 'note': str}} from a grading page."""
    out, cur = {}, None
    for line in text.splitlines():
        h = re.match(r'^###\s+([A-Z]{2}\d+)\b', line)
        if h:
            cur = h.group(1)
            out[cur] = {'value': None, 'ticks': 0, 'note': ''}
            continue
        if cur is None:
            continue
        if line.startswith('- grade:'):
            ticked = [v for mark, v in TICK.findall(line) if mark.lower() == 'x']
            out[cur]['ticks'] = len(ticked)
            out[cur]['value'] = ticked[0] if len(ticked) == 1 else None
        elif line.startswith('- note:'):
            out[cur]['note'] = line[len('- note:'):].strip()
    return out


def new_met_value(ticked, current, note):
    if ticked != 'fact/not stated':
        return ticked
    m = re.search(r'\b(fact|not stated)(?::([a-z_]+))?', note)
    if m:
        return m.group(1) + (f':{m.group(2)}' if m.group(2) else '')
    if re.match(r'^(fact|not stated)\b', current):
        return current
    return 'not stated'


def apply_grading(cal_text, grading_text):
    """Returns (new calibration text, changes, skipped). Only lines of rows with
    exactly one ticked box change; in those lines only the ok and met cells
    (and section when the tick is `not met`)."""
    grades = parse_grading(grading_text)
    lines = cal_text.splitlines(keepends=True)
    changes, skipped = [], []
    for ad in parse_calibration(cal_text):
        idx = ad['header'].index
        for row in ad['rows']:
            g = grades.get(row['id'])
            if not g:
                continue
            if g['ticks'] != 1:
                if g['ticks'] > 1:
                    skipped.append((row['id'], f"{g['ticks']} boxes ticked"))
                continue
            value = new_met_value(g['value'], row['met'], g['note'])
            base = value.split(':')[0]
            if base not in MET_VALUES:
                skipped.append((row['id'], f'unknown value {value!r}'))
                continue
            raw = lines[row['line']]
            nl = '\n' if raw.endswith('\n') else ''
            cells = split_cells_raw(raw)
            before = (row['ok'], row['met'], row['section'])
            cells[idx('ok')] = ' [x] '
            cells[idx('met')] = f' {value} '
            section = row['section']
            if value == 'not met':
                section = '-'
                cells[idx('section')] = ' - '
            lines[row['line']] = join_cells_raw(cells) + nl
            changes.append((row['id'], before, ('[x]', value, section), g['note']))
    return ''.join(lines), changes, skipped


def diff_summary(changes, skipped):
    L = []
    for cid, (ok0, met0, sec0), (ok1, met1, sec1), note in changes:
        what = [f'ok {ok0} -> {ok1}']
        if met0 != met1:
            what.append(f'met {met0} -> {met1}')
        if sec0 != sec1:
            what.append(f'section {sec0} -> {sec1}')
        L.append(f'{cid}: ' + ', '.join(what) + (f'  (note: {note})' if note else ''))
    for cid, why in skipped:
        L.append(f'{cid}: skipped, {why}')
    L.append(f'{len(changes)} rows updated, {len(skipped)} skipped. Counts lines and the Summary table were not touched; '
             'rerun the night count or leave them for the next regeneration.')
    return '\n'.join(L)


# --- main ---------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('--ad', help='one ad slug (heading in calibration.md)')
    ap.add_argument('--all', action='store_true', help='every ad in calibration.md')
    ap.add_argument('--run', action='append', default=[], help='run page, briefs directory or stub json; repeatable')
    ap.add_argument('--apply', metavar='GRADING_FILE', help='read ticks back into calibration.md')
    ap.add_argument('--calibration', default=CALIBRATION)
    ap.add_argument('--out', default=GRADING, help='output directory for grading pages')
    a = ap.parse_args(argv)

    with open(a.calibration, encoding='utf-8') as fh:
        cal_text = fh.read()

    if a.apply:
        with open(a.apply, encoding='utf-8') as fh:
            grading_text = fh.read()
        new_text, changes, skipped = apply_grading(cal_text, grading_text)
        print(diff_summary(changes, skipped))
        if new_text != cal_text:
            with open(a.calibration, 'w', encoding='utf-8') as fh:
                fh.write(new_text)
            print(f'wrote {rel(a.calibration)}')
        return 0

    if not a.ad and not a.all:
        ap.error('give --ad <slug>, --all, or --apply <grading file>')
    ads = parse_calibration(cal_text)
    if a.ad:
        ads = [x for x in ads if x['slug'] == a.ad]
        if not ads:
            ap.error(f'no ad {a.ad!r} in calibration.md')
    sources = a.run or default_run_sources()
    grades, returned, used = load_run_sources(sources)
    os.makedirs(a.out, exist_ok=True)
    health = os.path.dirname(os.path.abspath(a.calibration))
    total_rows = total_low = total_got = 0
    for ad in ads:
        page = render_ad(ad, grades, returned, used, health)
        path = os.path.join(a.out, f"{ad['slug']}.md")
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(page)
        low = sum('?' in r['conf'] for r in ad['rows'])
        got = len(re.findall(r'\n- returned \([^)]*\): `', page))
        total_rows += len(ad['rows'])
        total_low += low
        total_got += got
        print(f"{ad['slug']:44s} rows {len(ad['rows']):2d}  ? {low:2d}  returned rows paired {got:2d}  -> {rel(path)}")
    print(f"{len(ads)} pages, {total_rows} rows, {total_low} low confidence, {total_got} with a returned row. Run data: {'; '.join(used) or 'none'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
