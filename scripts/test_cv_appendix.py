#!/usr/bin/env python3
"""Checks the CV appendix for agents (scripts/cv_appendix.py) against Tom's
rulings R1012-22, R1012-23 and R1012-24: written by his agent for recruiters'
agents and the standard ATS, so no first-person prose, no section ids, no
/about/ link; a fact answers what was asked and nothing else; the fit is plain
text, the job description's words in full with the evidence beside each.

Small synthetic /ask/brief responses are rendered through build() against the
real for-agents/proof-points.json; stories and facts are picked from that file
by shape, so the checks do not depend on which rows or ask patterns it holds.
No network: post_brief is never called.

    python3 scripts/test_cv_appendix.py
"""
import copy
import datetime
import glob
import json
import os
import re
import sys
import urllib.parse

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)   # build() reads the generator's page list from the working directory
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import cv_appendix as c  # noqa: E402

BRIEFS = os.path.join(ROOT, 'docs', 'agent-readable', 'evals', 'health', 'briefs-2026-10-12')
with open(os.path.join(ROOT, c.ROWS_FILE), encoding='utf-8') as f:
    ROWS = json.load(f)

passed = failed = warned = 0


def check(name, cond, detail=''):
    global passed, failed
    if cond:
        passed += 1
        print(f'ok   {name}')
    else:
        failed += 1
        print(f'FAIL {name}' + (f': {detail}' if detail else ''))


def warn(name, detail):
    global warned
    warned += 1
    print(f'WARNING {name}: {detail}')


# Rules 1 to 3 (R1012-22): never weaken.
FIRST_PERSON = re.compile(r"\bI\b|(?i:\b(?:we|my|our)\b)")
SECTION_ID = re.compile(r'\b[A-Z][A-Z0-9]+(?:\.[A-Z0-9]+)+\b')   # NOVO.R1, META.EDUCATION, PP.3
CROSS_REF = re.compile(r'(?i)\b(?:see|as|same as|same story as|story|row|requirement|ref|id)[ :#]*\d+\b|\bibid\b|\bsee above\b')
URL = r'https://takenbyninjas\.com/\S+'


def first_person(text):
    return FIRST_PERSON.findall(text)


def lines_of(out):
    return out.split('\n')


def fit_section(out):
    """The lines between the Fit heading and the next heading."""
    ls = lines_of(out)
    start = next(i for i, ln in enumerate(ls) if ln.startswith('### Fit:'))
    stop = next(i for i in range(start + 1, len(ls)) if ls[i].startswith('### '))
    return ls[start:stop]


def fit_pairs(out):
    """[(n, requirement line text, fit, evidence text)] from the fit section."""
    ls = fit_section(out)
    pairs = []
    for i, ln in enumerate(ls):
        m = re.match(r'^(\d+)\. (.*)$', ln)
        if m:
            e = re.match(r'^Evidence \(([a-z ]+)\): (.*)$', ls[i + 1])
            pairs.append((int(m.group(1)), m.group(2), e.group(1) if e else None, e.group(2) if e else None))
    return pairs


def text_of(r, key):
    return c.cell(r, key)


# --- Stories and facts picked from the real file by shape -------------------

by_result, by_section = c.star_index(ROWS)
full = [r for r in ROWS['proof_points']
        if all(text_of(r, k) for k in ('result', 'action', 'role', 'product', 'year')) and r.get('page')
        and by_result.get(c._norm(text_of(r, 'result'))) is r]
stories = []
for r in full:   # four stories, a different product each
    if text_of(r, 'product') not in [text_of(x, 'product') for x in stories]:
        stories.append(r)
A, B, C, D = stories[:4]
UNIQUE = next(((sec, r) for sec, r in by_section.items() if r in full and r not in (A, B, C, D)), None)
NO_PAGE = next((r for r in ROWS['proof_points'] if text_of(r, 'result') and not r.get('page')
                and by_result.get(c._norm(text_of(r, 'result'))) is r), None)

FACTS = ROWS['screening_facts']
STATED = next(f for f in FACTS if f['value'] and not f.get('qualifiers') and not f.get('per_send') and not f.get('on_request')
              and f['type'] not in ('name', 'last_role') + c.OMIT_ON_SEND)
UNSTATED = next(f for f in FACTS if not f['value'])


