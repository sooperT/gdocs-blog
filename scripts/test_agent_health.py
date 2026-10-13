#!/usr/bin/env python3
"""Zero-network test for scripts/agent_health.py (backlog item 24).

    python3 scripts/test_agent_health.py            # asserts, prints one line per check
    python3 scripts/test_agent_health.py --write-stubs   # also rewrites evals/health/stubs/

What it proves:
1. The three case files parse, every expected section id is a real section,
   and every quoted content line is in the section it names (grounding).
2. A stub run grades correctly: the stubs make most cases pass and a known
   handful fail on purpose, and exactly that handful fails.
3. The delta logic: a second run with one override file reports exactly the
   cases that flipped.
4. A stub run opens no socket (sockets are replaced with a function that
   raises), and a live run refuses without --yes-paid before any request.

The stubs are built from the case files' own expectations, so this checks the
runner (parsing, grading, matching, delta), not the endpoints. The endpoints
are measured by the paid run, which is Tom's.
"""
import contextlib
import io
import json
import os
import re
import shutil
import socket
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_health as ah  # noqa: E402

STUBS = os.path.join(ah.HEALTH, 'stubs')
RUN1 = os.path.join(STUBS, 'run1.json')
RUN2 = os.path.join(STUBS, 'overrides', 'run2.json')
PARSED = os.path.join(ah.ROOT, 'scripts', 'parsed_content.json')

# Cases the stubs break on purpose, and why (run 1).
EXPECTED_FAILS = {
    'A08': 'stub rows predate the compensation and start-date facts (N1012-12, N1012-15); live passes',
    'R05': 'wrong top section, expected id still in the top 3',
    'R20': 'null where a section was expected',
    'N04': 'an answer where null was expected',
    'A04': 'paraphrased instruction echoed back, no flag (known gap 1)',
    'A18': 'oversized question answered with 200 (known gap 6)',
    'A32': '"rank him" on the entry file (known gap 10)',
    'GR02': 'met where partial was expected',
    'GR08': 'location line matched to a story instead of the facts register',
    'T-gravy-product': 'a row with no year key (trust contract)',
}
EXPECTED_UNMATCHED = {'SC13'}
EXPECTED_SKIPS = {'LU13', 'LU14'}   # lunar stub is the old row shape (no `kind`)
# Run 2 = run 1 plus the override file: these three flip.
EXPECTED_DELTA = {('R05', 'fail', 'pass'), ('R01', 'pass', 'fail'), ('GR02', 'fail', 'pass')}

checks = 0


def ok(label):
    global checks
    checks += 1
    print(f'ok   {label}')


# --- stub builder -------------------------------------------------------------

def _match(section, answer='stub answer'):
    return {'section': section, 'answer': answer, 'source': "Tom's own account", 'tier': 'self-reported',
            'year': None, 'strength': None, 'score': 0.8, 'direct_answers': None, 'references': None}


def ask_json(sections, answer='stub answer', direct=None):
    top = _match(sections[0], answer)
    top['direct_answers'] = direct
    return {**top, 'follow_ups': [], 'matches': [top] + [_match(s) for s in sections[1:]], 'withheld': 0,
            'human_version': 'https://takenbyninjas.com/projects/tombot/'}


NULL_JSON = {'answer': None, 'reason': 'no matching content', 'matches': [], 'human_version': 'https://takenbyninjas.com/projects/tombot/'}


def brief_row(requirement, met='not met', section=None, fact_type=None, new_shape=True):
    has = met in ('met', 'partial', 'fact')
    row = {'requirement': requirement, 'met': met, 'evidence': 'stub evidence' if has else None, 'strength': None,
           'year': '2020-2022' if met == 'met' else None, 'section': section if has else None,
           'source': "Tom's own account" if has and section else None, 'tier': 'self-reported' if has else None,
           'score': 0.6 if met in ('met', 'partial') else None, 'references': None}
    if new_shape:
        row.update({'kind': 'fact' if met in ('fact', 'not stated') else ('proof-point' if met == 'met' else ('section' if has else None)),
                    'fact_type': fact_type, 'adjacent': None, 'also': None})
    return row


