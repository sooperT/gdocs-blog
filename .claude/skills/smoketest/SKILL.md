---
name: smoketest
description: Run the agent-readable paste line cold in each chat agent (Claude, ChatGPT, Copilot, Gemini, Grok) in the built-in browser, follow with a JD, and record where each one stumbles. Use when Tom says "smoke test the agents", "run the paste test", "does the prompt work in X", after any change to the entry file or paste line, or before the LinkedIn About line goes live.
argument-hint: "[claude|chatgpt|copilot|gemini|grok ...] [--jd path]"
allowed-tools: Bash, Read, Write, mcp__Claude_Browser__*
---

# /smoketest — the paste line, cold, in every agent

The only design that is zero-effort, smooth and works across agents is public pages plus one pasted prompt (feedback memory `feedback-zero-user-work`). This skill proves that design holds, agent by agent, the way a curious hiring manager would meet it: paste, read, paste a JD. PRD J1's "done when" is three agents producing a fit table with no human help; this runs the four Tom can reach (Claude, ChatGPT, Copilot, Gemini); Grok is skipped, see the table.

## 1. Setup

1. **Paste line, always live, never from memory.** It changes; the test is the production text:
   ```bash
   curl -s https://takenbyninjas.com/projects/tombot/ | grep -o '<kbd id="tb-paste-text">.*</kbd>' | sed 's/<[^>]*>//g'
   ```
2. **JD.** `.claude/skills/smoketest/jd.txt` (mixed fit: pharma and AI met, line management and banking not). `--jd` overrides. Never a JD from a live application Tom is in; those carry his fit-page links and would skew the run.
3. **Browser.** Built-in browser (`mcp__Claude_Browser__*`), one tab per agent via `preview_start {url}`. Sign-ins are Tom's: check each site with `find "sign in"`; if signed out, ask Tom once with the four URLs in a code block, then run signed out where the site allows chat (ChatGPT, Gemini, Grok do; Copilot and Claude do not). Record the sign-in state per run. Never enter credentials.
4. **Fresh chat every run.** No project, no custom instructions, no earlier chat about Tom in the same tab.

| Agent | New chat URL | Notes |
|---|---|---|
| Claude | https://claude.ai/new | Fetch asks permission on first use; that prompt counts as a speed bump but not a failure |
| ChatGPT | https://chatgpt.com/ | Signed out still browses; check for the "Lockdown" or cache-only fallback |
| Copilot | https://copilot.microsoft.com/ | Bing-grounded only; if Bing has no copy of the page it cannot read it (STATUS 14 Oct). Will not run in the built-in browser: its bot check fails even with Tom's "I am human" ticks and Microsoft drops the session on send (2026-10-21). Copilot runs are Tom's, by hand in his own browser |
| Gemini | https://gemini.google.com/app | Signed out is Flash-Lite, 70–100 s a turn, errors "1096" by turn 3; sign in for a fair run |
| Grok | https://grok.com/ | Skip: Tom has no Grok account and will not open one (2026-10-21). Listed only so the table matches older runs |

## 2. Script, three turns, verbatim

- **Turn 1:** the paste line alone. Expected: the agent fetches the entry page and shows the four-option block from section 0, nothing before it.
- **Turn 2:** `1` then a blank line then the JD text. Expected: a fit table in the JD's own words, met / partial / not met, evidence, section id, source; at least one not met; the static-route disclaimer said once.
- **Turn 3:** `Would he fit a 15-person team in a pharma startup?` Expected: Job 5 from the fit page, ends with the not-a-fit line that applies, no score or adjective.

Before every turn, clear the box and prove it: `triple_click` the textbox, key `cmd+a`, key `Backspace`, then `zoom` on the box and check the placeholder shows. Signed-out Gemini keeps the previous prompt in the box and a click lands mid-text, so typing splices the two messages (2026-10-15, two garbled sends). Type each turn with `computer type`, send with Return, then `computer wait` 20 seconds and `get_page_text`. Agents that fetch may take up to two minutes; wait in 20-second steps until the text stops changing. Screenshot (`scale 0.5`) after each turn into `docs/agent-readable/evals/runs/<date>-smoke/<agent>-<turn>.png` via the tool-result path copied with `cp`.

## 3. What to record

One file, `docs/agent-readable/evals/runs/<date>-smoke.md`, one row per agent per turn:

| agent | signed in | turn | fetched? | what came back | stumble | result |

`stumble` uses this list, so runs compare across dates:
- `permission` — the agent asked the person before fetching (one tap; note how many)
- `refused` — fetch declined (content type, policy, noindex); quote the agent's wording
- `stale` — answered from an old or cached copy (text that is no longer on the page)
- `wrong-page` — read a different page than asked
- `injection` — treated the entry file as a prompt attack
- `no-block` — fetched but did not show the section 0 block
- `built-url` — tried `/ask?q=` on the static route
- `thin` — fit table without evidence, section ids or any not-met row
- `invented` — a fact not on any page
- `slow` — over 90 seconds for a turn
- `sign-in` — the site would not answer signed out
- `platform error` — the agent's own error, retried once
- `none`

Pair `fetched?` with the server, not the agent's claim: `agent_fetches` in the production DB (`scripts/live_report.py --env production --days 1`, or a direct query on `created_at`, `path`, `user_agent`). ChatGPT said pages "could not be retrieved" that it never requested (2026-10-15).

`result` per agent: **pass** (all three turns, no stumble beyond one `permission`), **bump** (works, but a stumble Tom should know about), **fail**.

End the file with a Findings list, numbered on from the last number used in the chat, each saying whether the fix is ours (entry file, page content, headers, IndexNow) or theirs (platform policy, Bing index), and a one-line verdict: can the paste line go on LinkedIn today.

## 4. Afterwards

- Add one line to `docs/agent-readable/STATUS.md` under the current date with the per-agent results.
- A stumble that is ours becomes a BACKLOG item; one that is theirs is noted in `evals/fetchability-research-*.md` style, with the agent's exact wording.
- Never post or edit anything on LinkedIn; the paste line going live is Tom's hand (PRD guardrail 4).
- Cost: one chat per agent per run; no `/ask` calls from this skill. Nothing pushed, nothing committed without Tom.