def pp_row(requirement, story, met='met', also=None):
    return {'requirement': requirement, 'met': met, 'kind': 'proof-point', 'section': text_of(story, 'result') and story['result']['section'],
            'evidence': text_of(story, 'result'), 'page': story.get('page'), 'adjacent': None, 'fact_type': None, 'also': also,
            'evidence_star': {k: text_of(story, k) for k in ('situation', 'task', 'action', 'result')}}


def fact_row(requirement, fact_type):
    return {'requirement': requirement, 'met': 'fact', 'kind': 'fact', 'section': 'META.EDUCATION', 'evidence': 'x', 'page': None,
            'evidence_star': None, 'adjacent': None, 'fact_type': fact_type, 'also': None}


def gap_row(requirement, near=None):
    adjacent = near and {'evidence': text_of(near, 'result'), 'section': near['result']['section'], 'kind': 'proof-point',
                         'product': text_of(near, 'product'), 'page': near.get('page')}
    return {'requirement': requirement, 'met': 'not met', 'kind': None, 'section': None, 'evidence': None, 'page': None,
            'evidence_star': None, 'adjacent': adjacent, 'fact_type': None, 'also': None}


def section_row(requirement, section):
    return {'requirement': requirement, 'met': 'partial', 'kind': 'section', 'section': section, 'evidence': 'I did a thing, and we shipped our plan.',
            'page': None, 'evidence_star': None, 'adjacent': None, 'fact_type': None, 'also': None}


# Requirements in invented words, so no screening ask pattern claims them.
LONG = ('Steer a portfolio of lighthouse refurbishment programmes from the earliest sketch to the final handover, keeping each one inside the '
        'agreed scope, the agreed budget and the agreed calendar, while reporting progress to the harbour board every single quarter without fail')
REQ = {
    'pp': LONG,
    'fact': 'Zebra clearance for the Atlantis site',
    'unstated': 'Quokka paperwork within one fortnight',
    'pointer': 'Cartography of submarine volcanoes',
    'near': 'Falconry for airport runways',
    'gap': 'Glassblowing at furnace scale',
    'repeat': 'Lighthouse refurbishment in a harbour setting',
    'also': 'Beekeeping across several orchards',
    'unique': 'Bookbinding for a private library',
}
rows = [
    pp_row(REQ['pp'], A),
    fact_row(REQ['fact'], STATED['type']),
    fact_row(REQ['unstated'], UNSTATED['type']),
    section_row(REQ['pointer'], 'SYNTH.NOSUCH'),
    gap_row(REQ['near'], C),
    gap_row(REQ['gap']),
    pp_row(REQ['repeat'], A),
    pp_row(REQ['also'], B, also=[{'evidence': text_of(D, 'result'), 'product': text_of(D, 'product')}]),
]
if UNIQUE:
    rows.append(section_row(REQ['unique'], UNIQUE[0]))
BRIEF = {'rows': rows}
EXPERIENCE = [k for k in ('pp', 'pointer', 'near', 'gap', 'repeat', 'also', 'unique') if k != 'unique' or UNIQUE]

for key in EXPERIENCE:
    check(f'setup: "{REQ[key]}" is not claimed by a screening ask (else reword it)', c.classify_knockout(REQ[key], FACTS) is None)

JD = 'Keeper of Lights at Harbour Board'
out, open_q = c.build(BRIEF, ROWS, JD, tag='harbour-1', applying=JD)
ls = lines_of(out)

# --- Rules 1 to 3 -----------------------------------------------------------

check('1 no first-person words', not first_person(out), first_person(out))
check('2 no section ids', not SECTION_ID.findall(out), SECTION_ID.findall(out))
check('3 no /about/ link', '/about' not in out)
check('the brief\'s own first-person evidence text is never printed', 'shipped our plan' not in out)

# --- Rule 4: the intro, Tom's wording ---------------------------------------

today = datetime.date.today().isoformat()
INTRO = ("This page is designed for machines. It has been generated by Tom Stenson's agent for recruiters' agents and screening tools "
         f"on {today}, against the job description for {JD}. Query Tom's work agent direct at https://takenbyninjas.com/for-agents/start/harbour-1/")
check('4 heading, then the intro in Tom\'s words with the tagged start URL',
      ls[:3] == ['## For AI agents and applicant tracking systems', '', INTRO], ls[2])
