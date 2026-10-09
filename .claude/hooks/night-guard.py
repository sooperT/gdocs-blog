#!/usr/bin/env python3
"""night-guard.py: enforcement for night shift sessions (takenbyninjas).

Adapted 2026-10-08 from kitten-pm/.claude/hooks/night-guard.py. Differences: repo paths, a shared usage
ledger with Kitten PM, docs/ symlinked into the worktree (gitignored, so reports are not committed),
TomBot DB loads and publish.py and paid APIs on the never list, port 8199, 2.5 hour nights.

The /nightshift skill is guidance. This hook is the enforcement: the limits here hold
whatever the model decides. It does nothing at all in Tom's own sessions.

How a session becomes a "night session": the moment it invokes the nightshift skill
(PreToolUse on the Skill tool). The hook records the session id in a marker file, so
no cooperation from the model is needed. Sub-agents share the session id, so they are
covered too.

Enforced in a night session:
  1. File edits land only in a night worktree, the usage ledger folder, or a temp folder.
  2. Shell commands run inside a night worktree (they must start with `cd <worktree>`),
     apart from a short list of read-only and setup commands.
  3. Never: push, merge, deploy, switch to main/production, act on the main checkout
     with git, install packages, or call the paid image API.
  4. A ceiling on agent launches per night, and no new agents after the time limit.
  5. The session cannot end without a morning report, and it is told if the main
     checkout changed during the run.
  6. Nothing under a `.claude/` directory is changed (skills, hooks, settings), not even
     inside the worktree: those files raise a permission prompt, and a prompt at night
     freezes the run until morning (2026-09-30). Edits and the usual shell write routes
     are blocked; the model writes the change into the report's "Needs your approval".
  7. Any permission prompt that still comes up (PermissionRequest) is answered "deny"
     at once, with a message to record it and carry on, and logged to DENIED_LOG.
     Unanswered prompts that no hook can answer (Notification) are logged there too.
     MCP input requests (Elicitation) are declined and logged the same way.
  8. AskUserQuestion is blocked: nobody is awake to answer.

Exit 0 = allow. Exit 2 = block (stderr goes back to the model).
PermissionRequest cannot block with exit 2 (the docs say it is ignored): it answers
with a JSON decision on stdout instead.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time

REPO = "/Users/tom/Developer/takenbyninjas"
WT_ROOT = REPO + "/.claude/worktrees"
WT_PREFIX = WT_ROOT + "/night-"
MARKERS = WT_ROOT + "/.night-sessions"
LEDGER_DIR = os.path.expanduser("~/.claude/projects/-Users-tom-Developer-takenbyninjas/memory")
# The usage ledger is SHARED with the Kitten PM night shift (D4: one weekly budget, this shift runs first).
SHARED_LEDGER_DIR = os.path.expanduser("~/.claude/projects/-Users-tom-Developer-kitten-pm/memory")
# docs/ is gitignored in this repo, so night worktrees symlink it from the main checkout. Reports, the
# backlog and drafts live there (private, never pushed) and may be written directly.
DOCS_WORK = REPO + "/docs/agent-readable/"
WRITE_OK = (WT_PREFIX, LEDGER_DIR + "/", SHARED_LEDGER_DIR + "/", DOCS_WORK, "/private/tmp/", "/tmp/", "/private/var/folders/", "/var/folders/")
DENIED_LOG = LEDGER_DIR + "/night-denied.log"   # written by this hook only; read by both skills

APPROVAL = ("Nobody is awake to approve this. Do not retry it and do not work around it. "
            "Write the exact change (file, text to replace, new text, what it cost tonight) under "
            "'Needs your approval' in the morning report, then carry on with the next item.")

MAX_AGENTS = 20          # per night. This shift shares the budget with Kitten PM (D4).
MAX_HOURS = 3.5          # 23:00 start, done by about 02:30; the Kitten PM shift runs at 03:15.
NIGHT_PORT = 8199        # the night's own http.server. Stopped when the session ends. Never 8000 or 8888 (Tom's).

# Commands allowed from outside a worktree: setup and read-only looks at the repo.
SETUP_OK = re.compile(
    r"^\s*(git\s+-C\s+" + re.escape(REPO) + r"\s+(worktree\s+(add|list)|branch\s+--list|log|rev-parse|status|show)\b"
    r"|date\b|pwd\b|ls\b|cat\s+(" + re.escape(LEDGER_DIR) + "|" + re.escape(SHARED_LEDGER_DIR) + "|" + re.escape(DOCS_WORK) + r"))"
)
# Never allowed in a night session, wherever it runs.
CHAIN = r"(^|&&|\|\||;|\|)\s*"
NEVER = [
    (CHAIN + r"git\s+(-C\s+\S+\s+)?push\b", "pushing (a push deploys and costs credits)"),
    (CHAIN + r"git\s+(-C\s+\S+\s+)?merge\b", "merging (Tom merges at review)"),
    (CHAIN + r"git\s+(-C\s+\S+\s+)?(checkout|switch)\s+(-\S+\s+)*(main|production)\b", "switching to main or production"),
    (CHAIN + r"git\s+-C\s+" + re.escape(REPO) + r"\s+(commit|add|checkout|switch|reset|rebase|restore|stash|clean|cherry-pick|revert|rm|mv)\b",
     "changing the main checkout with git"),
    (CHAIN + r"(sudo\s+)?(npm|pnpm|yarn)\s+(install|i|ci|add|publish)\b", "installing or publishing packages"),
    (CHAIN + r"(npx\s+)?netlify\s+(deploy|env|sites)", "deploying"),
    (r"load_content[A-Za-z0-9_]*\.py", "reloading the LIVE TomBot database (it wipes and reinserts every chunk)"),
    (r"NILEDB_URL.*\b(DELETE|TRUNCATE|DROP|INSERT|UPDATE|ALTER)\b|\b(DELETE|TRUNCATE|DROP|INSERT|UPDATE|ALTER)\b.*NILEDB_URL", "writing to the LIVE TomBot database"),
    (r"\bpublish\.py\b", "publish.py (it needs Google OAuth and can push; use scripts/publish_local.py or the generators)"),
    (r"(api\.openai\.com|api\.perplexity\.ai|api\.x\.ai|api\.exa\.ai|api\.voyageai\.com|api\.anthropic\.com)", "a paid API from the shell (D1: paid engines only with keys Tom approved, from his session)"),
    (r"(-p|--port)[ =]?(8000|8888)\b|http\.server\s+(8000|8888)\b", "using a port that belongs to Tom's sessions (use 8199)"),
]


def marker_path(sid):
    return os.path.join(MARKERS, re.sub(r"[^A-Za-z0-9_.-]", "_", sid) + ".json")


def load_marker(sid):
    try:
        with open(marker_path(sid)) as f:
            return json.load(f)
    except Exception:
        return None


def save_marker(sid, m):
    os.makedirs(MARKERS, exist_ok=True)
    with open(marker_path(sid), "w") as f:
        json.dump(m, f)


def git_main(*args):
    try:
        return subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def block(msg):
    sys.stderr.write("NIGHT GUARD: " + msg + "\n")
    sys.exit(2)


def notify(text):
    try:
        subprocess.run(["osascript", "-e",
                        'display notification "%s" with title "takenbyninjas night shift"' % text.replace('"', "'")],
                       timeout=5)
    except Exception:
        pass


def inside(path, prefixes):
    p = os.path.realpath(os.path.expanduser(path)) if path else ""
    real = [os.path.realpath(x.rstrip("/")) + ("/" if x.endswith("/") else "") for x in prefixes]
    return any(p.startswith(r) or (p + "/").startswith(r) for r in real) or any(path.startswith(x) for x in prefixes)


# --- Rule 6: Claude's own config (.claude/) is read-only at night. ---
# A night worktree lives at <repo>/.claude/worktrees/night-*/, so the worktree prefix is cut off
# first; what is left must not contain a .claude segment. The ledger folder is the one exception.
WT_CUT = re.compile(r"^(.*/)?\.claude/worktrees/night-[^/]+(/|$)")
WT_ITSELF = re.compile(r"^(.*/)?\.claude/worktrees(/night-[^/]+)?/?$")   # creating the worktree
CONFIG_SEG = re.compile(r"(^|/)\.claude(/|$)")


def is_config_path(path):
    if not path or re.search(r"\s", path):
        return False
    forms = {path, os.path.expanduser(path.replace("$HOME", "~", 1))}
    forms |= {os.path.normpath(f) for f in list(forms)}
    forms |= {os.path.realpath(f) for f in list(forms) if f.startswith("/")}
    ledger = os.path.realpath(LEDGER_DIR)
    if any(f == ledger or f.startswith(ledger + "/") or f.startswith(LEDGER_DIR + "/") for f in forms):
        return False
    if any(WT_ITSELF.match(f) for f in forms):
        return False
    return any(CONFIG_SEG.search(WT_CUT.sub("", f, count=1)) for f in forms)


def block_config(path):
    block("%s is under .claude/ (skills, hooks, settings). Night shifts never change those files: "
          "they raise a permission prompt and nobody is awake to answer it. %s" % (path, APPROVAL))


ENV_OR_WRAP = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*=.*|sudo|env|command|nohup|time)$")
WRITE_ANY = {"tee", "touch", "rm", "rmdir", "unlink", "mkdir", "chmod", "chown", "truncate", "mv"}
WRITE_LAST = {"cp", "rsync", "install", "ln", "ditto"}
INTERP = {"python", "python3", "node", "ruby", "perl", "bash", "sh", "zsh"}
REDIRECT = {">", ">>", ">|", "&>", "&>>"}
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(\n|$)", re.S)


def config_write_in_bash(cmd):
    """The .claude path a shell command would change, or None. Reads are fine."""
    body = HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0] + "\n", cmd)   # a heredoc body is text, not a target
    try:
        lex = shlex.shlex(body.replace("\n", " ; "), posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        toks = body.split()
    segs, cur = [], []
    for t in toks:
        if t and set(t) <= set(";&|()"):
            segs.append(cur)
            cur = []
        else:
            cur.append(t)
    segs.append(cur)
    for seg in segs:
        for i, t in enumerate(seg):                      # redirects, whatever the command
            if t in REDIRECT and i + 1 < len(seg) and is_config_path(seg[i + 1]):
                return seg[i + 1]
        words = [w for w in seg if w not in REDIRECT]
        while words and ENV_OR_WRAP.match(words[0]):
            words = words[1:]
        if not words:
            continue
        verb = os.path.basename(words[0])
        args = [w for w in words[1:] if not w.startswith("-")]
        flags = [w for w in words[1:] if w.startswith("-")]
        targets = []
        if verb in WRITE_ANY:
            targets = args
        elif verb in WRITE_LAST:
            targets = args[-1:]
        elif verb == "dd":
            targets = [a[3:] for a in args if a.startswith("of=")]
        elif verb in ("sed", "gsed") and any(f == "-i" or f.startswith("--in-place") or re.match(r"^-[a-zA-Z]*i", f) for f in flags):
            targets = args
        elif verb == "git" and any(a in ("checkout", "restore", "rm", "mv", "apply", "add", "commit") for a in args[:3]):
            targets = args
        if verb == "perl" and any(re.match(r"^-[a-zA-Z]*i", f) for f in flags):
            targets = args
        elif verb in INTERP and any(f in ("-c", "-e", "-pe", "-ne") for f in flags):
            # Inline code is one token: look for paths inside it.
            targets = [m.group(0) for w in words[1:] for m in re.finditer(r"[\w~$./-]*\.claude/[\w./-]*", w)]
        for a in targets:
            if is_config_path(a):
                return a
    return None


def log_denied(kind, data):
    tool = data.get("tool_name") or data.get("notification_type") or ""
    ti = data.get("tool_input") or {}
    what = ti.get("command") or ti.get("file_path") or ti.get("notebook_path") or ti.get("url") \
        or data.get("message") or json.dumps(ti)[:200]
    line = "%s\t%s\t%s\t%s\t%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), (data.get("session_id") or "")[:8],
                                     kind, tool, re.sub(r"\s+", " ", str(what))[:200])
    try:
        os.makedirs(LEDGER_DIR, exist_ok=True)
        with open(DENIED_LOG, "a") as f:
            f.write(line)
    except Exception:
        pass


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    sid = data.get("session_id") or ""
    event = data.get("hook_event_name") or ""
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    if not sid:
        sys.exit(0)

    # --- Registration: the session invokes the nightshift skill. ---
    if event == "PreToolUse" and tool == "Skill" and (ti.get("skill") or "").split(":")[-1] == "nightshift":
        if load_marker(sid) is None:
            save_marker(sid, {
                "started": time.time(),
                "agents": 0,
                "main_head": git_main("rev-parse", "HEAD"),
                "main_branch": git_main("rev-parse", "--abbrev-ref", "HEAD"),
                "main_status": git_main("status", "--porcelain"),
            })
        sys.exit(0)

    m = load_marker(sid)
    if m is None:
        sys.exit(0)  # not a night session: this hook has no opinion

    hours = (time.time() - m.get("started", time.time())) / 3600.0

    # --- Rule 7: a permission prompt at night is answered "no" at once, never left waiting. ---
    if event == "PermissionRequest":
        log_denied("auto-denied", data)
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {
            "behavior": "deny", "interrupt": False,
            "message": "NIGHT GUARD: this needed a permission prompt. " + APPROVAL}}}))
        sys.exit(0)
    if event == "Elicitation":   # an MCP server asking for input: decline, never wait
        log_denied("declined-elicitation", dict(data, tool_name=data.get("mcp_server_name") or "mcp"))
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "Elicitation", "action": "decline"}}))
        sys.exit(0)
    if event == "Notification":
        # No hook can answer these (for example a sandbox network prompt). Log it so the review sees it.
        log_denied("UNANSWERED-" + (data.get("notification_type") or "prompt"), data)
        notify("Night shift is waiting on a prompt. See night-denied.log")
        sys.exit(0)

    if event == "PreToolUse":
        if tool == "AskUserQuestion":
            block("nobody is awake to answer questions. Decide, state the assumption in the morning report, move on.")
        if tool in ("Edit", "Write", "NotebookEdit"):
            path = ti.get("file_path") or ti.get("notebook_path") or ""
            if is_config_path(path):
                block_config(path)
            if not inside(path, WRITE_OK):
                block("file edits must land in tonight's worktree under %s-<date>/ . You tried: %s . "
                      "Tom's main checkout is off limits. Use the same path inside the worktree." % (WT_PREFIX, path))
            sys.exit(0)

        if tool == "Bash":
            cmd = ti.get("command") or ""
            for pat, what in NEVER:
                if re.search(pat, cmd, re.M):
                    block("%s is never allowed on a night shift. Write it up in the morning report instead." % what)
            target = config_write_in_bash(cmd)
            if target:
                block_config(target)
            cwd = data.get("cwd") or ""
            starts_in_wt = re.match(r"^\s*cd\s+[\"']?" + re.escape(WT_PREFIX), cmd) is not None
            if not (starts_in_wt or cwd.startswith(WT_PREFIX) or SETUP_OK.match(cmd)):
                block("shell commands must run inside tonight's worktree. Start the command with "
                      "`cd %s<date> && ...`. Create the worktree first if it does not exist "
                      "(`git -C %s worktree add ...`)." % (WT_PREFIX, REPO))
            sys.exit(0)

        if tool in ("Agent", "Task"):
            if hours > MAX_HOURS:
                block("the night is over (%.1f hours). Start no new agents. Write the morning report and stop." % hours)
            m["agents"] = m.get("agents", 0) + 1
            if m["agents"] > MAX_AGENTS:
                block("agent ceiling reached (%d tonight). Write the morning report and stop." % MAX_AGENTS)
            save_marker(sid, m)
            sys.exit(0)

        if tool == "Workflow":
            block("workflows are not used on a night shift (they can fan out past the budget). Use single agents.")
        sys.exit(0)

    if event == "Stop":
        today = time.strftime("%Y-%m-%d")
        have_report = False
        if os.path.isdir(WT_ROOT):
            for d in os.listdir(WT_ROOT):
                if d.startswith("night-"):
                    pass
        rep = os.path.join(DOCS_WORK, "reports")
        if os.path.isdir(rep) and any(f.startswith(today) for f in os.listdir(rep)):
            have_report = True
        changed = []
        if git_main("rev-parse", "HEAD") != m.get("main_head"):
            changed.append("main has new commits")
        if git_main("rev-parse", "--abbrev-ref", "HEAD") != m.get("main_branch"):
            changed.append("the main checkout is on a different branch")
        if git_main("status", "--porcelain") != m.get("main_status"):
            changed.append("files in the main checkout changed")
        if changed and not m.get("warned"):
            m["warned"] = True
            save_marker(sid, m)
            notify("Main checkout changed during the night: " + "; ".join(changed))
        if not have_report and not data.get("stop_hook_active"):
            extra = (" Also state in the report that during this run: " + "; ".join(changed) + ".") if changed else ""
            block("no morning report found for %s. Write docs/agent-readable/reports/%s.md (docs/ is the symlinked, "
                  "gitignored folder) and give the same text as your final message.%s" % (today, today, extra))
        # Never leave the night's server running: it would hold a port into Tom's day.
        try:
            pids = subprocess.run(["lsof", "-ti", "tcp:%d" % NIGHT_PORT], capture_output=True, text=True, timeout=5).stdout.split()
            for pid in pids:
                os.kill(int(pid), 15)
        except Exception:
            pass
        notify("Night shift finished. Ask for /night-review.")
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
