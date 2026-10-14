#!/usr/bin/env python3
"""Tone check (docs/agent-readable/evals/tone-rubric.md, rules 1, 2, 3, 8): patterns over
the STAR rows (tightened text, as the appendix prints it) and the content file's
direct answers. Read-only; prints findings for Tom. Exit 1 when any rule-2 or rule-3
pattern hits (those are never acceptable), 0 otherwise."""
import re
import sys

sys.path.insert(0, '.')
import generate_agent_page as g  # noqa: E402

RULES = {
    '1 faults stated outright': [
        r"\bnobody (knew|had authority|understood)\b", r"\bnever collaborated\b", r"\bin over their heads\b",
        r"\bthought they knew best\b", r"\bsaw \w+ as a chore\b", r"\btheatre\b", r"\binsular\b", r"\bdysfunctional\b",
        r"\bincompetent\b", r"\bbroken culture\b", r"\bno one (knew|cared|had)\b", r"\bclueless\b", r"\btoxic\b",
    ],
    '2 bad form': [
        r"execs? (weren't|were not) ready", r"\bdid(n't| not) want the mistake\b", r"\bblame\b", r"\bfired\b",
        r"\bcover(ed|ing)? up\b", r"\bpolitics\b", r"\bincompeten",
    ],
    '3 self-aggrandising': [
        r"\bthought partner to\b", r"\bvisionary\b", r"\brockstar\b", r"\bworld[- ]class\b", r"\bexceptional\b",
        r"\bstrong fit\b", r"\bhighly relevant\b", r"\bbest[- ]in[- ]class\b", r"\bguru\b", r"\bninja\b(?! ?s\.com)",
    ],
    '8 first person in agent text': [r"\bI\b", r"(?i)\b(?:we|my|our)\b"],
}
compiled = {k: [re.compile(p) for p in v] for k, v in RULES.items()}
findings = []

def scan(where, text, rules=RULES):
    for rule in rules:
        for rx in compiled[rule]:
            m = rx.search(text)
            if m:
                findings.append((rule, where, m.group(0), text[:140]))
                break

for n, row in enumerate(g.PROOF_POINTS, 1):
    for k in ('situation', 'task', 'action', 'result', 'desc'):
        v = row.get(k)
        if not v:
            continue
        shown = g.TIGHT.get(n, {}).get(k, v[0])
        scan(f"row {n:02d} {row['product'][0]} {k}", shown)

# Direct answers in the content: rules 1 to 3 only (first person is the chat voice there)
sec, da = None, False
for line in open(g.CONTENT_FILE, encoding='utf-8'):
    if line.startswith('## '):
        sec = line[3:].strip(); da = False
    elif line.startswith('**Direct answers:**'):
        da = True
    elif line.startswith('**') or not line.strip():
        da = False
    elif da and line.startswith('- '):
        scan(f"{sec} direct answer", line[2:].strip(), rules=[r for r in RULES if not r.startswith('8')])

hard = [f for f in findings if f[0][0] in '23']
print(f"{len(findings)} findings ({len(hard)} on rules 2 and 3)\n")
for rule, where, hit, text in sorted(findings):
    print(f"[{rule}] {where}: '{hit}' in: {text}")
sys.exit(1 if hard else 0)