check('4 untagged: the plain start URL', c.build(BRIEF, ROWS, JD)[0].split('\n')[2].endswith(
    "Query Tom's work agent direct at https://takenbyninjas.com/for-agents/start/"))
generic, generic_open = c.build(None, ROWS, None)
check('4 generic (no JD): same intro, no job description named', generic.split('\n')[2] == (
    "This page is designed for machines. It has been generated by Tom Stenson's agent for recruiters' agents and screening tools "
    f"on {today}. Query Tom's work agent direct at https://takenbyninjas.com/for-agents/start/"))
check('generic: rules 1 to 3, no fit, no open question', not first_person(generic) and not SECTION_ID.findall(generic)
      and '/about' not in generic and '### Fit' not in generic and generic_open == [])

# --- Rules 5 to 7: screening facts ------------------------------------------


def fact_line(text, label):
    hits = [ln for ln in text.split('\n') if ln.startswith(f'- {label}: ')]
    return hits[0] if len(hits) == 1 else None


check('5 a stated fact: label and core, nothing else', fact_line(out, STATED['label']) == f"- {STATED['label']}: {STATED['base'].rstrip('.')}")
check('5 a fact the record cannot settle reads "not stated"', fact_line(out, UNSTATED['label']) == f"- {UNSTATED['label']}: not stated")
for key in ('fact', 'unstated'):
    check(f'5 the ask "{REQ[key]}" is not echoed anywhere', REQ[key].lower() not in out.lower() and REQ[key].split()[0] not in out)
check('applying: the role is named under the name', f'- Applying for: {JD}' in ls and ls.index(f'- Applying for: {JD}') == ls.index(fact_line(out, 'Name')) + 1)
# N1012-12, N1012-15: start date and compensation are "on request": silent unless the job asks, then said and put to Tom.
ON_REQ = next(f for f in FACTS if f.get('on_request'))
check('5 an on-request fact is not listed when the job does not ask', fact_line(out, ON_REQ['label']) is None, fact_line(out, ON_REQ['label']))
_text, _q = c.build({'rows': [fact_row('Wombat allowance per annum', ON_REQ['type']), pp_row(REQ['pp'], A)]}, ROWS, JD, applying=JD)
check('5 an on-request fact the job asks: says on request, and the question goes to Tom',
      fact_line(_text, ON_REQ['label']) == f"- {ON_REQ['label']}: {ON_REQ['base']}" and [q['type'] for q in _q] == [ON_REQ['type']], (fact_line(_text, ON_REQ['label']), _q))
_text, _q = c.build({'rows': [fact_row('Wombat allowance per annum', ON_REQ['type']), pp_row(REQ['pp'], A)]}, ROWS, JD, applying=JD, answers={ON_REQ['type']: 'agreed by phone'})
check('5 Tom\'s answer to an on-request fact stands alone', fact_line(_text, ON_REQ['label']) == f"- {ON_REQ['label']}: agreed by phone", fact_line(_text, ON_REQ['label']))
_two = dict(fact_row('Wombat allowance and Zebra clearance', ON_REQ['type']), fact_types=[ON_REQ['type'], STATED['type']])
_text, _q = c.build({'rows': [_two, pp_row(REQ['pp'], A)]}, ROWS, JD, applying=JD)
check('5 a line that asks two facts gets both (N1012-15)', fact_line(_text, ON_REQ['label']) and fact_line(_text, STATED['label']), _text[:400])
check('7 the unanswered question comes back in open_q',
      open_q == [{'type': UNSTATED['type'], 'asked': REQ['unstated'], 'record': None}], open_q)

# A register of our own for the qualifier rules: the real ask patterns may change.
SYNTH = copy.deepcopy(ROWS)
SYNTH['screening_facts'] = [
    {'type': 'name', 'label': 'Name', 'base': 'Tom Stenson', 'qualifiers': [], 'value': 'Tom Stenson', 'per_send': False, 'asks': []},
    {'type': 'location', 'label': 'Location', 'base': 'Copenhagen, Denmark', 'per_send': True, 'asks': [],
     'qualifiers': [{'text': 'Open to onsite roles in Copenhagen', 'ask': r'\boffice\b|\bon-?site\b'}, {'text': 'remote roles across the EU', 'ask': r'\bremote\b'}],
     'value': 'Copenhagen, Denmark; Open to onsite roles in Copenhagen; remote roles across the EU'},
    {'type': 'start_date', 'label': 'Start date', 'base': None, 'qualifiers': [], 'value': None, 'per_send': False, 'asks': []},
]
RECORD = SYNTH['screening_facts'][1]['value']


