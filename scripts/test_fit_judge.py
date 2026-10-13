#!/usr/bin/env python3
"""Zero-network test for scripts/fit_judge.py (fit evals, layer 2).

    python3 scripts/test_fit_judge.py

What it proves:
1. The 16 cases in evals/fit-questions.md section 3 parse: ids F01 to F16,
   types T1 to T5, context cells read, attachments on disk.
2. The paid gate: a live run refuses without --yes-paid before any request,
   prints the estimated calls, and refuses production whatever the flags.
3. The mechanical C5 (guard patterns win on a fail) and C2 (facet overlap,
   BRIEF marker, prefix match) checks.
4. The pass rule: 5 of 6 with C4 and C5 mandatory.
5. The stub replay end to end, writing a run file.
6. Privacy: the run file carries no visitor text beyond the case message and
   no API key; transcripts record brief text as counts.

No socket is opened: sockets are replaced with a function that raises.
"""
import contextlib
import io
import json
import os
import shutil
import socket
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fit_judge as fj  # noqa: E402

STUBS = os.path.join(fj.FIT_JUDGE, 'stubs')
FAKE_KEY = 'sk-ant-test-FAKE-KEY-never-real-0000'
checks = 0


def ok(label):
    global checks
    checks += 1
    print(f'ok {checks:2d}  {label}')


@contextlib.contextmanager
def no_network():
    def boom(*a, **k):
        raise AssertionError('network call attempted')
    saved = socket.socket
    socket.socket = boom
    try:
        yield
    finally:
        socket.socket = saved


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = fj.main(argv)
    return code, out.getvalue()


def test_cases():
    cases = fj.load_cases()
    assert len(cases) == 16, len(cases)
    assert [c['id'] for c in cases] == [f'F{i:02d}' for i in range(1, 17)]
    assert {c['type'] for c in cases} == {'T1', 'T2', 'T3', 'T4', 'T5'}
    ok('16 cases parse, ids F01 to F16, types T1 to T5')
    by = {c['id']: c for c in cases}
    assert by['F01']['context'] is None and by['F01']['attachment'] is None and by['F01']['thread'] is None
    assert by['F02']['context'].startswith("We're 6 engineers")
    assert by['F15']['thread'] and 'CTO' in by['F15']['thread']
    assert by['F09']['attachment'] and os.path.exists(by['F09']['attachment'])
    assert by['F10']['attachment'] and os.path.exists(by['F10']['attachment'])
    ok('context cells read: cold, quoted line, thread, two JD attachments on disk')
    assert by['F01']['expected'] == ['FIT.TEAM', 'FIT.FIXER']
    assert by['F09']['expected'] == ['BRIEF'] and by['F10']['expected'] == ['BRIEF', 'FIT.NOT']
    assert by['F14']['expected'] == []
    assert by['F05']['expected'] == ['FIT.ENV', 'FIT.FIXER', 'OPBEAT']
    assert by['F15']['expected'] == ['FIT.TEAM', 'FIT.ENV', 'LEO']
    ok('expected facets: ids, BRIEF marker, prefixes (OPBEAT, LEO), none for F14')
    spec = fj.read_spec()
    assert '| C1 | Context |' in fj.section(spec, 2) and '## 3.' not in fj.section(spec, 2)
    assert fj.type_guidance(spec, 'T3').startswith('Exists: Job 1')
    ok('rubric (section 2) and per-type guidance extracted from the spec')
    user, rec = fj.person_turn(by['F09'])
    assert rec['attachment']['chars'] > 1000 and 'job description' in user
    ok('person turn carries the JD; the transcript records it as counts only')


def test_paid_gate():
    with no_network():
        code, out = run(['--base', 'https://staging--example.netlify.app'])
    assert code == 2 and 'Refusing' in out and '--yes-paid' in out, out
    assert '160 Claude calls' in out and '16 assistant runs of up to 8 tool rounds' in out and '16 judge calls' in out, out
    ok('live run refuses without --yes-paid, after printing 160 Claude calls (16 x 9 assistant, 16 judge) and 128 site calls')
    with no_network():
        code, out = run(['--base', 'https://staging--example.netlify.app', '--case', 'F01'])
    assert code == 2 and '10 Claude calls' in out, out
    ok('--case F01 narrows the estimate to 10 Claude calls')
    for base in ('https://takenbyninjas.com', 'https://www.takenbyninjas.com/', 'http://staging.takenbyninjas.com'):
        with no_network():
            code, out = run(['--base', base, '--yes-paid'])
        assert code == 2 and 'production' in out, (base, out)
    ok('production refused even with --yes-paid')
    assert fj.estimate_calls(16) == (160, 128)
    ok('estimate_calls(16) = 160 Claude, 128 site')


def _transcript(calls, answer):
    return {'rounds': [{'n': 1, 'calls': calls}], 'final_answer': answer}


