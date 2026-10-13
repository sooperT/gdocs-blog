#!/usr/bin/env python3
"""Health evals for the agent side (PRD W10.1, backlog item 24).

Runs the three fixed sets in docs/agent-readable/evals/health/ against a base
URL, grades them, and (with --write) writes runs/<date>.md with the delta
against the previous run. The cases live in the markdown files only; this
script parses them and holds no second copy.

    retrieval.md     GET /ask?q=...       hit@1, hit@3, deflection on must-be-null
    adversarial.md   mixed                assertion vocabulary (see that file)
    calibration.md   POST /ask/brief      met / partial / not met / fact per requirement

A live run is PAID (Voyage embeddings, Claude calls on briefs). It prints the
number of paid calls and refuses without --yes-paid. The night shift never
passes that flag. A --stub run answers every case from canned JSON and opens
no connection at all.

    python3 scripts/agent_health.py --stub docs/agent-readable/evals/health/stubs/run1.json
    python3 scripts/agent_health.py --base https://staging--<site>.netlify.app --set all --yes-paid --write
    python3 scripts/agent_health.py --base https://staging--<site>.netlify.app --free-only
"""
import argparse
import datetime
import difflib
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEALTH = os.path.join(ROOT, 'docs', 'agent-readable', 'evals', 'health')
GUARD_JS = os.path.join(ROOT, 'netlify', 'functions', 'lib', 'guard.js')
UA = 'tbn-agent-health/1.0 (+https://takenbyninjas.com/for-agents/)'
TIMEOUT = 120
RUN_MARKER = '<!-- agent_health v1 -->'
SETS = ('retrieval', 'adversarial', 'calibration')
MET_VALUES = ('met', 'partial', 'not met', 'fact', 'not stated')
MAX_REQUIREMENTS = 16          # calibrate.js MAX_REQUIREMENTS
EMBEDS_PER_REQUIREMENT = 3     # the requirement plus up to two evidence queries
CLAUDE_PER_BRIEF = 2           # splitter + evidence queries

# Mirrors of netlify/functions/lib/guard.js, used only when the file cannot be
# read or parsed at runtime (RANKING_PATTERNS, RATE_LIMIT, RATE_WINDOW_MS).
FALLBACK_RANKING = [r'\bideal candidate\b', r'\brank (?:this|him|tom)\b', r'\bstrongly recommend', r'\btop candidate\b']
FALLBACK_RATE = (20, 60000)
# Mirror of guard.js CURRENCY_AMOUNT (the `no_money_amount` assertion).
MONEY = re.compile(r'(?:DKK|kr\.?|€|\$|£|EUR|USD|GBP)\s?\d|\d[\d.,]*\s?[kKmM]?\s?(?:DKK|kr\b|kr\.|€|EUR|USD|GBP)')


# --- guard.js constants -------------------------------------------------------

def read_guard(path=GUARD_JS):
    """(ranking regexes, rate limit, window ms, where they came from)."""
    try:
        src = open(path, encoding='utf-8').read()
        block = re.search(r'RANKING_PATTERNS\s*=\s*\[(.*?)\];', src, re.S)
        pats = re.findall(r'^\s*/(.+)/i,?\s*$', block.group(1), re.M) if block else []
        limit = re.search(r'RATE_LIMIT\s*=\s*(\d+)', src)
        window = re.search(r'RATE_WINDOW_MS\s*=\s*(\d+)\s*\*\s*(\d+)', src)
        if pats and limit and window:
            for p in pats:
                re.compile(p, re.I)
            return pats, int(limit.group(1)), int(window.group(1)) * int(window.group(2)), 'guard.js'
    except (OSError, re.error, AttributeError):
        pass
    return list(FALLBACK_RANKING), FALLBACK_RATE[0], FALLBACK_RATE[1], 'fallback mirror'


# --- markdown tables ----------------------------------------------------------

def _cells(line):
    inner = line.strip()
    inner = inner[1:] if inner.startswith('|') else inner
    inner = inner[:-1] if inner.endswith('|') and not inner.endswith('\\|') else inner
    out = []
    for c in re.split(r'(?<!\\)\|', inner):
        c = c.strip().replace('\\|', '|')
        if len(c) >= 2 and c.startswith('`') and c.endswith('`') and '`' not in c[1:-1]:
            c = c[1:-1]
        out.append(c)
    return out