def facts_for(ask, fact_type='location', applying=JD, answers=None):
    text, q = c.build({'rows': [fact_row(ask, fact_type), pp_row(REQ['pp'], A)]}, SYNTH, JD, applying=applying, answers=answers)
    return text, q


ASK_OFFICE, ASK_REMOTE, ASK_NEITHER = 'Three days a week in the Lisbon office', 'This is a fully REMOTE position', 'Location: Lisbon, Portugal'
for applying in (JD, None):   # with or without --role and --company
    how = 'on a send' if applying else 'JD without role/company'
    text, q = facts_for(ASK_OFFICE, applying=applying)
    check(f'5 {how}: core plus the qualifier the ask mentions', fact_line(text, 'Location') == '- Location: Copenhagen, Denmark; Open to onsite roles in Copenhagen',
          fact_line(text, 'Location'))
    check(f'5 {how}: the ask is not echoed', 'Lisbon' not in text and 'Three days' not in text)
    check(f'7 {how}: a per-send question is open until Tom answers', q == [{'type': 'location', 'asked': ASK_OFFICE, 'record': RECORD}], q)
    text, _ = facts_for(ASK_REMOTE, applying=applying)
    check(f'5 {how}: the other qualifier for the other ask, case-insensitive', fact_line(text, 'Location') == '- Location: Copenhagen, Denmark; remote roles across the EU',
          fact_line(text, 'Location'))
    text, q = facts_for(ASK_NEITHER, applying=applying)
    check(f'5 {how}: an ask that names no qualifier gets the core only', fact_line(text, 'Location') == '- Location: Copenhagen, Denmark' and len(q) == 1,
          fact_line(text, 'Location'))
    text, q = facts_for(ASK_OFFICE, applying=applying, answers={'location': 'relocating to Lisbon: yes'})
    check(f'6 {how}: Tom\'s answer replaces the qualifiers', fact_line(text, 'Location') == '- Location: Copenhagen, Denmark; relocating to Lisbon: yes',
          fact_line(text, 'Location'))
    check(f'6 {how}: and clears the open question', q == [])
    text, q = facts_for('Notice period of one month at most', 'start_date', applying=applying)
    check(f'7 {how}: a fact with no record is "not stated" and open', fact_line(text, 'Start date') == '- Start date: not stated'
          and q == [{'type': 'start_date', 'asked': 'Notice period of one month at most', 'record': None}], (fact_line(text, 'Start date'), q))
    text, q = facts_for('Notice period of one month at most', 'start_date', applying=applying, answers={'start_date': 'one month from offer'})
    check(f'6 {how}: Tom\'s answer stands alone where the record has nothing', fact_line(text, 'Start date') == '- Start date: one month from offer' and q == [],
          fact_line(text, 'Start date'))

text, q = c.build({'rows': [pp_row(REQ['pp'], A)]}, SYNTH, JD, applying=JD)
check('5 on a send, a fact the JD does not ask about: core only, nothing open', fact_line(text, 'Location') == '- Location: Copenhagen, Denmark' and q == [])
check('5 on a send, an unasked fact with no record is left out', fact_line(text, 'Start date') is None)
text, q = c.build(None, SYNTH, None)
check('generic (no JD): the whole standing fact', fact_line(text, 'Location') == f'- Location: {RECORD}' and q == [])

# The real register: whatever its qualifier patterns are, only the ones the ask matches are printed.
REAL_Q = next((f for f in FACTS if f.get('qualifiers') and f.get('base')), None)
if REAL_Q:
    ask = 'Hybrid: two days a week on-site, otherwise remote'
    text, _ = c.build({'rows': [fact_row(ask, REAL_Q['type'])]}, ROWS, JD, applying=JD)
    want = [REAL_Q['base']] + [x['text'] for x in REAL_Q['qualifiers'] if re.search(x['ask'], ask, re.I)]
    check('5 real register: core plus only the matching qualifiers', fact_line(text, REAL_Q['label']) == f"- {REAL_Q['label']}: " + '; '.join(want).rstrip('.'),
          fact_line(text, REAL_Q['label']))
    check('5 real register: the ask is not echoed', 'two days a week' not in text)
    text, q = c.build({'rows': [fact_row(ask, REAL_Q['type'])]}, ROWS, JD, applying=JD, answers={REAL_Q['type']: 'settled with the recruiter'})
    check('6 real register: the answer replaces the qualifiers and nothing is open',
          fact_line(text, REAL_Q['label']) == f"- {REAL_Q['label']}: {REAL_Q['base'].rstrip('.')}; settled with the recruiter" and q == [], fact_line(text, REAL_Q['label']))