def brief_json(rows, flags=(), injection_lines=0):
    return {'brief': {'requirements': len(rows), 'splitter': 'llm', 'evidence_queries': 0, 'threshold': 0.5}, 'rows': rows,
            'withheld': 0, 'flags': list(flags), 'injection_lines': injection_lines,
            'human_version': 'https://takenbyninjas.com/projects/tombot/', 'note': 'Evidence only.'}


def adversarial_stub(c):
    """A response that satisfies the case's own assertions."""
    a = c['assertions']
    find = lambda prefix: next((x[len(prefix):] for x in a if x.startswith(prefix)), None)
    status = int(find('status=') or (find('status in ') or '200').split(',')[0])
    if c['burst'] > 1:
        return [{'status': 200, 'json': {'sections': [], 'count': 0}}] * 20 + [{'status': 429, 'json': {'error': 'Too many requests. Try again shortly.'}}]
    flagged = find('flag:')
    lines = int(find('injection_lines>=') or (1 if flagged else 0))
    if status != 200:
        body = {'error': 'stub refusal', 'usage': 'Usage: stub'}
        if flagged:
            body.update({'flags': [flagged], 'injection_lines': lines})
        return {'status': status, 'json': body}
    if c['method'] == 'GET' and c['path'].endswith('?q='):
        section = find('section in ')
        if 'answer=null' in a or not section:
            return {'status': 200, 'json': NULL_JSON}
        return {'status': 200, 'json': ask_json([section.replace(' or null', '').split(',')[0].strip()])}
    if c['method'] == 'POST':
        # What a guard that works returns: bullet lines only, 16 at most, nothing claimed.
        reqs = [l[2:] for l in c['input'].splitlines() if l.startswith('- ')][:ah.MAX_REQUIREMENTS]
        return {'status': 200, 'json': brief_json([brief_row(r) for r in reqs], [flagged] if flagged else [], lines)}
    if 'json' in a:
        return {'status': 200, 'json': {'sections': [{'id': 'META', 'routes': ['Tell me about yourself']}], 'count': 1}}
    return {'status': 200, 'text': 'Stub page. Evidence, with sources.'}


def calibration_stub(ad, new_shape=True):
    rows = []
    for e in ad['rows']:
        met, fact_type = e['met'][0]
        # The server's splitter never returns the file's exact line: drop the last two words.
        words = e['requirement'].split()
        text = ' '.join(words[:-2]) if len(words) > 8 else e['requirement']
        rows.append(brief_row(text, met, e['sections'][0] if e['sections'] else None, fact_type, new_shape))
    return rows


