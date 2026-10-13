#!/usr/bin/env python3
"""Fit evals, layer 2: judged, paid (docs/agent-readable/evals/fit-questions.md section 4).

Runs the 16 cases in section 3 of that file through a simulated visiting
assistant (a Claude call with three tools against the deployed site: ask,
brief, fetch) and scores the exchange on the six-check rubric in section 2
with a second Claude call, the judge. Two checks are also run mechanically:

    C5 (no verdict)  guard.js RANKING_PATTERNS over the final answer, plus the
                     rubric's own phrases; a mechanical fail wins.
    C2 (facet)       the sections seen in the ask / brief results against the
                     case's expected facets (any overlap passes); the judge's
                     opinion is recorded beside it.

A case passes at 5 of 6 with C4 and C5 mandatory. The set passes at 80%.

A live run is PAID (Claude calls for the assistant and the judge, Voyage
embeddings on every ask and brief). It prints the number of calls and refuses
without --yes-paid, exactly like agent_health.py, and it never runs against
production. A --stub run replays recorded transcripts and judge outputs from
JSON and opens no connection at all.

    python3 scripts/fit_judge.py --stub docs/agent-readable/evals/health/fit-judge/stubs --write
    python3 scripts/fit_judge.py --base https://staging--<site>.netlify.app --case F01 --yes-paid
    python3 scripts/fit_judge.py --base https://staging--<site>.netlify.app --yes-paid --write

Privacy: the run file carries the case message, counts for any attached text
(a job description is visitor text), and never the API key. Transcripts
(runs/<date>/<id>.json) record every tool call and result; the text a visitor
typed is recorded as counts only.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_health as ah  # noqa: E402  (parse_tables, read_guard, Live, as_json)

ROOT = ah.ROOT
FIT_QUESTIONS = os.path.join(ROOT, 'docs', 'agent-readable', 'evals', 'fit-questions.md')
FIT_JUDGE = os.path.join(ah.HEALTH, 'fit-judge')
CASE_FILES = os.path.join(FIT_JUDGE, 'cases')
JDS = os.path.join(ah.HEALTH, 'jds')
RUN_MARKER = '<!-- fit_judge v1 -->'

ASSISTANT_MODEL = 'claude-sonnet-5-5'
JUDGE_MODEL = 'claude-sonnet-5-5'
MAX_ROUNDS = 8
MAX_OUTPUT_TOKENS = 1500
JUDGE_MAX_TOKENS = 800
TOOL_RESULT_CAP = 20000          # characters of a tool result passed back to the assistant
API_URL = 'https://api.anthropic.com/v1/messages'
API_VERSION = '2023-06-01'
PRODUCTION_HOSTS = ('takenbyninjas.com', 'www.takenbyninjas.com')
CHECKS = ('C1', 'C2', 'C3', 'C4', 'C5', 'C6')
MANDATORY = ('C4', 'C5')
PASS_AT = 5
SET_PASS_PCT = 80

# Section 2 of fit-questions.md lists these beside the guard's patterns.
RUBRIC_VERDICT = [r'\bstrong fit\b', r'\bhighly\b']

# How a `context` cell in section 3 becomes the person's side of the thread.
# Text in quotes is the context line itself; these map the prose cells.
ATTACHMENTS = {
    'Novonesis JD': os.path.join(JDS, 'novonesis-senior-principal-innovation-pm.txt'),
    'a JD that is mostly line management': os.path.join(CASE_FILES, 'F10-line-management-jd.txt'),
}
THREADS = {
    'thread says the person is a CTO at a 40-person health-tech':
        'Earlier in this thread the person said: I am the CTO at a 40-person health-tech company.',
}
COLD = ('cold', 'in the message', 'none')

ASSISTANT_SUFFIX = (
    "\n\nYou are the person's assistant. The person's message follows; the thread context (if any) "
    "is given. Use the tools to consult Tom's agent and pages; every URL in the entry file is served "
    "by the tools as a path. Then answer the person."
)

TOOLS = [
    {'name': 'ask', 'description': "Tom's agent, questions: GET /ask?q=<question>. Returns matches with section, answer, "
                                   "direct_answers, references.",
     'input_schema': {'type': 'object', 'properties': {'q': {'type': 'string', 'description': 'the question, under 500 characters'}},
                      'required': ['q'], 'additionalProperties': False}, 'strict': True},
    {'name': 'brief', 'description': "Tom's agent, role fit: POST /ask/brief with a job description or context lines as plain "
                                     "text (max 12000 characters). Returns one row per requirement.",
     'input_schema': {'type': 'object', 'properties': {'text': {'type': 'string', 'description': 'the brief, plain text'}},
                      'required': ['text'], 'additionalProperties': False}, 'strict': True},
    {'name': 'fetch', 'description': "GET a page under /for-agents/ (proof points, recommendations, the entry page). "
                                     "Give the path, e.g. /for-agents/recommendations/",
     'input_schema': {'type': 'object', 'properties': {'path': {'type': 'string', 'description': 'path starting with /for-agents/'}},
                      'required': ['path'], 'additionalProperties': False}, 'strict': True},
]


# --- the spec file --------------------------------------------------------------

def read_spec(path=FIT_QUESTIONS):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def section(text, number):
    """The body of `## <number>.` up to the next `## ` heading."""
    m = re.search(r'^## %s\.\s.*?$' % re.escape(str(number)), text, re.M)
    if not m:
        return ''
    rest = text[m.end():]
    n = re.search(r'^## ', rest, re.M)
    return rest[:n.start()].strip() if n else rest.strip()


def type_guidance(text, type_id):
    """The `### T<n>.` subsection of section 1 for one type."""
    m = re.search(r'^### %s\.\s.*?$' % re.escape(type_id), text, re.M)
    if not m:
        return ''
    rest = text[m.end():]
    n = re.search(r'^##', rest, re.M)
    return rest[:n.start()].strip() if n else rest.strip()


def facet_ids(cell):
    """Section ids (or prefixes) in an `expected facets` cell. 'brief rows' becomes
    the marker BRIEF; prose like 'LEO stories' keeps its id prefix; 'none yet' is nothing."""
    out = []
    for part in cell.split(','):
        part = part.strip()
        if not part or part == 'none yet':
            continue
        if part == 'brief rows':
            out.append('BRIEF')
            continue
        m = re.search(r'\b([A-Z][A-Z0-9]+(?:\.[A-Z0-9]+)*)\b', part)
        if m:
            out.append(m.group(1))
    return out


def load_cases(path=FIT_QUESTIONS):
    cases = []
    for t in ah.parse_tables(read_spec(path)):
        if t['header'][:6] != ['id', 'type', 'message', 'context', 'expected facets', 'watch']:
            continue
        for r in t['rows']:
            if not re.match(r'^F\d+$', r['id']):
                continue
            raw = r['context'].strip()
            ctx, attach, thread = None, None, None
            if raw.startswith('"') and raw.endswith('"'):
                ctx = raw[1:-1]
            elif raw in ATTACHMENTS:
                attach = ATTACHMENTS[raw]
            elif raw in THREADS:
                thread = THREADS[raw]
            elif not raw.startswith(COLD):
                raise ValueError(f"{r['id']}: cannot read context {raw!r}")
            cases.append({'id': r['id'], 'type': r['type'], 'message': r['message'], 'context': ctx,
                          'attachment': attach, 'thread': thread, 'context_raw': raw,
                          'expected': facet_ids(r['expected facets']), 'expected_raw': r['expected facets'],
                          'watch': r['watch']})
    return cases


# --- Claude ---------------------------------------------------------------------

def load_key():
    """ANTHROPIC_API_KEY from the environment, else from .env at the repo root
    (where every script keeps its keys). Returned, never printed."""
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, '.env'))
    except ImportError:
        pass
    return os.environ.get('ANTHROPIC_API_KEY', '')


class Claude:
    """Messages API via the anthropic SDK when installed, else urllib. Every
    response is a plain dict: content (list of blocks), stop_reason, usage."""

    def __init__(self, key):
        if not key:
            raise RuntimeError('ANTHROPIC_API_KEY is not set (environment or .env)')
        self._key = key
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=key)
        except ImportError:
            self._client = None
        self.calls = 0
        self.usage = {'input_tokens': 0, 'output_tokens': 0}

    def create(self, model, system, messages, max_tokens, tools=None, tool_choice=None):
        body = {'model': model, 'max_tokens': max_tokens, 'system': system, 'messages': messages}
        if tools:
            body['tools'] = tools
        if tool_choice:
            body['tool_choice'] = tool_choice
        self.calls += 1
        if self._client is not None:
            data = self._client.messages.create(**body).to_dict()
        else:
            req = urllib.request.Request(API_URL, data=json.dumps(body).encode('utf-8'), method='POST', headers={
                'x-api-key': self._key, 'anthropic-version': API_VERSION, 'content-type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=ah.TIMEOUT) as res:
                    data = json.loads(res.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                raise RuntimeError(f'Claude API {e.code}: {e.read().decode("utf-8", "replace")[:300]}') from None
        for k in self.usage:
            self.usage[k] += int((data.get('usage') or {}).get(k) or 0)
        return data


def text_of(content):
    return '\n'.join(b.get('text', '') for b in content if b.get('type') == 'text').strip()


# --- the visiting assistant -----------------------------------------------------

def person_turn(case):
    """The user turn: thread context, then an attachment, then the message.
    Also returns what the transcript may record (counts for attached text)."""
    parts, recorded = [], {}
    if case['thread']:
        parts.append(case['thread'])
    if case['context']:
        parts.append(f"Context from the person: {case['context']}")
    if case['attachment']:
        with open(case['attachment'], encoding='utf-8') as fh:
            jd = fh.read()
        parts.append('The person pasted this job description:\n\n' + jd)
        recorded['attachment'] = {'file': os.path.basename(case['attachment']), 'chars': len(jd), 'lines': len(jd.splitlines())}
    parts.append(f"The person's message: {case['message']}")
    return '\n\n'.join(parts), recorded


def run_tool(name, inp, client):
    """Execute one assistant tool against the base URL. Returns (record, result text)."""
    if name == 'ask':
        q = str(inp.get('q', ''))
        status, text = client.call('ask', 'GET', '/ask?q=' + urllib.parse.quote(q))
        rec = {'tool': 'ask', 'q': q}
    elif name == 'brief':
        body = str(inp.get('text', ''))
        status, text = client.call('brief', 'POST', '/ask/brief', body, 'text/plain')
        rec = {'tool': 'brief', 'chars': len(body), 'lines': len(body.splitlines())}   # visitor text: counts only
    elif name == 'fetch':
        path = str(inp.get('path', ''))
        if not path.startswith('/for-agents/'):
            return {'tool': 'fetch', 'path': path, 'status': None, 'error': 'path must start with /for-agents/'}, \
                'error: path must start with /for-agents/'
        status, text = client.call('fetch', 'GET', path)
        rec = {'tool': 'fetch', 'path': path}
    else:
        return {'tool': name, 'status': None, 'error': 'unknown tool'}, f'error: unknown tool {name}'
    rec['status'] = status
    rec['sections'] = sections_in(ah.as_json(text))
    rec['result'] = text
    if len(text) > TOOL_RESULT_CAP:
        text = text[:TOOL_RESULT_CAP] + f'\n[truncated at {TOOL_RESULT_CAP} characters]'
    return rec, text


def sections_in(data):
    """Every section id on an /ask or /ask/brief response: top level, matches, rows, also, adjacent."""
    seen = []
    if not isinstance(data, dict):
        return seen
    seen.append(data.get('section'))
    for key in ('matches', 'rows'):
        for row in data.get(key) or []:
            if not isinstance(row, dict):
                continue
            seen.append(row.get('section'))
            seen += [a.get('section') for a in (row.get('also') or []) if isinstance(a, dict)]
            if isinstance(row.get('adjacent'), dict):
                seen.append(row['adjacent'].get('section'))
    return list(dict.fromkeys(s for s in seen if isinstance(s, str) and s))


def run_assistant(case, entry, claude, site):
    """The exchange: up to MAX_ROUNDS tool rounds, then one answer with tools off."""
    system = entry + ASSISTANT_SUFFIX
    user, recorded = person_turn(case)
    messages = [{'role': 'user', 'content': user}]
    transcript = {'id': case['id'], 'type': case['type'], 'message': case['message'],
                  'context': 'cold' if not (case['context'] or case['thread'] or case['attachment']) else 'given',
                  'context_chars': len(case['context'] or case['thread'] or ''), **recorded,
                  'assistant_model': ASSISTANT_MODEL, 'rounds': [], 'final_answer': '', 'stop_reason': None}
    final = None
    for n in range(MAX_ROUNDS + 1):
        last = n == MAX_ROUNDS
        res = claude.create(ASSISTANT_MODEL, system, messages, MAX_OUTPUT_TOKENS,
                            tools=None if last else TOOLS, tool_choice={'type': 'none'} if last else None)
        content = res.get('content') or []
        messages.append({'role': 'assistant', 'content': content})
        uses = [b for b in content if b.get('type') == 'tool_use']
        rnd = {'n': n + 1, 'text': text_of(content), 'calls': []}
        transcript['rounds'].append(rnd)
        if res.get('stop_reason') != 'tool_use' or not uses:
            final = res
            break
        results = []
        for u in uses:
            inp = u.get('input') if isinstance(u.get('input'), dict) else {}
            rec, text = run_tool(u.get('name'), inp, site)
            rnd['calls'].append(rec)
            results.append({'type': 'tool_result', 'tool_use_id': u.get('id'), 'content': text})
        messages.append({'role': 'user', 'content': results})
    transcript['final_answer'] = text_of((final or {}).get('content') or [])
    transcript['stop_reason'] = (final or {}).get('stop_reason')
    return transcript


# --- the judge and the mechanical checks ----------------------------------------

JUDGE_SCHEMA = ('Return strict JSON and nothing else: {"C1":0|1,"C2":0|1,"C3":0|1,"C4":0|1,"C5":0|1,"C6":0|1,'
                '"notes":{"C1":"...","C2":"...","C3":"...","C4":"...","C5":"...","C6":"...","summary":"one line"}}')


def judge_prompt(spec, case, transcript):
    rubric = section(spec, 2)
    guidance = type_guidance(spec, case['type'])
    calls = []
    for rnd in transcript['rounds']:
        for c in rnd['calls']:
            what = c.get('q') or c.get('path') or f"brief of {c.get('lines')} lines"
            calls.append(f"- round {rnd['n']}: {c['tool']}({what!r}) -> status {c.get('status')}, sections {', '.join(c.get('sections') or []) or 'none'}")
    row = (f"id {case['id']}, type {case['type']}\nmessage: {case['message']}\ncontext: {case['context_raw']}\n"
           f"expected facets: {case['expected_raw']}\nwatch: {case['watch']}")
    user = (f"## The case row\n\n{row}\n\n## What the type calls for\n\n{guidance}\n\n"
            f"## Tool calls the assistant made\n\n{chr(10).join(calls) or '(none)'}\n\n"
            f"## The assistant's final answer\n\n{transcript['final_answer'] or '(empty)'}\n\n"
            f"Score the final answer on the six checks. {JUDGE_SCHEMA}")
    system = ('You judge a visiting assistant\'s answer about Tom\'s fit for a team, company or role, using this rubric. '
              'Each check is 0 or 1. Be strict: an unsourced claim fails C3, an all-positive answer fails C4, '
              'any score, rank or superlative fails C5.\n\n' + rubric)
    return system, user


def parse_judge(text):
    m = re.search(r'\{.*\}', text or '', re.S)
    if not m:
        raise ValueError('judge returned no JSON')
    data = json.loads(m.group(0))
    out = {c: 1 if int(data.get(c, 0)) else 0 for c in CHECKS}
    notes = data.get('notes') if isinstance(data.get('notes'), dict) else {}
    out['notes'] = {k: str(v) for k, v in notes.items()}
    return out


def run_judge(spec, case, transcript, claude):
    system, user = judge_prompt(spec, case, transcript)
    res = claude.create(JUDGE_MODEL, system, [{'role': 'user', 'content': user}], JUDGE_MAX_TOKENS)
    return parse_judge(text_of(res.get('content') or []))


def verdict_hits(answer, ranking):
    """C5 mechanically: guard.js ranking patterns plus the rubric's phrases over the final answer."""
    hits = []
    for p in list(ranking) + RUBRIC_VERDICT:
        m = re.search(p, answer or '', re.I)
        if m:
            hits.append(m.group(0))
    return hits


