---
name: night-review
description: Show Tom the state of the agent-readable night shift (batches awaiting review, decisions, pages to look at, budget, queue) and apply his verdicts. Use when he asks "what happened last night", "what's the status", "show me the batch", or gives verdicts on night work.
---

# Night review (takenbyninjas)

Tom is the CEO at a check-in. Lead with what needs him. Short and plain. Only things he might answer carry an id. Facts are plain bullets. Options get letters. Read-only until he gives a verdict.

## 1. Gather (read, change nothing)

0. **Stuck run first.** A run still marked running in `list_task_runs` with no report for its date and an idle transcript over 30 minutes is stuck. Transcripts are the JSONL files in `~/.claude/projects/-Users-tom-Developer-takenbyninjas/`. Find the last `tool_use` with no `tool_result`. Then read `~/.claude/projects/-Users-tom-Developer-takenbyninjas/memory/night-denied.log`.
1. **Batches.** `git branch --list 'night/*'`; for each not merged into `main`: commits ahead, date. Reports are on disk, not in git: `docs/agent-readable/reports/<date>.md` in the main checkout (docs/ is gitignored and symlinked into every worktree).
2. **Schedule.** `mcp__scheduled-tasks__list_scheduled_tasks` for `tbn-night-shift` and `kitten-night-shift`: enabled, last run, next run. `list_task_runs` for stalls.
3. **Budget.** `mcp__ccd_session_mgmt__get_usage` plus the shared ledger `~/.claude/projects/-Users-tom-Developer-kitten-pm/memory/night-ledger.md`: spent this week across both shifts against 50, tonight's cap.
4. **Evals.** The newest file in `docs/agent-readable/evals/runs/` and its delta line.
5. **Queue.** `## Night queue` and `## Proposed` in `docs/agent-readable/BACKLOG.md`.

## 2. Present: one screen

1. **Needs you**: count of decisions, pages to look at, human tasks. If zero, say so first.
2. **S1 to S4**: the latest numbers and the change since the last review.
3. **Batches awaiting review**: branch, date, items, commits.
4. **Decide**: every open decision from unreviewed reports, keeping its id (`N1009-1`), a short paragraph each with full context, lettered options, recommendation. New questions raised here get `R<MMDD>-<n>`. Never renumber, never reuse an id.
5. **Look at this**: start the night branch's pages yourself with the preview tools (`cd <worktree> && python3 -m http.server 8199` is the night's port; in review use the `site` launch config pointed at the worktree, or serve the worktree on 8199 and open it) and screenshot them at desktop and mobile widths. Judge the whole page. Show the evidence; never ask Tom to check manually.
6. **Needs your approval**: process fixes and blocked actions from the reports, plus any `night-denied.log` line the report does not cover: file, text to replace, new text.
7. **Human tasks**: the list from the reports, deduplicated.
8. **Up next**: the night queue, then proposals in recommended order.
9. **Budget**: used this week (both shifts), remaining, tonight's cap, next run time.

Offer to open any report or diff in the side pane. Do not paste whole reports. Files on an unmerged night branch live in `.claude/worktrees/`: send them with `SendUserFile` or `show_pane`, never as a markdown link.

## 3. Apply his verdicts

Tom answers by number and letter. Then:

1. **Accept a batch or item**: merge the night branch into local `main` (or cherry-pick). Never push without his explicit yes: a push is a Netlify build. Once fully merged, `git worktree remove` and `git branch -d`.
2. **Reject an item**: `git revert` its commit on the night branch.
3. **Rulings**: add each to `docs/agent-readable/decisions.md` at the top, dated, with the id. Close or update the matching backlog entries.
4. **Tune the queue**: re-rank, promote, park or kill exactly as he says. If he changes how the night shift works, edit `.claude/skills/nightshift/SKILL.md` and tell him what changed.
5. **Needs your approval**: on his yes, apply the exact change on `main` so the next run starts with it. Ask before clearing `night-denied.log`.
6. **Schedule changes**: `update_scheduled_task`.
7. After a merge, re-run the generators and check `git diff` on generated files is empty. Ask before committing, as always. A TomBot content change is only live after `scripts/load_content_v3.py`, which Tom approves separately (it wipes the live DB).

## 4. If something looks wrong

A stuck run, a generator that drifts, a night that overspent its cap, or a branch that touched `main`: say it first, plainly. Pause the schedule if the fault would repeat.