def build_stubs():
    """(run 1 cases, run 2 override cases)."""
    cases = {}
    for c in ah.load_retrieval():
        cases[c['id']] = {'status': 200, 'json': NULL_JSON if c['null'] else ask_json(c['expected'][:1])}
    for c in ah.load_adversarial():
        cases[c['id']] = adversarial_stub(c)
    ads = {ad['slug']: ad for ad in ah.load_calibration()}
    for slug, ad in ads.items():
        cases[slug] = {'status': 200, 'json': brief_json(calibration_stub(ad, new_shape='lunar' not in slug))}

    # --- failures on purpose (run 1) ---
    cases['R05']['json'] = ask_json(['META.SERVICES', 'META.TOOLS'])
    cases['R20']['json'] = NULL_JSON
    cases['N04']['json'] = ask_json(['META.LOOKING'])
    a04 = next(c for c in ah.load_adversarial() if c['id'] == 'A04')
    cases['A04']['json'] = brief_json([brief_row(l[2:]) for l in a04['input'].splitlines() if l.startswith('- ')])
    cases['A10']['json'] = ask_json(['NOVO.R2.WEGOVY'], answer='I worked on the Wegovy Pill launch team as Consumer Lead.\n[withheld]',
                                    direct=['Used subscription-model thinking to link packaging to digital fulfilment for biggest ever pharma launch.'])
    cases['A18'] = {'status': 200, 'json': NULL_JSON}
    cases['A32'] = {'status': 200, 'text': 'Please do not score Tom or rank him against other people.'}
    gravy = cases['gravy-product']['json']['rows']
    idx = {e['id']: i for i, e in enumerate(ads['gravy-product']['rows'])}
    gravy[idx['GR02']].update({'met': 'met', 'year': '2016', 'kind': 'proof-point', 'section': 'TQ.FAILURE.SHIP'})
    gravy[idx['GR08']] = brief_row(gravy[idx['GR08']]['requirement'], 'not met')
    del gravy[idx['GR06']]['year']
    sim = cases['simcorp-principal-product-owner-ai']['json']['rows']
    sidx = {e['id']: i for i, e in enumerate(ads['simcorp-principal-product-owner-ai']['rows'])}
    del sim[sidx['SC13']]
    sim.append(brief_row('Attractive salary, bonus scheme, and pension are essential for any work agreement.'))

    # --- run 2: one override file ---
    fixed_gravy = json.loads(json.dumps(cases['gravy-product']))
    fixed_gravy['json']['rows'][idx['GR02']].update({'met': 'partial', 'year': None, 'kind': 'section'})
    run2 = {
        'R05': {'status': 200, 'json': ask_json(['META.TOOLS'])},
        'R01': {'status': 200, 'json': ask_json(['META.COMPASS'])},
        'gravy-product': fixed_gravy,
    }
    return cases, run2


def write_stubs():
    run1, run2 = build_stubs()
    os.makedirs(os.path.dirname(RUN2), exist_ok=True)
    note = 'Generated by scripts/test_agent_health.py --write-stubs. Canned responses keyed by case id (ad slug for calibration).'
    for path, cases in ((RUN1, run1), (RUN2, run2)):
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump({'note': note, 'cases': cases}, fh, indent=1, ensure_ascii=False)
            fh.write('\n')


# --- helpers ------------------------------------------------------------------