def parse_tables(text):
    """Every markdown table as {heading, meta, header, rows}. `meta` holds the
    `- key: value` lines between the heading and the table."""
    tables, heading, meta = [], '', {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        h = re.match(r'^#{1,6}\s+(.*)$', line)
        if h:
            heading, meta = h.group(1).strip(), {}
        m = re.match(r'^-\s+([a-z_]+):\s*(.+)$', line)
        if m:
            meta[m.group(1)] = m.group(2).strip().strip('`')
        if line.lstrip().startswith('|') and i + 1 < len(lines) and re.match(r'^\s*\|[\s:|-]+\|\s*$', lines[i + 1]):
            header = [c.lower() for c in _cells(line)]
            rows = []
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith('|'):
                cells = _cells(lines[i])
                if len(cells) == len(header):
                    rows.append(dict(zip(header, cells)))
                i += 1
            tables.append({'heading': heading, 'meta': dict(meta), 'header': header, 'rows': rows})
            continue
        i += 1
    return tables


def _read(name, health=HEALTH):
    with open(os.path.join(health, name), encoding='utf-8') as fh:
        return fh.read()


def _ids(cell):
    return [x.strip() for x in cell.split(',') if x.strip()]


def load_retrieval(health=HEALTH):
    cases = []
    for t in parse_tables(_read('retrieval.md', health)):
        if t['header'][:3] != ['id', 'question', 'expected']:
            continue
        for r in t['rows']:
            if not re.match(r'^[RN]\d+$', r['id']):
                continue
            null = r['expected'].strip().lower() == 'null'
            cases.append({'id': r['id'], 'set': 'retrieval', 'question': r['question'], 'null': null,
                          'expected': [] if null else _ids(r['expected'])})
    return cases


def expand_input(text):
    """`\\n` escapes, plus two generators: @chars:<n>:<unit> and @lines:<n>:<template with {i}>."""
    m = re.match(r'^@chars:(\d+):(.*)$', text, re.S)
    if m:
        n, unit = int(m.group(1)), m.group(2).replace('\\n', '\n') or 'x'
        return (unit * (n // len(unit) + 1))[:n]
    m = re.match(r'^@lines:(\d+):(.*)$', text, re.S)
    if m:
        return '\n'.join(m.group(2).replace('{i}', str(i)) for i in range(1, int(m.group(1)) + 1))
    return text.replace('\\n', '\n')


def load_adversarial(health=HEALTH):
    cases = []
    for t in parse_tables(_read('adversarial.md', health)):
        if t['header'][:4] != ['id', 'endpoint', 'input', 'expect']:
            continue
        for r in t['rows']:
            if not re.match(r'^A\d+$', r['id']):
                continue
            ep = r['endpoint']
            burst = 1
            b = re.match(r'^BURST\s+(\d+)\s+(.*)$', ep)
            if b:
                burst, ep = int(b.group(1)), b.group(2)
            m = re.match(r'^(GET|POST)\s+(\S+)(?:\s+as\s+(\S+))?$', ep)
            if not m:
                raise ValueError(f"{r['id']}: cannot read endpoint {r['endpoint']!r}")
            cases.append({'id': r['id'], 'set': 'adversarial', 'method': m.group(1), 'path': m.group(2),
                          'ctype': m.group(3) or 'text/plain', 'burst': burst, 'raw_input': r['input'],
                          'input': expand_input(r['input']), 'cost': r.get('cost', 'free').strip().lower(),
                          'assertions': [a.strip() for a in r['expect'].split(';') if a.strip()]})
    return cases


def load_calibration(health=HEALTH):
    """One entry per ad: slug, brief text, expected rows."""
    ads = []
    for t in parse_tables(_read('calibration.md', health)):
        if t['header'][:5] != ['id', 'ok', 'conf', 'requirement', 'met']:
            continue
        slug = t['heading'].split()[0]
        rows = []
        for r in t['rows']:
            if not re.match(r'^[A-Z]{2}\d+$', r['id']):
                continue
            alts = []
            for part in re.split(r'\s+or\s+', r['met'].strip()):
                value, _, fact_type = part.partition(':')
                value = value.strip()
                if value not in MET_VALUES:
                    raise ValueError(f"{r['id']}: unknown met value {part!r}")
                alts.append((value, fact_type.strip() or None))
            rows.append({'id': r['id'], 'requirement': r['requirement'], 'met': alts,
                         'sections': [] if r['section'].strip() in ('', '-') else _ids(r['section']),
                         'confirmed': r['ok'].strip().lower().startswith('[x]'), 'low': '?' in r['conf']})
        brief_src = t['meta'].get('brief', 'requirements')
        if brief_src == 'requirements':
            brief = '\n'.join(r['requirement'] for r in rows)
        else:
            with open(os.path.join(health, brief_src), encoding='utf-8') as fh:
                brief = fh.read()
        ads.append({'slug': slug, 'brief': brief, 'brief_src': brief_src, 'rows': rows})
    return ads


# --- transports ---------------------------------------------------------------

class Live:
    """Real HTTP. Paces itself under the guard's per-IP limit."""

    def __init__(self, base, limit, window_ms):
        self.base = base.rstrip('/')
        self.gap = (window_ms / 1000.0) / max(1, limit) * 1.15
        self.window = window_ms / 1000.0
        self.last = 0.0

    def call(self, key, method, path, body=None, ctype=None, pace=True):
        if pace:
            wait = self.gap - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
        self.last = time.time()
        headers = {'User-Agent': UA}
        data = None
        if method == 'POST':
            data = (body or '').encode('utf-8')
            headers['Content-Type'] = ctype or 'text/plain'
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
                return res.status, res.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8', 'replace')
        except Exception as e:  # network error, timeout, bad URL
            return None, f'{type(e).__name__}: {e}'

    def cool_down(self):
        time.sleep(self.window)


class Stub:
    """Canned responses keyed by case id (ad slug for calibration). Never
    touches the network: it has no code path that could."""

    def __init__(self, paths):
        self.cases = {}
        for p in paths:
            files = sorted(glob.glob(os.path.join(p, '*.json'))) if os.path.isdir(p) else [p]
            for f in files:
                with open(f, encoding='utf-8') as fh:
                    self.cases.update(json.load(fh).get('cases', {}))
        self.cursor = {}

    def call(self, key, method, path, body=None, ctype=None, pace=True):
        entry = self.cases.get(key)
        if entry is None:
            return None, f'no stub for {key}'
        if isinstance(entry, list):   # a burst: one canned response per request
            n = self.cursor.get(key, 0)
            self.cursor[key] = n + 1
            entry = entry[min(n, len(entry) - 1)]
        if 'json' in entry:
            return entry.get('status', 200), json.dumps(entry['json'])
        return entry.get('status', 200), entry.get('text', '')

    def cool_down(self):
        pass


# --- reading a response -------------------------------------------------------

def as_json(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def strings(node, skip=()):
    """Every string value in a JSON tree, except under the keys in `skip`."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for x in node:
            yield from strings(x, skip)
    elif isinstance(node, dict):
        for k, v in node.items():
            if k not in skip:
                yield from strings(v, skip)


# `requirement` is the asker's own words echoed back (a job ad may say "the
# ideal candidate"); usage/note/error are fixed server strings.
ECHO_KEYS = ('requirement',)
NON_EVIDENCE_KEYS = ('requirement', 'usage', 'note', 'error', 'human_version', 'reason')


def trust_violations(status, text, ranking):
    """Trust contract (PRD section 4) on any response: every row carries
    section, source and year keys; no ranking word in any output text."""
    out = []
    data = as_json(text)
    body = list(strings(data, ECHO_KEYS)) if data is not None else [text or '']
    for p in ranking:
        if any(re.search(p, s, re.I) for s in body):
            out.append(f'ranking word /{p}/')
    if isinstance(data, dict) and status == 200:
        for key in ('rows', 'matches'):
            for i, row in enumerate(data.get(key) or []):
                if not isinstance(row, dict):
                    out.append(f'{key}[{i}] is not an object')
                    continue
                missing = [k for k in ('section', 'source', 'year') if k not in row]
                if missing:
                    out.append(f"{key}[{i}] has no {', '.join(missing)}")
    return out


# --- retrieval ----------------------------------------------------------------

def run_retrieval(cases, client, ranking):
    results = []
    for c in cases:
        status, text = client.call(c['id'], 'GET', '/ask?q=' + urllib.parse.quote(c['question']))
        data = as_json(text)
        why = []
        hit3 = None
        if status != 200 or not isinstance(data, dict):
            why.append(f'status {status}' if status else (text or 'no response')[:100])
        elif c['null']:
            if data.get('answer') is not None:
                why.append(f"expected null, got {data.get('section')} (score {data.get('score')})")
        else:
            top = data.get('section')
            top3 = [m.get('section') for m in (data.get('matches') or [])[:3] if isinstance(m, dict)]
            hit3 = any(s in c['expected'] for s in top3) or top in c['expected']
            if top not in c['expected']:
                got = 'null' if data.get('answer') is None else f"{top} (score {data.get('score')})"
                why.append(f"expected {' or '.join(c['expected'])}, got {got}" + ('; expected id is in the top 3' if hit3 else ''))
        why += ['trust: ' + v for v in trust_violations(status, text, ranking)]
        results.append({'id': c['id'], 'set': 'retrieval', 'result': 'fail' if why else 'pass', 'why': '; '.join(why),
                        'null': c['null'], 'hit3': hit3})
    return results


# --- adversarial --------------------------------------------------------------

def _rows(data):
    return data.get('rows') if isinstance(data, dict) and isinstance(data.get('rows'), list) else []


def check_assertion(a, statuses, text, data, ranking):
    """None when the assertion holds, else a short reason."""
    status = statuses[-1]
    if a.startswith('status='):
        return None if str(status) == a[7:].strip() else f'status {status}'
    if a.startswith('status in '):
        return None if str(status) in _ids(a[10:]) else f'status {status}'
    if a.startswith('any_status='):
        return None if a[11:].strip() in [str(s) for s in statuses] else f"no {a[11:].strip()} in {len(statuses)} requests"
    if a == 'json':
        return None if data is not None else 'body is not JSON'
    if a == 'answer=null':
        if not isinstance(data, dict) or 'answer' not in data:
            return 'no answer field'
        return None if data['answer'] is None else f"answer from {data.get('section')}"
    if a.startswith('section in '):
        spec = a[11:]
        or_null = spec.endswith(' or null')
        ids = _ids(spec[:-8] if or_null else spec)
        if not isinstance(data, dict):
            return 'body is not JSON'
        if data.get('answer') is None and 'section' not in data:
            return None if or_null else 'answer is null'
        return None if data.get('section') in ids else f"section {data.get('section')}"
    m = re.match(r'^rows(<=|>=)(\d+)$', a)
    if m:
        n = len(_rows(data))
        ok = n <= int(m.group(2)) if m.group(1) == '<=' else n >= int(m.group(2))
        return None if ok else f'{n} rows'
    if a.startswith('flag:'):
        flags = data.get('flags') if isinstance(data, dict) else None
        return None if isinstance(flags, list) and a[5:].strip() in flags else f'flags {flags}'
    m = re.match(r'^injection_lines>=(\d+)$', a)
    if m:
        n = data.get('injection_lines') if isinstance(data, dict) else None
        return None if isinstance(n, int) and n >= int(m.group(1)) else f'injection_lines {n}'
    if a.startswith('no_text_matching:'):
        hit = re.search(a[17:], text or '', re.I)
        return f'text matches: {hit.group(0)[:60]!r}' if hit else None
    if a.startswith('no_evidence_matching:') or a == 'no_money_amount':
        pat = MONEY if a == 'no_money_amount' else re.compile(a[21:], re.I)
        body = strings(data, NON_EVIDENCE_KEYS) if data is not None else [text or '']
        for s in body:
            hit = pat.search(s)
            if hit:
                return f'evidence matches: {hit.group(0)[:60]!r}'
        return None
    if a == 'no_ranking_words':
        body = list(strings(data, ECHO_KEYS)) if data is not None else [text or '']
        for p in ranking:
            for s in body:
                hit = re.search(p, s, re.I)
                if hit:
                    return f'ranking word: {hit.group(0)!r}'
        return None
    m = re.match(r'^row_met:(.+)=([^=]+)$', a)
    if m:
        allowed = _ids(m.group(2))
        hits = [r for r in _rows(data) if isinstance(r, dict) and re.search(m.group(1), str(r.get('requirement') or ''), re.I)]
        bad = [r.get('met') for r in hits if r.get('met') not in allowed]
        return f"row is {bad[0]!r}" if bad else None   # no such row is fine: nothing was claimed
    if a.startswith('rows_met_only:'):
        allowed = _ids(a[14:])
        bad = [r.get('met') for r in _rows(data) if isinstance(r, dict) and r.get('met') not in allowed]
        return f"a row is {bad[0]!r}" if bad else None
    return f'unknown assertion {a!r}'


def run_adversarial(cases, client, ranking):
    results = []
    bursts = [c for c in cases if c['burst'] > 1]
    for c in [c for c in cases if c['burst'] == 1] + bursts:   # bursts last: they trip the limiter
        path, body = c['path'], None
        if c['method'] == 'GET' and path.endswith('?q='):
            path += urllib.parse.quote(c['input'])
        elif c['method'] == 'POST':
            body = c['input']
        statuses, text = [], ''
        for _ in range(c['burst']):
            status, text = client.call(c['id'], c['method'], path, body, c['ctype'], pace=c['burst'] == 1)
            statuses.append(status)
        if c['burst'] > 1:
            client.cool_down()
        data = as_json(text)
        why = []
        if statuses[-1] is None:
            why.append((text or 'no response')[:100])
        else:
            for a in c['assertions']:
                reason = check_assertion(a, statuses, text, data, ranking)
                if reason:
                    why.append(f'{a.split(":")[0]}: {reason}')
            # A case that asserts on ranking words itself reports them once.
            seen = 'no_ranking_words' in c['assertions']
            why += ['trust: ' + v for v in trust_violations(statuses[-1], text, ranking) if not (seen and v.startswith('ranking'))]
        results.append({'id': c['id'], 'set': 'adversarial', 'result': 'fail' if why else 'pass', 'why': '; '.join(why)})
    return results


# --- calibration --------------------------------------------------------------

STOP = set('a an the and or of to in for with on at by is are be as that this you your youve youll we our it its from'.split())


def _tokens(s):
    return [t for t in re.findall(r'[a-z0-9]+', s.lower().replace("'", '').replace('\u2019', '')) if t not in STOP]


def similarity(a, b):
    """Token containment (so a server-side fragment still finds its line) with a
    little sequence ratio to break ties."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    sa, sb = set(ta), set(tb)
    contain = len(sa & sb) / min(len(sa), len(sb))
    return 0.75 * contain + 0.25 * difflib.SequenceMatcher(None, ' '.join(ta), ' '.join(tb)).ratio()


MATCH_FLOOR = 0.5


def match_rows(expected, returned):
    """Greedy one-to-one match on similarity. Returns (pairs, unmatched expected, unmatched returned)."""
    scored = sorted(((similarity(e['requirement'], str(r.get('requirement') or '')), i, j)
                     for i, e in enumerate(expected) for j, r in enumerate(returned) if isinstance(r, dict)), reverse=True)
    used_e, used_r, pairs = set(), set(), []
    for score, i, j in scored:
        if score < MATCH_FLOOR:
            break
        if i in used_e or j in used_r:
            continue
        used_e.add(i)
        used_r.add(j)
        pairs.append((expected[i], returned[j]))
    return (pairs, [e for i, e in enumerate(expected) if i not in used_e],
            [r for j, r in enumerate(returned) if j not in used_r])


def grade_row(exp, got, old_shape):
    met = got.get('met')
    values = [v for v, _ in exp['met']]
    if old_shape and all(v in ('fact', 'not stated') for v in values):
        return 'skip', 'server predates screening facts (no `kind` on rows)'
    why = []
    hit = [(v, ft) for v, ft in exp['met'] if v == met]
    if not hit:
        why.append(f"met: expected {' or '.join(values)}, got {met}")
    else:
        fact_type = hit[0][1]
        if fact_type and got.get('fact_type') and got.get('fact_type') != fact_type:
            why.append(f"fact_type: expected {fact_type}, got {got.get('fact_type')}")
    if exp['sections'] and met in ('met', 'partial', 'fact') and got.get('section') not in exp['sections']:
        why.append(f"section: expected {' or '.join(exp['sections'])}, got {got.get('section')}")
    return ('fail' if why else 'pass'), '; '.join(why)


def run_calibration(ads, client, ranking):
    results, extras = [], []
    for ad in ads:
        status, text = client.call(ad['slug'], 'POST', '/ask/brief', ad['brief'], 'text/plain')
        data = as_json(text)
        returned = _rows(data)
        if status != 200 or not isinstance(data, dict):
            reason = f'status {status}' if status else (text or 'no response')[:100]
            results += [{'id': e['id'], 'set': 'calibration', 'ad': ad['slug'], 'result': 'fail', 'why': reason,
                         'exp': e, 'got': None} for e in ad['rows']]
            continue
        trust = trust_violations(status, text, ranking)
        if trust:
            results.append({'id': f"T-{ad['slug']}", 'set': 'calibration', 'ad': ad['slug'], 'result': 'fail',
                            'why': 'trust: ' + '; '.join(trust), 'exp': None, 'got': None})
        bad = [r.get('met') for r in returned if isinstance(r, dict) and r.get('met') not in MET_VALUES]
        if bad:
            results.append({'id': f"M-{ad['slug']}", 'set': 'calibration', 'ad': ad['slug'], 'result': 'fail',
                            'why': f'unknown met value {bad[0]!r}', 'exp': None, 'got': None})
        old_shape = bool(returned) and not any(isinstance(r, dict) and 'kind' in r for r in returned)
        pairs, lost, extra = match_rows(ad['rows'], returned)
        for e, g in pairs:
            result, why = grade_row(e, g, old_shape)
            results.append({'id': e['id'], 'set': 'calibration', 'ad': ad['slug'], 'result': result, 'why': why, 'exp': e, 'got': g})
        for e in lost:
            results.append({'id': e['id'], 'set': 'calibration', 'ad': ad['slug'], 'result': 'unmatched',
                            'why': 'no returned row matches this requirement', 'exp': e, 'got': None})
        extras += [(ad['slug'], str(r.get('requirement') or '')[:90], r.get('met')) for r in extra if isinstance(r, dict)]
    return results, extras


def calibration_metrics(results):
    graded = [r for r in results if r.get('exp') and r.get('got')]
    exp_met = [r for r in graded if any(v == 'met' for v, _ in r['exp']['met'])]
    got_met = [r for r in graded if r['got'].get('met') == 'met']
    tp = [r for r in got_met if r in exp_met]
    partial = [r for r in graded if r['got'].get('met') == 'partial']
    pct = lambda a, b: f'{100 * len(a) // len(b)}% ({len(a)}/{len(b)})' if b else 'n/a'
    return {'precision': pct(tp, got_met), 'recall': pct(tp, exp_met), 'partial_rate': pct(partial, graded)}


# --- paid calls ---------------------------------------------------------------

def _brief_cost(lines):
    return CLAUDE_PER_BRIEF, EMBEDS_PER_REQUIREMENT * min(MAX_REQUIREMENTS, max(1, lines))


def paid_calls(retrieval, adversarial, ads):
    """Upper bound: (voyage embeddings, claude calls)."""
    embeds, claude = len(retrieval), 0
    for c in adversarial:
        if c['cost'] == 'embed':
            embeds += c['burst']
        elif c['cost'] == 'split':
            claude += 1
        elif c['cost'] == 'brief':
            k, e = _brief_cost(len([l for l in c['input'].splitlines() if l.strip()]))
            claude, embeds = claude + k, embeds + e
        # 'free' costs nothing; 'guarded' costs nothing when the guard rejects it as expected.
    for ad in ads:
        k, e = _brief_cost(len(ad['rows']) if ad['brief_src'] == 'requirements' else MAX_REQUIREMENTS)
        claude, embeds = claude + k, embeds + e
    return embeds, claude


# --- run file and delta -------------------------------------------------------

def previous_run(runs_dir, date, mode):
    """Latest runs/<date>.md written by this script in the same mode (stub or
    live), today's included. Ignores <date>-brief.md and anything without the
    marker. Returns (filename, {case id: result}) or (None, {})."""
    names = sorted(n for n in (os.listdir(runs_dir) if os.path.isdir(runs_dir) else [])
                   if re.match(r'^\d{4}-\d{2}-\d{2}\.md$', n) and n[:10] <= date)
    for name in reversed(names):
        text = open(os.path.join(runs_dir, name), encoding='utf-8').read()
        if RUN_MARKER not in text or f'- mode: {mode}' not in text:
            continue
        state = {}
        for t in parse_tables(text):
            if t['header'] == ['id', 'set', 'result']:
                state = {r['id']: r['result'] for r in t['rows']}
        return name, state
    return None, {}


def delta(prev, now):
    changed = []
    for cid, result in now.items():
        before = prev.get(cid)
        if before is None:
            changed.append((cid, 'new', result))
        elif before != result:
            changed.append((cid, before, result))
    changed += [(cid, before, 'gone') for cid, before in prev.items() if cid not in now]
    return changed


def _cell(s):
    return str(s).replace('|', '\\|').replace('\n', ' ')


def render(date, base, mode, guard_src, totals, results, extras, metrics, prev_name, changes, paid):
    L = [f'# Agent health run {date}', '', RUN_MARKER, '',
         f'- date: {date}', f'- base: {base}', f'- mode: {mode}', f'- guard constants: {guard_src}',
         f'- paid calls (upper bound): {paid[0]} Voyage embeddings, {paid[1]} Claude calls' if mode == 'live' else '- paid calls: 0 (stub run, no network)',
         '', '## Totals', '', '| set | pass | fail | unmatched | skip | total |', '|---|---|---|---|---|---|']
    for s in SETS:
        if s in totals:
            t = totals[s]
            L.append(f"| {s} | {t['pass']} | {t['fail']} | {t['unmatched']} | {t['skip']} | {t['total']} |")
    L += ['']
    L += [f'- {line}' for line in metrics]
    L += ['', '## Failures', '']
    fails = [r for r in results if r['result'] in ('fail', 'unmatched')]
    if fails:
        L += ['| id | set | result | why |', '|---|---|---|---|']
        L += [f"| {r['id']} | {r['set']} | {r['result']} | {_cell(r['why'])} |" for r in fails]
    else:
        L.append('None.')
    if extras:
        L += ['', '## Returned rows with no expected row', '', '| ad | requirement (first 90 chars) | met |', '|---|---|---|']
        L += [f'| {a} | {_cell(q)} | {m} |' for a, q, m in extras]
    L += ['', f"## Delta against {prev_name or 'nothing (first run in this mode)'}", '']
    if not prev_name:
        L.append('No previous run to compare with.')
    elif not changes:
        L.append('No case changed.')
    else:
        L += ['| id | before | now |', '|---|---|---|']
        L += [f'| {c} | {b} | {n} |' for c, b, n in changes]
    L += ['', '## Case results', '', '| id | set | result |', '|---|---|---|']
    L += [f"| {r['id']} | {r['set']} | {r['result']} |" for r in results]
    return '\n'.join(L) + '\n'


# --- main ---------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--base', help='deployed site for a live (paid) run, e.g. https://staging--<site>.netlify.app')
    ap.add_argument('--set', dest='which', default='all', choices=SETS + ('all',))
    ap.add_argument('--stub', action='append', default=[], help='JSON file or directory of canned responses; repeatable, later files override. No network.')
    ap.add_argument('--write', action='store_true', help='write runs/<date>.md')
    ap.add_argument('--limit', type=int, help='first N cases per set (N ads for calibration)')
    ap.add_argument('--yes-paid', action='store_true', help='confirm the paid calls of a live run')
    ap.add_argument('--free-only', action='store_true', help='live run of the adversarial cases marked cost=free only (plain GETs and a 405)')
    ap.add_argument('--burst', action='store_true', help='include the rate-limit burst case (it trips the limiter for a minute)')
    ap.add_argument('--health-dir', default=HEALTH, help=argparse.SUPPRESS)
    ap.add_argument('--runs-dir', help='where run files live (default: <health>/runs)')
    ap.add_argument('--date', default=datetime.date.today().isoformat(), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    stub = bool(a.stub)
    if not stub and not a.base:
        ap.error('give --base <url> for a live run, or --stub <file> for a dry run')
    runs_dir = a.runs_dir or os.path.join(a.health_dir, 'runs')
    ranking, limit, window_ms, guard_src = read_guard()

    want = SETS if a.which == 'all' else (a.which,)
    retrieval = load_retrieval(a.health_dir) if 'retrieval' in want else []
    adversarial = load_adversarial(a.health_dir) if 'adversarial' in want else []
    ads = load_calibration(a.health_dir) if 'calibration' in want else []
    if a.free_only:
        retrieval, ads = [], []
        adversarial = [c for c in load_adversarial(a.health_dir) if c['cost'] == 'free']
    if not a.burst and not stub:
        adversarial = [c for c in adversarial if c['burst'] == 1]
    if a.limit:
        retrieval, adversarial, ads = retrieval[:a.limit], adversarial[:a.limit], ads[:a.limit]

    paid = paid_calls(retrieval, adversarial, ads)
    guarded = sum(1 for c in adversarial if c['cost'] == 'guarded')
    if stub:
        client, mode, base = Stub(a.stub), 'stub', a.base or '(stub)'
        print(f"Stub run from {', '.join(a.stub)}: no network, 0 paid calls.")
    else:
        mode, base = 'live', a.base.rstrip('/')
        print(f'Live run against {base}')
        print(f'Paid calls, upper bound: {paid[0]} Voyage embeddings and {paid[1]} Claude calls '
              f'({len(retrieval)} retrieval questions, {len(adversarial)} adversarial cases, {len(ads)} briefs).')
        if guarded:
            print(f'{guarded} more cases are free only if the guard rejects them before retrieval (cost=guarded).')
        if (paid[0] or paid[1] or guarded) and not a.yes_paid:
            print('Refusing: this run spends money. Pass --yes-paid to confirm, or --free-only for the free cases.')
            return 2
        client = Live(base, limit, window_ms)
        calls = len(retrieval) + len(adversarial) + len(ads)
        print(f'Pacing: one call every {client.gap:.1f}s (guard limit {limit} per {window_ms // 1000}s), about {int(calls * client.gap / 60) + 1} min.')

    results, extras, metrics = [], [], []
    if retrieval:
        r = run_retrieval(retrieval, client, ranking)
        results += r
        qs, ns = [x for x in r if not x['null']], [x for x in r if x['null']]
        if qs:
            metrics.append(f"retrieval hit@1: {sum(x['result'] == 'pass' for x in qs)}/{len(qs)}; hit@3: {sum(bool(x['hit3']) for x in qs)}/{len(qs)}")
        if ns:
            metrics.append(f"retrieval deflection on must-be-null: {sum(x['result'] == 'pass' for x in ns)}/{len(ns)}")
    if adversarial:
        results += run_adversarial(adversarial, client, ranking)
    if ads:
        r, extras = run_calibration(ads, client, ranking)
        results += r
        m = calibration_metrics(r)
        metrics.append(f"calibration, 'met': precision {m['precision']}, recall {m['recall']}; partial rate {m['partial_rate']}")
        metrics.append(f"calibration rows returned with no expected row: {len(extras)}")

    totals = {}
    for r in results:
        t = totals.setdefault(r['set'], {'pass': 0, 'fail': 0, 'unmatched': 0, 'skip': 0, 'total': 0})
        t[r['result']] += 1
        t['total'] += 1

    print()
    for r in results:
        if r['result'] != 'pass':
            print(f"{r['result'].upper():9s} {r['id']}: {r['why']}")
    for ad, q, m in extras:
        print(f'EXTRA     {ad}: "{q}" ({m})')
    print()
    for s in SETS:
        if s in totals:
            t = totals[s]
            tail = ''.join(f", {t[k]} {k}" for k in ('unmatched', 'skip') if t[k])
            print(f"{s:12s} {t['pass']}/{t['total']} passed, {t['fail']} failed{tail}")
    for line in metrics:
        print(line)

    prev_name, prev = previous_run(runs_dir, a.date, mode)
    now = {r['id']: r['result'] for r in results}
    changes = delta(prev, now) if prev_name else []
    print(f"\nDelta against {prev_name or 'nothing (first run in this mode)'}: " + (f'{len(changes)} changed' if prev_name else 'n/a'))
    for cid, before, after in changes:
        print(f'  {cid}: {before} -> {after}')

    if a.write:
        os.makedirs(runs_dir, exist_ok=True)
        out = os.path.join(runs_dir, f'{a.date}.md')
        with open(out, 'w', encoding='utf-8') as fh:
            fh.write(render(a.date, base, mode, guard_src, totals, results, extras, metrics, prev_name, changes, paid))
        print(f'written: {out}')
    return 1 if any(r['result'] == 'fail' for r in results) else 0


if __name__ == '__main__':
    sys.exit(main())