# --- Rule 8: facts are not fit rows; the fit renumbers ----------------------

pairs = fit_pairs(out)
fit = fit_section(out)
check('8 fit rows renumber without gaps', [p[0] for p in pairs] == list(range(1, len(EXPERIENCE) + 1)), [p[0] for p in pairs])
check('8 fit rows are the experience requirements, in order', [p[1] for p in pairs] == [c.end(REQ[k]) for k in EXPERIENCE])
check('8 the heading counts experience requirements only',
      fit[0] == f"### Fit: {JD} ({len(EXPERIENCE)} experience requirements, in the job description's words)", fit[0])
check('8 fact requirements are nowhere in the fit', not any(REQ[k].split()[0] in ln for k in ('fact', 'unstated') for ln in fit))

# --- Rule 9: plain text for the standard ATS (R1012-24) ---------------------

got = {k: pairs[i] for i, k in enumerate(EXPERIENCE)}
check('9 the requirement is the job description\'s full words, untruncated', got['pp'][1] == LONG + '.' and len(LONG) > 200)
check('9 every requirement line is followed by its Evidence line, then a blank',
      all(p[2] in ('met', 'partial', 'not met') and p[3] for p in pairs)
      and all(fit[i + 2] == '' for i, ln in enumerate(fit) if re.match(r'^\d+\. ', ln)))
check('9 the fit label is the brief\'s verdict', [got[k][2] for k in ('pp', 'pointer', 'near', 'gap', 'repeat', 'also')] == ['met', 'partial', 'not met', 'not met', 'met', 'met'])


def who(r):
    return f"{text_of(r, 'role')}, {text_of(r, 'product')}, {c.year_span([text_of(r, 'year')])}."


check('9 a story: result, action, role, product, years, link, as plain sentences',
      got['pp'][3] == f"{c.end(text_of(A, 'result'))} {c.end(text_of(A, 'action'))} {who(A)} {A['page']}", got['pp'][3])
# Tom's ruling in the R1012-24 commit, not "in full": a story already told is restated short, never referenced.
check('9 a repeated story is restated on its own line (result, role, product, years, link), not referenced',
      got['repeat'][3] == f"{c.end(text_of(A, 'result'))} {who(A)} {A['page']}", got['repeat'][3])
check('9 a second example is written out after "Also:" (R1012-23 e)',
      got['also'][3] == f"{c.end(text_of(B, 'result'))} {c.end(text_of(B, 'action'))} {who(B)} Also: {c.end(text_of(D, 'result'))} {who(D)} {B['page']}", got['also'][3])
check('9 a section with no summarised story: says so, with a link', re.fullmatch(rf'On record, no summarised story yet\. {URL}', got['pointer'][3]), got['pointer'][3])
check('9 a gap with nearest evidence: named as not a match, with who, when and link',
      got['near'][3] == f"Nearest, not a match: {c.end(text_of(C, 'result'))} {who(C)} {C['page']}", got['near'][3])
check('9 a gap with nothing near: not on record', got['gap'][3] == 'Not on record.')
check('9 only the gap with nothing near is listed to ask Tom', f"Not on record, ask Tom: {REQ['gap']}." in fit and not any(REQ['near'] in ln for ln in fit if ln.startswith('Not on record')))
if UNIQUE:
    U = UNIQUE[1]
    check('9 a section one story summarises is told as that story',
          got['unique'][3] == f"{c.end(text_of(U, 'result'))} {c.end(text_of(U, 'action'))} {who(U)} {U['page']}", got['unique'][3])
check('9 every evidence line but "Not on record." ends with a link', all(re.search(rf' {URL}$', p[3]) for p in pairs if p[3] != 'Not on record.'))
check('9 no markdown tables', not any(ln.lstrip().startswith('|') for ln in ls) and '|' not in '\n'.join(fit))
check('9 no JSON or arrays in the fit', not any(ln.lstrip()[:1] in ('[', '{') for ln in fit) and not re.search(r'\["|\{"|":|\],', out))
check('9 no ids or cross-references in the fit', not any(CROSS_REF.search(ln) for ln in fit if not re.match(r'^\d+\. ', ln) and not ln.startswith('### ')),
      [ln for ln in fit if CROSS_REF.search(ln)])