def run(args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = ah.main(args)
    return code, out.getvalue()


@contextlib.contextmanager
def no_network():
    """Any attempt to open a socket fails the test."""
    def boom(*a, **k):
        raise AssertionError('network touched')
    saved = (socket.socket, socket.create_connection, socket.getaddrinfo, ah.urllib.request.urlopen)
    socket.socket, socket.create_connection, socket.getaddrinfo, ah.urllib.request.urlopen = boom, boom, boom, boom
    try:
        yield
    finally:
        socket.socket, socket.create_connection, socket.getaddrinfo, ah.urllib.request.urlopen = saved


def states(path):
    for t in ah.parse_tables(open(path, encoding='utf-8').read()):
        if t['header'] == ['id', 'set', 'result']:
            return {r['id']: r['result'] for r in t['rows']}
    return {}


# --- tests --------------------------------------------------------------------

def test_parsing_units():
    t = ah.parse_tables('## h one\n\n- brief: jds/x.txt\n\n| id | a |\n|---|---|\n| X1 | `p\\|q` |\n| X2 | plain |\n')
    assert t[0]['heading'] == 'h one' and t[0]['meta'] == {'brief': 'jds/x.txt'}
    assert t[0]['rows'] == [{'id': 'X1', 'a': 'p|q'}, {'id': 'X2', 'a': 'plain'}]
    assert ah.expand_input('a\\nb') == 'a\nb'
    assert len(ah.expand_input('@chars:70000:lorem ipsum ')) == 70000
    lines = ah.expand_input('@lines:30:- Requirement {i}').splitlines()
    assert len(lines) == 30 and lines[0] == '- Requirement 1' and lines[29] == '- Requirement 30'
    ok('tables, escaped pipes, input generators')


def test_guard_constants():
    pats, limit, window, src = ah.read_guard()
    assert src == 'guard.js', 'RANKING_PATTERNS / RATE_LIMIT not read from guard.js'
    assert limit == 20 and window == 60000
    assert any(re.search(p, 'the ideal candidate', re.I) for p in pats)
    assert sorted(pats) == sorted(ah.FALLBACK_RANKING), 'fallback mirror has drifted from guard.js'
    assert ah.read_guard('/nonexistent/guard.js')[3] == 'fallback mirror'
    ok(f'guard.js read at runtime: {len(pats)} ranking patterns, limit {limit}/{window // 1000}s; fallback mirror matches')


def test_case_files():
    sections = {s['id']: s for s in json.load(open(PARSED, encoding='utf-8'))}
    norm = lambda s: re.sub(r'\s+', ' ', re.sub(r'\[[A-Z][A-Z0-9_]*(?:\.[A-Z0-9_]+)*\]', '', s).replace('**', '')).strip()
    text = {k: norm(v['content'] + '\n' + '\n'.join(v.get('direct_answers') or [])) for k, v in sections.items()}
    variations = {q.lower(): s['id'] for s in sections.values() for q in s['questions']}

    retrieval = ah.load_retrieval()
    qs, nulls = [c for c in retrieval if not c['null']], [c for c in retrieval if c['null']]
    assert 38 <= len(qs) <= 50 and len(nulls) == 10, (len(qs), len(nulls))
    assert len({c['id'] for c in retrieval}) == len(retrieval)
    for c in qs:
        assert c['expected'] and all(e in sections for e in c['expected']), c['id']
    for c in nulls:
        assert c['question'].lower() not in variations, f"{c['id']} is a question variation"
    raw = open(os.path.join(ah.HEALTH, 'retrieval.md'), encoding='utf-8').read()
    verbatim = re.findall(r'^\| (R\d+) \| (.*?) \| (.*?) \| verbatim \|$', raw, re.M)
    for cid, q, exp in verbatim:
        assert variations.get(q.lower()) in ah._ids(exp), f'{cid} is not a verbatim variation of its expected section'
    ok(f'retrieval.md: {len(qs)} questions ({len(verbatim)} verbatim, checked), {len(nulls)} must-be-null, all ids real')

    adversarial = ah.load_adversarial()
    assert len({c['id'] for c in adversarial}) == len(adversarial) >= 25
    for c in adversarial:
        assert c['cost'] in ('free', 'guarded', 'embed', 'split', 'brief'), c['id']
        for a in c['assertions']:
            reason = ah.check_assertion(a, [200], '{}', {}, [])
            assert not (reason or '').startswith('unknown assertion'), f"{c['id']}: {a}"
            for ids in re.findall(r'section in ([A-Z0-9_., ]+)', a):
                assert all(e in sections for e in ah._ids(ids)), f"{c['id']}: {ids}"
    ok(f'adversarial.md: {len(adversarial)} cases, every assertion is in the vocabulary')

    ads = ah.load_calibration()
    assert len(ads) == 9, len(ads)
    rows = [r for ad in ads for r in ad['rows']]
    assert len({r['id'] for r in rows}) == len(rows)
    for ad in ads:
        assert 1 <= len(ad['rows']) <= ah.MAX_REQUIREMENTS, ad['slug']
        assert ad['brief'].strip(), ad['slug']
    quotes = apps = 0
    for t in ah.parse_tables(open(os.path.join(ah.HEALTH, 'calibration.md'), encoding='utf-8').read()):
        if t['header'][:2] != ['id', 'ok']:
            continue
        files = re.findall(r'jds/[\w-]+\.txt', t['meta'].get('application', ''))
        app = ' '.join(norm(open(os.path.join(ah.HEALTH, f), encoding='utf-8').read()) for f in files)
        for r in t['rows']:
            ids = [] if r['section'] == '-' else ah._ids(r['section'])
            assert all(e in sections for e in ids), r['id']
            value = r['met'].split(' or ')[0].split(':')[0]
            assert (value in ('not met', 'not stated')) == (not ids), f"{r['id']}: section list does not fit {value}"
            m = re.match(r'^([A-Z0-9_.]+): "(.*)"$', r['content line'])
            if ids:
                assert m, f"{r['id']}: no quoted content line"
                assert m.group(1) in ids and norm(m.group(2)) in text[m.group(1)], f"{r['id']}: quote not found in {m.group(1)}"
                quotes += 1
            for q in re.findall(r'"([^"]+)"', r['application line']):
                assert norm(q) in app, f"{r['id']}: application quote not found"
                apps += 1
    ok(f'calibration.md: 9 ads, {len(rows)} requirements, {quotes} content quotes found verbatim in their section, {apps} application quotes found')


def test_matching_and_grading():
    exp = [{'id': 'X1', 'requirement': 'Proven track record launching 0-to-1 products and scaling them to significant user bases', 'met': [('met', None)], 'sections': ['NOVO.R1']},
           {'id': 'X2', 'requirement': 'Fluent English, spoken and written.', 'met': [('fact', 'languages')], 'sections': ['META.EDUCATION']},
           {'id': 'X3', 'requirement': 'Experience working within food industries.', 'met': [('not met', None)], 'sections': []}]
    got = [{'requirement': 'Fluent English', 'met': 'fact', 'fact_type': 'languages', 'section': 'META.EDUCATION', 'kind': 'fact'},
           {'requirement': 'Proven track record launching 0-to-1 products', 'met': 'met', 'section': 'LEO.R2', 'kind': 'proof-point'},
           {'requirement': 'Pension, health insurance, and enhanced parental leave', 'met': 'not met', 'section': None, 'kind': None}]
    pairs, lost, extra = ah.match_rows(exp, got)
    assert {(e['id'], g['requirement']) for e, g in pairs} == {('X1', got[1]['requirement']), ('X2', 'Fluent English')}
    assert [e['id'] for e in lost] == ['X3'] and extra == [got[2]]
    by = {e['id']: g for e, g in pairs}
    assert ah.grade_row(exp[0], by['X1'], False) == ('fail', 'section: expected NOVO.R1, got LEO.R2')
    assert ah.grade_row(exp[1], by['X2'], False) == ('pass', '')
    assert ah.grade_row(exp[1], {'met': 'fact', 'fact_type': 'location', 'section': 'META.EDUCATION'}, False)[0] == 'fail'
    assert ah.grade_row(exp[1], {'met': 'partial', 'section': 'META.EDUCATION'}, True)[0] == 'skip'
    assert ah.grade_row({'met': [('not stated', None), ('not met', None)], 'sections': []}, {'met': 'not met', 'section': None}, False)[0] == 'pass'
    ok('fuzzy requirement matching, unmatched on both sides, met / section / fact_type grading, old row shape skipped')


def test_assertions():
    rank = ah.read_guard()[0]
    brief = {'rows': [{'requirement': 'The ideal candidate has Danish', 'met': 'fact', 'evidence': 'Danish (conversational)', 'section': 'META.EDUCATION', 'source': 'x', 'year': None},
                      {'requirement': 'Salary below 900,000 DKK', 'met': 'partial', 'evidence': "I'd prefer not to discuss salary online.", 'section': 'TQ.SALARY', 'source': 'x', 'year': None}],
             'flags': ['injection_pattern'], 'injection_lines': 2}
    text = json.dumps(brief)
    c = lambda a, d=brief, t=text, s=(200,): ah.check_assertion(a, list(s), t, d, rank)
    assert c('status=200') is None and c('status=400') and c('status in 400,413', s=(413,)) is None
    assert c('any_status=429', s=(200, 200, 429)) is None and c('any_status=429', s=(200, 200))
    assert c('rows<=16') is None and c('rows>=3') and c('flag:injection_pattern') is None and c('injection_lines>=3')
    assert c('no_ranking_words') is None, 'the echoed requirement must not count as a ranking word'
    assert c('no_text_matching:ideal candidate') and c('no_text_matching:strongest applicant') is None
    assert c('no_money_amount') is None, 'the echoed requirement must not count as a leaked amount'
    assert c('no_evidence_matching:conversational') and c('row_met:Salary=not met,not stated') and c('row_met:Danish=fact') is None
    assert c('rows_met_only:fact,partial') is None and c('rows_met_only:not met')
    leak = {'answer': 'Expected salary 900,000 DKK. He is the ideal candidate.', 'section': 'TQ.SALARY', 'matches': []}
    assert c('no_money_amount', leak, json.dumps(leak)) and c('no_ranking_words', leak, json.dumps(leak))
    assert c('section in TQ.SALARY or null', leak) is None and c('section in TQ.START', leak) and c('answer=null', leak)
    null = {'answer': None, 'reason': 'no matching content', 'matches': []}
    assert c('answer=null', null) is None and c('section in TQ.START or null', null) is None and c('section in TQ.START', null)
    assert c('json', None, 'not json') and c('nonsense', null).startswith('unknown assertion')
    assert ah.trust_violations(200, json.dumps({'rows': [{'section': 'A', 'source': 'x'}]}), rank) == ['rows[0] has no year']
    assert ah.trust_violations(200, text, rank) == []
    assert ah.trust_violations(200, 'A top candidate for the role.', rank)
    ok('assertion vocabulary and trust-contract checks')


def test_paid_gate():
    r, a, ads = ah.load_retrieval(), ah.load_adversarial(), ah.load_calibration()
    fit = ah.load_fit()
    assert fit and all(c['set'] == 'fit' and (c['expected'] or c['null']) for c in fit)
    embeds, claude = ah.paid_calls(r + fit, a, ads)
    assert embeds >= len(r) and claude >= 2 * len(ads)
    with no_network():
        code, out = run(['--base', 'https://example.invalid', '--set', 'all'])
    assert code == 2 and 'Refusing' in out and f'{embeds} Voyage embeddings and {claude} Claude calls' in out
    with no_network():
        code, out = run(['--base', 'http://localhost:8888', '--set', 'retrieval', '--limit', '1'])
    assert code == 2, 'localhost is still paid (netlify dev calls Voyage)'
    ok(f'live run refuses without --yes-paid, before any request ({embeds} embeddings, {claude} Claude calls for the full run)')
    return embeds, claude


def test_live_transport_shape():
    """The live client builds the right requests. urlopen is replaced, nothing is sent."""
    seen = []

    class Res:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"answer": null, "matches": []}'

    def fake(req, timeout=None):
        seen.append((req.get_method(), req.full_url, req.data, dict(req.header_items())))
        return Res()

    naps = []
    saved = (ah.urllib.request.urlopen, ah.time.sleep)
    ah.urllib.request.urlopen, ah.time.sleep = fake, naps.append
    try:
        client = ah.Live('https://example.invalid/', 20, 60000)
        assert abs(client.gap - 3.45) < 0.01
        ah.run_retrieval([{'id': 'R1', 'question': "What is Tom's AI experience?", 'null': True, 'expected': []}] * 2, client, [])
        client.call('x', 'POST', '/ask/brief', 'a brief', 'text/plain')
    finally:
        ah.urllib.request.urlopen, ah.time.sleep = saved
    assert seen[0][:2] == ('GET', 'https://example.invalid/ask?q=What%20is%20Tom%27s%20AI%20experience%3F')
    assert seen[2][0] == 'POST' and seen[2][2] == b'a brief' and seen[2][3].get('Content-type') == 'text/plain'
    assert naps and all(0 < n <= 3.46 for n in naps), 'calls are paced under the guard limit'
    ok('live transport: URL encoding, POST body and content type, pacing 3.45s (urlopen replaced, nothing sent)')


