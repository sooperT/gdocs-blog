#!/usr/bin/env python3
"""Zero-network test for scripts/grade_calibration.py.

    python3 scripts/test_grade_calibration.py

What it proves:
1. parse: the line-aware parser sees the same ads and ids as
   agent_health.load_calibration, and keeps each row's line number.
2. render: a page from the stub run holds one block per row with the ad line
   verbatim, the expected value, a returned row (from the stub) and exactly
   one tick line; `?` rows come first.
3. apply round-trip on a temp copy: three ticks (met, not met, fact/not stated
   with a note) change exactly those three table lines, agent_health still
   loads the result, and every other line is byte-identical.
4. unticked rows untouched: a page with no ticks, or two ticks on one row,
   changes nothing.
5. No socket is opened by any of it.
"""
import os
import re
import shutil
import socket
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agent_health  # noqa: E402
import grade_calibration as gc  # noqa: E402


def no_socket(*a, **k):
    raise AssertionError('network call attempted')


socket.socket = no_socket
socket.create_connection = no_socket

checks = []


def ok(name, cond, detail=''):
    checks.append((name, bool(cond)))
    print(('pass  ' if cond else 'FAIL  ') + name + (f'  ({detail})' if detail and not cond else ''))
    if not cond:
        sys.exit(1)


# 1. parse ---------------------------------------------------------------------
with open(gc.CALIBRATION, encoding='utf-8') as fh:
    cal_text = fh.read()
cal_lines = cal_text.splitlines()
ads = gc.parse_calibration(cal_text)
ref = agent_health.load_calibration(gc.HEALTH)
ok('parse: same ads as agent_health', [a['slug'] for a in ads] == [r['slug'] for r in ref])
ok('parse: same ids per ad', all([x['id'] for x in a['rows']] == [x['id'] for x in r['rows']] for a, r in zip(ads, ref)))
ok('parse: line numbers point at the row', all(cal_lines[x['line']].startswith(f"| {x['id']} |") for a in ads for x in a['rows']))
ok('parse: met values are known', all(x['met'].split(' or ')[0].split(':')[0] in agent_health.MET_VALUES for a in ads for x in a['rows']))
n_rows = sum(len(a['rows']) for a in ads)
n_low = sum('?' in x['conf'] for a in ads for x in a['rows'])
ok('parse: row count matches the Summary total', f'| **total** | {n_rows} |' in cal_text, str(n_rows))
ok('parse: low-confidence count matches the Summary total', cal_text.rstrip().count(f'| {n_low} |\n') >= 1 or f'| {n_low} |' in cal_text, str(n_low))

# 2. render --------------------------------------------------------------------
stub = os.path.join(gc.HEALTH, 'stubs', 'run1.json')
run_pages = sorted(f for f in os.listdir(gc.RUNS) if f.endswith('.md') and not f.endswith('-brief.md'))
sources = [stub] + ([os.path.join(gc.RUNS, run_pages[-1])] if run_pages else [])
grades, returned, used = gc.load_run_sources(sources)
ok('render: stub holds rows for every ad', all(a['slug'] in returned for a in ads))
ad = next(a for a in ads if a['slug'] == 'heyra-deployment-strategist')
page = gc.render_ad(ad, grades, returned, used)
blocks = re.findall(r'^### ([A-Z]{2}\d+)', page, re.M)
ok('render: one block per row', blocks and sorted(blocks) == sorted(x['id'] for x in ad['rows']))
low_ids = [x['id'] for x in ad['rows'] if '?' in x['conf']]
ok('render: ? rows come first', blocks[:len(low_ids)] == low_ids)
ok('render: one tick line per row', page.count(gc.GRADE_LINE) == len(ad['rows']))
ok('render: ad lines verbatim', all(f"- ad: {gc.one_line(x['requirement'])}" in page for x in ad['rows']))
ok('render: expected value shown', all(f"- expected today: `{x['met']}`" in page for x in ad['rows']))
ok('render: stub rows paired and labelled', page.count('- returned (run1.json): `') >= len(ad['rows']) - 2)
ok('render: application lines are marked heuristic', 'a heuristic, not a judgement' in page)
ghost = next(a for a in ads if a['slug'] == 'ghost-application-form-questions')
gpage = gc.render_ad(ghost, grades, returned, used)
ok('render: ghost page uses both application files', 'closest lines' in gpage and gpage.count('### GH') == 4)
no_run = gc.render_ad(ad, {}, {}, [])
ok('render: no run data is said, not hidden', '- returned: no run data for this ad' in no_run)