check('9 no STAR labels: sentences, not fields', not re.search(r'\b(Situation|Task|Action|Result):', out))

if NO_PAGE:   # a story with no page of its own still ends with a link
    text, _ = c.build({'rows': [pp_row(REQ['pp'], NO_PAGE), gap_row(REQ['near'], NO_PAGE)]}, ROWS, JD, applying=JD)
    check('9 a story with no page of its own still carries a link (told and nearest)', all(re.search(rf' {URL}$', p[3]) for p in fit_pairs(text)),
          [p[3] for p in fit_pairs(text)])

# --- Rule 10: skills are markdown links -------------------------------------


def skills_line(text):
    t = text.split('\n')
    return t[t.index('### Skills (each links its stories)') + 2]


LINK = r'\[[^\]\[]+\]\(https://takenbyninjas\.com/for-agents/skills/[a-z0-9-]+/\)'
for name, text in (('on a send', out), ('generic', generic)):
    check(f'10 {name}: every skill is a markdown link to its skill page', re.fullmatch(rf'{LINK}(, {LINK})*\.', skills_line(text)), skills_line(text)[:120])
used = {s for r in ROWS['proof_points'] if text_of(r, 'product') in {text_of(x, 'product') for x in (A, B) + ((UNIQUE[1],) if UNIQUE else ())} for s in r.get('skills', [])}
check('10 on a send: only the skills of the stories this fit tells', set(re.findall(r'\[([^\]]+)\]\(', skills_line(out))) == used)

# --- The eight saved responses: rules 1 to 3 and no tables ------------------

saved = sorted(glob.glob(os.path.join(BRIEFS, '*.json')))
check('saved responses found', len(saved) == 8, len(saved))
for path in saved:
    name = os.path.basename(path).removesuffix('.json')
    with open(path, encoding='utf-8') as f:
        resp = json.load(f)
    text, _ = c.build(resp, ROWS, 'Role at Company', tag='smoke', applying='Role at Company')
    # The job description's own words (the requirement lines, and the gap list that
    # quotes them) are the fit's structure (R1012-23 b): a "we" or "our" there is
    # the employer's, reported as a WARNING. Everything else is the agent's text.
    jd_lines = {f"{c.end(' '.join(str(r['requirement']).split()))}" for r in resp['rows']}
    ours, theirs = [], []
    for ln in text.split('\n'):
        quoted = re.sub(r'^\d+\. ', '', ln) in jd_lines or ln.startswith('Not on record, ask Tom: ')
        if first_person(ln):
            (theirs if quoted else ours).append(ln)
    check(f'smoke {name}: 1 no first-person words in the agent\'s own text', not ours, ours[:2])
    if theirs:
        warn(f'smoke {name}: 1 first-person words in the job description\'s own words',
             f"{len(theirs)} line(s), e.g. \"{c.one_line(theirs[0], 110)}\" {first_person(theirs[0])}")
    check(f'smoke {name}: 2 no section ids', not SECTION_ID.findall(text), SECTION_ID.findall(text))
    check(f'smoke {name}: 3 no /about/ link', '/about' not in text)
    check(f'smoke {name}: no line starts with |', not any(ln.lstrip().startswith('|') for ln in text.split('\n')))
    numbers = [p[0] for p in fit_pairs(text)]
    check(f'smoke {name}: fit rows renumber without gaps, facts left out',
          numbers == list(range(1, len(numbers) + 1)) and len(numbers) == sum(1 for r in c.fit_rows(resp, ROWS)[0] if r['fit'] != 'fact'))
    # Decoded, the contact link's question reads "How can I contact Tom?": the asker's "I", inside a URL.
    hidden = first_person(urllib.parse.unquote(text)) if not (ours or theirs) else []
    if hidden and name == os.path.basename(saved[0]).removesuffix('.json'):
        warn('smoke: a first-person word inside a URL-encoded link', f'{hidden} in the Notes contact link (the asker\'s question to /ask)')

print(f'\n{passed} passed, {failed} failed' + (f', {warned} warnings' if warned else ''))
sys.exit(1 if failed else 0)
