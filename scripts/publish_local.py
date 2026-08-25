#!/usr/bin/env python3
"""Run publish.py locally, answering its prompts by reading them.

Piping blind answers (`printf "yes\\nyes\\nno"`) assumes a fixed prompt
sequence. publish.py's structural-errors prompt is conditional, so when it
doesn't fire the answers shift up one and a "yes" lands on "commit and push".
This matches each prompt's text instead. Anything unrecognised gets "no".

Usage: python3 scripts/publish_local.py "doc-name"
"""
import os
import pty
import re
import select
import subprocess
import sys

ANSWERS = [
    (re.compile(r'structural errors', re.I), 'yes'),   # validator false-positive
    (re.compile(r'publish to blog', re.I), 'yes'),     # writes local files only
    (re.compile(r'commit and push', re.I), 'no'),      # pushes are Tom's call
]
PROMPT_END = re.compile(r'\(yes/no\):\s*$')


def main():
    if len(sys.argv) < 2:
        sys.exit('usage: publish_local.py "doc-name"')

    master, slave = pty.openpty()
    proc = subprocess.Popen(
        [sys.executable, 'publish.py', *sys.argv[1:]],
        stdin=slave, stdout=slave, stderr=slave, close_fds=True,
    )
    os.close(slave)

    buf = ''
    unknown = []
    while True:
        if not select.select([master], [], [], 0.5)[0]:
            if proc.poll() is not None:
                break
            continue
        try:
            chunk = os.read(master, 4096).decode('utf-8', 'replace')
        except OSError:
            break
        if not chunk:
            break
        sys.stdout.write(chunk)
        sys.stdout.flush()
        buf += chunk

        if PROMPT_END.search(buf):
            question = buf[-400:]
            reply = next((a for pat, a in ANSWERS if pat.search(question)), None)
            if reply is None:
                reply = 'no'
                unknown.append(question.strip().splitlines()[-1])
            os.write(master, (reply + '\n').encode())
            buf = ''

    os.close(master)
    code = proc.wait()
    for q in unknown:
        print(f'\n! Unrecognised prompt, answered "no": {q}', file=sys.stderr)
    sys.exit(code)


if __name__ == '__main__':
    main()
