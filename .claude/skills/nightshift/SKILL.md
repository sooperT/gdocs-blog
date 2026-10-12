---
name: nightshift
description: The unattended overnight run for the agent-readable work (docs/agent-readable/prd.md). Checks the shared usage budget, takes work from the night queue in docs/agent-readable/BACKLOG.md, builds it on a night branch, and writes a morning report for Tom. Invoked by the tbn-night-shift scheduled task.
---

# Night shift (takenbyninjas)

Tom is the CEO with a morning check-in. You are the product team. Nobody is awake to answer questions:
never ask, never wait. Decide, state the assumption in the report, move on.
The spec is `docs/agent-readable/prd.md`: its principles (section 4) and guardrails (section 5) are rules, and CLAUDE.md still applies.
This shift is prioritised above the Kitten PM night shift and runs first (D4).

## 0. Hard limits (no exceptions)

Enforced by `.claude/hooks/night-guard.py`. A block message says what to do instead: follow it, never work around it.

1. Never push. Never deploy. Never commit to, check out, or edit files in `main` or Tom's main checkout. The one permitted action there is creating your own worktree (section 2).
2. Never reload the TomBot database (`load_content*.py`), never write to it, never run `publish.py`. Never install packages. Never call a paid API from the shell. Web search and web fetch from inside the session are free and allowed.
3. Never hidden text on any page, never Novo strategy or pricing, never salary or availability in public, never LinkedIn edits, never a personality test (PRD section 5).
4. Every claim on an agent surface is a verbatim line from TomBot content or the CV, with a source tier (PRD W1b). A line you cannot source goes on the human-task list, never on a page.
5. 3-strike rule: three failed attempts at one problem means stop that item, write up what you know, take the next.
6. Never edit anything under `.claude/`, not even in the worktree: it raises a permission prompt and nobody answers it. Any refused or blocked action goes under **Needs your approval** (section 5) and you move on. The hook answers every prompt "no" and logs it to `~/.claude/projects/-Users-tom-Developer-takenbyninjas/memory/night-denied.log`.

## 1. Clock and budget

The ledger is SHARED with Kitten PM: `~/.claude/projects/-Users-tom-Developer-kitten-pm/memory/night-ledger.md`. Same table, same columns; put `tbn:` at the start of the items column so the two shifts can be told apart.

1. Read the local time. The window is 23:00 to 02:45 (the Kitten PM shift runs at 03:15). Outside it, run in DRY RUN mode: one small queue item, 3 points maximum.
2. Read usage with `mcp__ccd_session_mgmt__get_usage` (load it via ToolSearch). Record both weekly figures: all models, and Fable. If the tool is unavailable, DRY RUN and say so.
3. Tonight's cap, for each figure: weekly overnight budget 50 points, shared. Spent so far = the sum of every nightly delta in the ledger (both shifts) since the last weekly reset. Cap = (50 - spent) / nights left, never more than 15. Stop as soon as either figure reaches its cap, either weekly total passes 85%, or the 5-hour window passes 90%.
4. Re-read usage after every finished queue item and before any agent fan-out.
5. Append start and end readings to the ledger with the Edit tool: date, start, end, delta, items done.

## 2. Workspace

1. Base: if the newest `night/*` branch is not merged into local `main`, base on it (stacking). Otherwise base on local `main`.
2. Make your own worktree, never work in `/Users/tom/Developer/takenbyninjas`:
   `git -C /Users/tom/Developer/takenbyninjas worktree add .claude/worktrees/night-YYYY-MM-DD -b night/YYYY-MM-DD <base>`
   Reuse tonight's worktree if the branch exists and is unmerged; suffix (`-2`) if it is already merged. From then on every command starts with `cd` into the worktree, and every file path is absolute.
   Until the worktree exists, each setup command (`date`, `ls`, `git -C … branch --list|--merged|--no-merged`, `log`, `status`, `worktree add|list`) runs on its own: no `;`, `&&`, pipes or redirects, or the guard blocks it.
3. `docs/` is gitignored and so missing from the worktree. Link it: `cd <worktree> && ln -s /Users/tom/Developer/takenbyninjas/docs docs`. TomBot content, the PRD, the backlog, drafts and reports all live there, private and never pushed. Link packages too: `ln -s /Users/tom/Developer/takenbyninjas/node_modules node_modules`.
4. Write the report skeleton first (`docs/agent-readable/reports/YYYY-MM-DD.md`, one line saying the night is in progress). Then the baseline before any change: `python3 generate_homepage.py && python3 generate_archive.py && python3 generate_sitemap.py && git status --short` must show no generated-file drift. If it drifts, the first job is to report that, and build nothing on top of it.
5. Write file content with the Write and Edit tools, not shell heredocs or redirects.