def test_mechanical_checks():
    ranking, *_ = fj.read_guard() if hasattr(fj, 'read_guard') else fj.ah.read_guard()
    assert fj.verdict_hits('Tom is the ideal candidate for this.', ranking) == ['ideal candidate']
    assert fj.verdict_hits('I would strongly recommend him.', ranking) == ['strongly recommend']
    assert fj.verdict_hits('He looks like a strong fit.', ranking) == ['strong fit']
    assert fj.verdict_hits('He has written about turnarounds and growth; the gap is fintech.', ranking) == []
    ok('C5 mechanical: guard patterns and the rubric phrases hit; a plain answer is clean')
    t = _transcript([{'tool': 'ask', 'sections': ['FIT.TEAM', 'META.COMPETENCIES']}], '')
    assert fj.facet_overlap(['FIT.TEAM', 'FIT.FIXER'], t) == (True, ['FIT.TEAM', 'META.COMPETENCIES'])
    assert fj.facet_overlap(['FIT.NOT'], t)[0] is False
    assert fj.facet_overlap([], t)[0] is True
    ok('C2 mechanical: any overlap passes, no overlap fails, no expectation passes')
    t = _transcript([{'tool': 'ask', 'sections': ['OPBEAT.R1.GROWTH']}], '')
    assert fj.facet_overlap(['OPBEAT'], t)[0] is True
    t = _transcript([{'tool': 'brief', 'sections': []}], '')
    assert fj.facet_overlap(['BRIEF', 'FIT.NOT'], t)[0] is True
    t = _transcript([{'tool': 'ask', 'sections': ['FIT.NOT']}], '')
    assert fj.facet_overlap(['BRIEF'], t)[0] is False
    ok('C2 mechanical: prefix match (OPBEAT), BRIEF needs a brief call')
    data = {'section': 'A', 'matches': [{'section': 'B', 'also': [{'section': 'C'}]}],
            'rows': [{'section': 'D', 'adjacent': {'section': 'E'}}, 'junk']}
    assert fj.sections_in(data) == ['A', 'B', 'C', 'D', 'E'] and fj.sections_in(None) == []
    ok('sections_in reads top level, matches, rows, also and adjacent')


def test_pass_rule():
    ranking = ['\\bideal candidate\\b']
    case = {'id': 'X', 'type': 'T1', 'expected': ['FIT.TEAM']}
    t = _transcript([{'tool': 'ask', 'sections': ['FIT.TEAM']}], 'Gap: no fintech. He takes unowned problems.')
    all1 = {c: 1 for c in fj.CHECKS} | {'notes': {'summary': 's'}}
    assert fj.score(case, t, all1, ranking)['result'] == 'pass'
    assert fj.score(case, t, all1 | {'C6': 0}, ranking)['result'] == 'pass'
    assert fj.score(case, t, all1 | {'C6': 0, 'C1': 0}, ranking)['result'] == 'fail'
    ok('pass rule: 6/6 and 5/6 pass, 4/6 fails')
    assert fj.score(case, t, all1 | {'C4': 0}, ranking)['result'] == 'fail'
    assert fj.score(case, t, all1 | {'C5': 0}, ranking)['result'] == 'fail'
    ok('pass rule: C4 and C5 mandatory (5/6 with either at 0 fails)')
    bad = _transcript([{'tool': 'ask', 'sections': ['FIT.TEAM']}], 'He is the ideal candidate.')
    r = fj.score(case, bad, all1, ranking)
    assert r['checks']['C5'] == 0 and r['result'] == 'fail' and r['judge']['C5'] == 1 and 'C5 mechanical' in r['note']
    ok('C5: mechanical fail wins over a judge 1; the judge opinion stays recorded')
    off = _transcript([{'tool': 'ask', 'sections': ['META.SERVICES']}], 'Gap: fintech.')
    r = fj.score(case, off, all1 | {'C2': 1}, ranking)
    assert r['checks']['C2'] == 0 and r['total'] == 5 and r['result'] == 'pass' and 'C2 mechanical' in r['note']
    ok('C2: mechanical result is the score; judge 1 recorded beside it')
    assert fj.parse_judge('Here you go:\n```json\n{"C1":1,"C2":0,"C3":1,"C4":1,"C5":1,"C6":1,"notes":{"summary":"x"}}\n```') == \
        {'C1': 1, 'C2': 0, 'C3': 1, 'C4': 1, 'C5': 1, 'C6': 1, 'notes': {'summary': 'x'}}
    ok('judge JSON parsed out of fences and chatter')