def facet_overlap(expected, transcript):
    """C2 mechanically: (pass, seen sections). BRIEF passes on any brief call; an
    expected id matches a seen section equal to it or under it (OPBEAT matches OPBEAT.R1.GROWTH)."""
    seen, briefed = [], False
    for rnd in transcript['rounds']:
        for c in rnd['calls']:
            seen += c.get('sections') or []
            briefed = briefed or c.get('tool') == 'brief'
    seen = list(dict.fromkeys(seen))
    if not expected:
        return True, seen
    for e in expected:
        if e == 'BRIEF' and briefed:
            return True, seen
        if any(s == e or s.startswith(e + '.') for s in seen):
            return True, seen
    return False, seen


def score(case, transcript, judge, ranking):
    hits = verdict_hits(transcript['final_answer'], ranking)
    c2_mech, seen = facet_overlap(case['expected'], transcript)
    checks = dict((c, judge[c]) for c in CHECKS)
    checks['C2'] = 1 if c2_mech else 0
    checks['C5'] = 0 if hits else judge['C5']
    total = sum(checks.values())
    passed = total >= PASS_AT and all(checks[c] for c in MANDATORY)
    note = judge['notes'].get('summary', '')
    if hits:
        note = f"C5 mechanical: {', '.join(repr(h) for h in hits)}. " + note
    if not c2_mech:
        note = f"C2 mechanical: expected {', '.join(case['expected'])}, saw {', '.join(seen) or 'nothing'}. " + note
    return {'id': case['id'], 'type': case['type'], 'message': case.get('message', ''), 'checks': checks, 'total': total,
            'result': 'pass' if passed else 'fail',
            'note': note, 'judge': judge, 'c2_mechanical': c2_mech, 'c5_hits': hits, 'sections_seen': seen,
            'final_answer': transcript['final_answer']}