## 3. Pick the work

Take items from the top of `## Night queue` in `docs/agent-readable/BACKLOG.md`, in order. An item is blocked only if it names a decision that has no ruling in the PRD's section 9 or in `docs/agent-readable/decisions.md`. Say why you skip.
Before building, check the item is not already done (`git log --oneline --grep`, the files it names) and that no later ruling contradicts it.
If the queue is empty, take `night-safe` items from `## Active`. If those are gone too, write a proposal and stop.

## 4. Do the work

1. You plan and review. Opus agents (`model: opus`) implement and verify. Each agent gets a self-contained brief, the worktree path as its working directory, one deliverable, and the PRD principles that apply to it.
2. One queue item, one commit, conventional message, ending `Co-Authored-By: Claude Code <noreply@anthropic.com>`. Generated files are committed with their generator in the same commit. Reports and drafts in `docs/` are not committed (gitignored): they are on disk for the morning.
3. Gates per item: every generator runs clean; `git diff` on generated files shows only the intended change; every HTML page parses with `python3 -m html.parser`-level validation (a script in `scripts/` once item 2 lands) and every internal link resolves; JSON-LD parses as JSON; `llms.txt` and `sitemap.xml` reference only pages that exist. For any page a human might land on, start `python3 -m http.server 8199` from the worktree, fetch the page with `curl` and check it, then stop the server. There is no headless browser here: visual checks happen in Tom's morning review, so say in the report which pages need a look.
4. Evals (W2): the runner must work with zero paid calls. Claude-side queries use the session's own WebSearch and WebFetch tools; Exa only once Tom has put a key in `.env` (never print it). Record every run under `docs/agent-readable/evals/runs/`.
5. Proceed on assumptions. Record each one for the report.
6. Tick the item off in `docs/agent-readable/BACKLOG.md` and update `docs/agent-readable/STATUS.md` (one page, under 60 lines).

## 5. Morning report

Write `docs/agent-readable/reports/YYYY-MM-DD.md` and give the same text as your final message. Plain words, short sentences, no em dashes. At most one page plus the decisions:

1. **Headline**: what moved on S1 to S4 (the evals delta), or what Tom can now look at that he could not yesterday.
2. **Done**: each item, one line, with its commit hash.
3. **Decide**: decisions waiting on Tom, ids `N<MMDD>-<n>` (never reused), each a short paragraph a reader with no context can answer: the thing in plain words, what you saw with numbers, why a recruiter or an agent would care, what each lettered option changes. Include every assumption you acted on.
4. **Look at this**: pages to open on the night branch (`cd <worktree> && python3 -m http.server 8199`, then the URL), and what to check visually.
5. **Human tasks**: anything only Tom can write or supply, with why a generator could not.
6. **Proposed next**: what should join the queue, in order (section 6).
7. **Needs your approval**: each process fix and each refused or blocked action, including every line of tonight's `night-denied.log`: file, exact text to replace, exact new text, what it cost tonight.
8. **Not done**: anything skipped or abandoned, and why.
9. **Budget**: start, end and delta for both figures, spent this week across both shifts, tomorrow's cap.
10. **Branch**: the night branch and how many commits ahead of main.

## 6. Keep the loop fed

Spend the last part of every night on this, within the cap.

1. **Generate** up to five candidates from, in order: what tonight uncovered; the newest evals run; `/stats` (AI referrers, agent page hits); `/tombot-logs` deflections (questions the content cannot answer are content debt on every surface); the PRD workstreams not yet started.
2. **Shape**: one line of what, one line of why now with its number, the workstream, a size, and what Tom would have to decide. A candidate with no number is a proposal, not a queue item.
3. **File** them under `## Proposed` in the backlog, newest first, fifteen at most.
4. **Promote**: if the queue has fewer than two items left and Tom has not reviewed, promote the top proposal that needs no ruling, and say so.
5. **Tune the process**: one thing that cost time or points tonight, with the fix at the source, under **Needs your approval**. This skill stays under 130 lines.

## 7. When Tom responds

Tom reviews in a normal session with the `/night-review` skill, not here.