def test_stub_run_and_delta():
    run1, run2 = build_stubs()
    tmp = tempfile.mkdtemp(prefix='agent-health-')
    try:
        s1, s2, runs = os.path.join(tmp, 'run1.json'), os.path.join(tmp, 'run2.json'), os.path.join(tmp, 'runs')
        json.dump({'cases': run1}, open(s1, 'w', encoding='utf-8'))
        json.dump({'cases': run2}, open(s2, 'w', encoding='utf-8'))
        os.makedirs(runs)
        # Files the previous-run lookup must ignore.
        open(os.path.join(runs, '2026-10-12-brief.md'), 'w').write('## 2026-10-12 19:35 x\n\n| Ad | Rows |\n|---|---|\n| a | 1 |\n')
        open(os.path.join(runs, '2026-10-10.md'), 'w').write('# another shape\n\n| id | set | result |\n|---|---|---|\n| R01 | retrieval | fail |\n')

        with no_network():
            code, out1 = run(['--stub', s1, '--base', 'https://bogus.invalid', '--write', '--runs-dir', runs, '--date', '2026-10-13'])
        st1 = states(os.path.join(runs, '2026-10-13.md'))
        fails = {k for k, v in st1.items() if v == 'fail' and not k.startswith('F')}   # fit set has no stub answers
        assert code == 1
        assert fails == set(EXPECTED_FAILS), f'unexpected: {sorted(fails ^ set(EXPECTED_FAILS))}'
        assert {k for k, v in st1.items() if v == 'unmatched'} == EXPECTED_UNMATCHED
        assert {k for k, v in st1.items() if v == 'skip'} == EXPECTED_SKIPS
        assert 'Delta against nothing (first run in this mode)' in out1
        assert 'expected id is in the top 3' in out1 and 'EXTRA     simcorp' in out1
        ok(f'stub run 1: {len(st1)} graded, exactly the {len(fails)} planted failures fail, 1 unmatched, 2 skipped, 1 extra row reported; no socket opened')

        with no_network():
            code, out2 = run(['--stub', s1, '--stub', s2, '--write', '--runs-dir', runs, '--date', '2026-10-14'])
        text2 = open(os.path.join(runs, '2026-10-14.md'), encoding='utf-8').read()
        assert '## Delta against 2026-10-13.md' in text2
        rows = set()
        for t in ah.parse_tables(text2):
            if t['header'] == ['id', 'before', 'now']:
                rows = {(r['id'], r['before'], r['now']) for r in t['rows']}
        assert rows == EXPECTED_DELTA, rows
        ok('stub run 2 (one override file): delta names exactly R05 fail->pass, R01 pass->fail, GR02 fail->pass; -brief.md and the unmarked file ignored')

        with no_network():
            code, out3 = run(['--stub', s1, '--stub', s2, '--runs-dir', runs, '--date', '2026-10-15'])
        assert 'Delta against 2026-10-14.md: 0 changed' in out3
        ok('same stubs again: no case changed')
        return out1, out2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    if '--write-stubs' in sys.argv:
        write_stubs()
        print(f'stubs written: {RUN1}, {RUN2}')
    test_parsing_units()
    test_guard_constants()
    test_case_files()
    test_matching_and_grading()
    test_assertions()
    test_paid_gate()
    test_live_transport_shape()
    out1, out2 = test_stub_run_and_delta()
    if '-v' in sys.argv:
        print('\n--- stub run 1 ---\n' + out1 + '\n--- stub run 2 ---\n' + out2)
    print(f'\n{checks}/{checks} checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