# --- stub replay ------------------------------------------------------------------

def load_stub(stub_dir, case_id):
    path = os.path.join(stub_dir, f'{case_id}.json')
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    if 'transcript' not in data or 'judge' not in data:
        raise ValueError(f'{path}: needs transcript and judge')
    judge = data['judge']
    judge = {c: 1 if judge.get(c) else 0 for c in CHECKS} | {'notes': dict(judge.get('notes') or {})}
    return data['transcript'], judge


# --- run file ---------------------------------------------------------------------

def render(date, base, mode, guard_src, results, skipped, calls, usage):
    run = [r for r in results]
    n, passed = len(run), sum(r['result'] == 'pass' for r in run)
    pct = 100 * passed // n if n else 0
    c4 = sum(r['checks']['C4'] for r in run)
    c5 = sum(r['checks']['C5'] for r in run)
    L = [f'# Fit judge run {date}', '', RUN_MARKER, '',
         f'- date: {date}', f'- base: {base}', f'- mode: {mode}', f'- guard constants: {guard_src}',
         f'- models: assistant {ASSISTANT_MODEL}, judge {JUDGE_MODEL}',
         f'- Claude calls: {calls}' + (f" ({usage['input_tokens']} input tokens, {usage['output_tokens']} output)" if mode == 'live' else ''),
         '', '## Totals', '',
         f'- cases: {passed}/{n} passed ({pct}%), set {"passes" if n and pct >= SET_PASS_PCT else "fails"} at {SET_PASS_PCT}%',
         f'- C4 honesty: {c4}/{n}; C5 no verdict: {c5}/{n} (both must be {n}/{n})',
         f'- rule: a case passes at {PASS_AT} of 6 with C4 and C5 mandatory; C2 and C5 are mechanical, the judge is recorded beside them']
    if skipped:
        L.append(f"- skipped (no stub): {', '.join(skipped)}")
    L += ['', '## Cases', '', '| id | type | message | C1 | C2 | C3 | C4 | C5 | C6 | result | note |', '|---|---|---|---|---|---|---|---|---|---|---|']
    for r in run:
        c = r['checks']
        L.append(f"| {r['id']} | {r['type']} | {ah._cell(r['message'])} | {c['C1']} | {c['C2']} | {c['C3']} | {c['C4']} | {c['C5']} | {c['C6']} | {r['result']} | {ah._cell(r['note'])} |")
    L += ['', '## Judge beside the mechanical checks', '', '| id | judge C2 | mechanical C2 | sections seen | judge C5 | mechanical C5 |', '|---|---|---|---|---|---|']
    for r in run:
        L.append(f"| {r['id']} | {r['judge']['C2']} | {1 if r['c2_mechanical'] else 0} | {ah._cell(', '.join(r['sections_seen']) or 'none')} | "
                 f"{r['judge']['C5']} | {'fail: ' + ah._cell(', '.join(r['c5_hits'])) if r['c5_hits'] else 'clean'} |")
    L += ['', '## Final answers (spot-check)', '', '<details>', '<summary>The 16 answers as the person would have read them</summary>', '']
    for r in run:
        L += [f"### {r['id']} ({r['type']}): {r['result']}", '', r['final_answer'] or '(empty)', '']
    L += ['</details>', '']
    return '\n'.join(L)