def test_stub_replay():
    tmp = tempfile.mkdtemp()
    try:
        runs = os.path.join(tmp, 'runs')
        os.environ['ANTHROPIC_API_KEY'] = FAKE_KEY
        with no_network():
            code, out = run(['--stub', STUBS, '--write', '--runs-dir', runs, '--date', '2026-10-13'])
        assert code == 0, out
        assert 'fit judge: 2/2 passed (100%, set passes at 80%)' in out, out
        assert 'skipped F03, F04' in out and 'F16' in out
        ok('stub replay: F01 and F02 pass (F02 at 5/6), the other 14 skipped as no stub, exit 0')
        path = os.path.join(runs, '2026-10-13.md')
        text = open(path, encoding='utf-8').read()
        assert fj.RUN_MARKER in text and '- mode: stub' in text and '- cases: 2/2 passed (100%)' in text
        rows = {}
        for t in fj.ah.parse_tables(text):
            if t['header'][:2] == ['id', 'type'] and 'result' in t['header']:
                rows = {r['id']: r for r in t['rows']}
        assert rows['F01']['result'] == 'pass' and rows['F02']['result'] == 'pass' and rows['F02']['c6'] == '0'
        assert '<details>' in text and '### F02 (T1): pass' in text and 'Three things, one need' in text
        ok('run file: marker, totals, per-case rows with C1 to C6, answers in a collapsed section')
        assert "We're 6 engineers" not in text, 'context line leaked into the run file'
        assert FAKE_KEY not in text and 'sk-ant' not in text
        assert 'What would Tom bring to my team?' in text
        ok('privacy: run file has the message, not the context line, and no key')
        for name in ('F01.json', 'F02.json'):
            raw = open(os.path.join(STUBS, name), encoding='utf-8').read()
            assert FAKE_KEY not in raw and 'sk-ant' not in raw
        f02 = json.load(open(os.path.join(STUBS, 'F02.json'), encoding='utf-8'))
        brief = [c for r in f02['transcript']['rounds'] for c in r['calls'] if c['tool'] == 'brief'][0]
        assert 'text' not in brief and brief['chars'] == 86 and brief['lines'] == 1
        ok('privacy: stub transcripts record the brief as counts, no key anywhere')
        with no_network():
            code, out = run(['--stub', STUBS, '--case', 'F02'])
        assert code == 0 and 'fit judge: 1/1 passed' in out and 'skipped' not in out
        ok('--case F02 on the stub dir runs one case')
        with no_network():
            code, out = run(['--stub', STUBS, '--case', 'F03'])
        assert code == 1 and 'fit judge: 0/0 passed' in out
        ok('a case with no stub is skipped and the set does not pass')
        src = open(fj.__file__, encoding='utf-8').read()
        assert 'print(' not in src.split('class Claude')[1].split('def text_of')[0], 'Claude class must never print'
        assert "load_dotenv(os.path.join(ROOT, '.env'))" in src
        ok('the key is read from the environment or .env and the API client never prints')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        os.environ.pop('ANTHROPIC_API_KEY', None)


def test_tool_execution():
    class Site:
        def __init__(self):
            self.calls = []

        def call(self, key, method, path, body=None, ctype=None, pace=True):
            self.calls.append((method, path, body, ctype))
            if path.startswith('/ask/brief'):
                return 200, json.dumps({'rows': [{'section': 'FIT.NOT', 'also': [{'section': 'FIT.FIXER'}]}]})
            if path.startswith('/ask?q='):
                return 200, json.dumps({'section': 'FIT.TEAM', 'matches': [{'section': 'FIT.TEAM'}]})
            return 200, 'x' * (fj.TOOL_RESULT_CAP + 10)

    site = Site()
    rec, text = fj.run_tool('ask', {'q': 'What would Tom bring?'}, site)
    assert rec['sections'] == ['FIT.TEAM'] and site.calls[-1][1] == '/ask?q=What%20would%20Tom%20bring%3F'
    rec, text = fj.run_tool('brief', {'text': 'line one\nline two'}, site)
    assert rec == {'tool': 'brief', 'chars': 17, 'lines': 2, 'status': 200, 'sections': ['FIT.NOT', 'FIT.FIXER'], 'result': text}
    assert site.calls[-1] == ('POST', '/ask/brief', 'line one\nline two', 'text/plain')
    ok('tools: ask is GET /ask?q=, brief is POST text/plain recorded as counts, sections read')
    rec, text = fj.run_tool('fetch', {'path': '/for-agents/recommendations/'}, site)
    assert text.endswith(f'[truncated at {fj.TOOL_RESULT_CAP} characters]') and len(rec['result']) == fj.TOOL_RESULT_CAP + 10
    rec, text = fj.run_tool('fetch', {'path': '/admin'}, site)
    assert rec['error'] and text.startswith('error') and len(site.calls) == 3
    ok('tools: fetch capped for the model, kept whole in the transcript, refused outside /for-agents/')


def main():
    test_cases()
    test_paid_gate()
    test_mechanical_checks()
    test_pass_rule()
    test_stub_replay()
    test_tool_execution()
    print(f'\n{checks}/{checks} checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