# 3. apply round-trip on a temp copy -----------------------------------------
tmp = tempfile.mkdtemp(prefix='grade-cal-')
try:
    health = os.path.join(tmp, 'health')
    os.makedirs(health)
    shutil.copy(gc.CALIBRATION, os.path.join(health, 'calibration.md'))
    os.symlink(os.path.join(gc.HEALTH, 'jds'), os.path.join(health, 'jds'))
    cal_copy = os.path.join(health, 'calibration.md')
    out = os.path.join(tmp, 'grading')
    gc.main(['--ad', 'heyra-deployment-strategist', '--run', stub, '--calibration', cal_copy, '--out', out])
    gpath = os.path.join(out, 'heyra-deployment-strategist.md')
    ok('apply: page written', os.path.exists(gpath))
    with open(gpath, encoding='utf-8') as fh:
        gtext = fh.read()

    def tick(text, rid, box, note=''):
        head, sep, tail = text.partition(f'### {rid}')
        assert sep, rid
        tail = tail.replace(f'[ ] {box}', f'[x] {box}', 1)
        if note:
            tail = tail.replace('- note: ', f'- note: {note}', 1)
        return head + sep + tail

    gtext2 = tick(gtext, 'HE01', 'partial')
    gtext2 = tick(gtext2, 'HE13', 'not met')
    gtext2 = tick(gtext2, 'HE16', 'fact/not stated', 'not stated:employment_type, Tom said so')
    gtext2 = tick(gtext2, 'HE15', 'fact/not stated')                      # keeps fact:location
    gtext2 = tick(gtext2, 'HE02', 'met')                                   # already met: ok tick only
    with open(gpath, 'w', encoding='utf-8') as fh:
        fh.write(gtext2)
    before = open(cal_copy, encoding='utf-8').read()
    gc.main(['--apply', gpath, '--calibration', cal_copy])
    after = open(cal_copy, encoding='utf-8').read()
    b, a = before.splitlines(keepends=True), after.splitlines(keepends=True)
    ok('apply: line count unchanged', len(a) == len(b))
    changed = [i for i in range(len(b)) if a[i] != b[i]]
    ok('apply: exactly five lines changed', len(changed) == 5, str(changed))
    ok('apply: only the ticked rows changed', sorted(re.match(r'^\| (\w+) ', a[i]).group(1) for i in changed) == ['HE01', 'HE02', 'HE13', 'HE15', 'HE16'])
    rows = {r['id']: r for ad2 in gc.parse_calibration(after) for r in ad2['rows']}
    ok('apply: HE01 met -> partial, section kept', rows['HE01']['met'] == 'partial' and rows['HE01']['section'] == 'NOVO.R2, NOVO.R1, NOVO.R2.GENAI' and rows['HE01']['ok'] == '[x]')
    ok('apply: HE13 -> not met, section -', rows['HE13']['met'] == 'not met' and rows['HE13']['section'] == '-')
    ok('apply: HE16 takes the typed value from the note', rows['HE16']['met'] == 'not stated:employment_type')
    ok('apply: HE15 keeps fact:location', rows['HE15']['met'] == 'fact:location' and rows['HE15']['ok'] == '[x]')
    ok('apply: HE02 ok ticked, value kept', rows['HE02']['met'] == 'met' and rows['HE02']['ok'] == '[x]')
    def keep(line, with_section):
        c = gc.split_cells_raw(line)
        return [c[0], c[2], c[3]] + ([c[5]] if with_section else []) + c[6:]
    ok('apply: other cells of a changed line are byte-identical',
       all(keep(a[i], '| HE13 |' not in a[i]) == keep(b[i], '| HE13 |' not in b[i]) for i in changed))
    ok('apply: agent_health still loads the result', len(agent_health.load_calibration(health)) == len(ref))
    ok('apply: counts and summary untouched', after.count('Counts:') == before.count('Counts:') and '| **total** |' in after)

    # 4. unticked rows untouched -------------------------------------------------
    with open(gpath, 'w', encoding='utf-8') as fh:
        fh.write(gtext)
    gc.main(['--apply', gpath, '--calibration', cal_copy])
    ok('untouched: no ticks changes nothing', open(cal_copy, encoding='utf-8').read() == after)
    two = tick(tick(gtext, 'HE03', 'met'), 'HE03', 'partial')
    with open(gpath, 'w', encoding='utf-8') as fh:
        fh.write(two)
    new_text, changes, skipped = gc.apply_grading(after, two)
    ok('untouched: two ticks on one row is skipped', new_text == after and not changes and skipped == [('HE03', '2 boxes ticked')])
    new_text, changes, skipped = gc.apply_grading(after, tick(gtext, 'ZZ99', 'met') if '### ZZ99' in gtext else gtext)
    ok('untouched: unknown ids are ignored', new_text == after)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f'{sum(c for _, c in checks)}/{len(checks)} checks passed, 0 network calls.')