def estimate_calls(n_cases):
    """Upper bound: (claude calls, site calls). Each case: MAX_ROUNDS tool rounds plus the
    answer, one judge call; up to MAX_ROUNDS site calls (each ask or brief is a Voyage embedding)."""
    return n_cases * (MAX_ROUNDS + 1) + n_cases, n_cases * MAX_ROUNDS


# --- main -------------------------------------------------------------------------

def is_production(base):
    host = (urllib.parse.urlparse(base).hostname or '').lower()
    return host in PRODUCTION_HOSTS or host.endswith('.takenbyninjas.com')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--base', help='deployed site for a live (paid) run: staging or localhost, never production')
    ap.add_argument('--case', action='append', default=[], help='run one case id (repeatable), e.g. F01')
    ap.add_argument('--yes-paid', action='store_true', help='confirm the paid calls of a live run')
    ap.add_argument('--write', action='store_true', help='write runs/<date>.md and runs/<date>/<id>.json')
    ap.add_argument('--stub', help='directory of <id>.json {transcript, judge}; replays with no network')
    ap.add_argument('--spec', default=FIT_QUESTIONS, help=argparse.SUPPRESS)
    ap.add_argument('--runs-dir', help='where run files live (default: <health>/fit-judge/runs)')
    ap.add_argument('--date', default=datetime.date.today().isoformat(), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    if not a.stub and not a.base:
        ap.error('give --base <url> for a live run, or --stub <dir> for a replay')
    if a.base and is_production(a.base):
        print(f'Refusing: {a.base} is production. This script runs against staging or localhost only.')
        return 2
    runs_dir = a.runs_dir or os.path.join(FIT_JUDGE, 'runs')
    ranking, limit, window_ms, guard_src = ah.read_guard()
    spec = read_spec(a.spec)
    cases = load_cases(a.spec)
    if a.case:
        cases = [c for c in cases if c['id'] in a.case]
        if not cases:
            ap.error(f"no case among {', '.join(a.case)}")

    results, skipped = [], []
    if a.stub:
        mode, base = 'stub', a.base or '(stub)'
        print(f'Stub run from {a.stub}: no network, 0 paid calls.')
        calls, usage = 0, {'input_tokens': 0, 'output_tokens': 0}
        for c in cases:
            got = load_stub(a.stub, c['id'])
            if got is None:
                skipped.append(c['id'])
                continue
            transcript, judge = got
            results.append(score(c, transcript, judge, ranking))
    else:
        mode, base = 'live', a.base.rstrip('/')
        claude_calls, site_calls = estimate_calls(len(cases))
        print(f'Live run against {base}')
        print(f'Paid calls, upper bound: {claude_calls} Claude calls ({len(cases)} assistant runs of up to {MAX_ROUNDS} tool rounds '
              f'plus the answer, {len(cases)} judge calls) and up to {site_calls} site calls (one Voyage embedding each).')
        if not a.yes_paid:
            print('Refusing: this run spends money. Pass --yes-paid to confirm.')
            return 2
        claude = Claude(load_key())
        site = ah.Live(base, limit, window_ms)
        print(f'Pacing site calls: one every {site.gap:.1f}s (guard limit {limit} per {window_ms // 1000}s).')
        status, entry = site.call('entry', 'GET', '/for-agents/start.md')
        if status != 200:
            print(f'Cannot fetch {base}/for-agents/start.md: {status} {entry[:100]}')
            return 1
        for c in cases:
            print(f"{c['id']} {c['type']}: {c['message']}")
            transcript = run_assistant(c, entry, claude, site)
            judge = run_judge(spec, c, transcript, claude)
            r = score(c, transcript, judge, ranking)
            results.append(r)
            print(f"  {r['result']} {r['total']}/6: {r['note'][:120]}")
            if a.write:
                d = os.path.join(runs_dir, a.date)
                os.makedirs(d, exist_ok=True)
                with open(os.path.join(d, f"{c['id']}.json"), 'w', encoding='utf-8') as fh:
                    json.dump({'transcript': transcript, 'judge': judge}, fh, indent=1, ensure_ascii=False)
        calls, usage = claude.calls, claude.usage

    print()
    for r in results:
        print(f"{r['result'].upper():5s} {r['id']} {r['type']} {''.join(str(r['checks'][c]) for c in CHECKS)}: {r['note'][:140]}")
    n, passed = len(results), sum(r['result'] == 'pass' for r in results)
    print(f'\nfit judge: {passed}/{n} passed' + (f' ({100 * passed // n}%, set {"passes" if 100 * passed // n >= SET_PASS_PCT else "fails"} at {SET_PASS_PCT}%)' if n else '')
          + (f"; skipped {', '.join(skipped)}" if skipped else ''))
    if a.write:
        os.makedirs(runs_dir, exist_ok=True)
        out = os.path.join(runs_dir, f'{a.date}.md')
        with open(out, 'w', encoding='utf-8') as fh:
            fh.write(render(a.date, base, mode, guard_src, results, skipped, calls, usage))
        print(f'written: {out}')
    return 0 if n and 100 * passed // n >= SET_PASS_PCT else 1


if __name__ == '__main__':
    sys.exit(main())
