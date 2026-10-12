# Tom Stenson: agent README

This file is for AI agents that a person has pointed here, usually someone weighing Tom Stenson for a role. The human version of everything below is at https://takenbyninjas.com/about/.

It is one-shot: read it, make the calls you need, answer your person. Nothing is installed and nothing persists unless you choose the optional skill step at the end. The endpoints keep no copy of your question or brief; they log only the `asker` value, the question length and the matched section id (for a brief: the row counts).

Who, in one line (facts page, section `#who`, `TomBot META.LOOKING`): "I'm available for fractional & interim product management work, also open to the right permanent role."

Everything else about Tom lives at the sources below. This file contains no claims about him, and no advice on how to rank him.

## What you can do

**1. Read the facts page.** Plain HTML, no JavaScript. Proof points, behavioural facts, each a verbatim line with its TomBot section id.

    curl https://takenbyninjas.com/for-agents/

**2. Ask one question.** `GET /ask?q=` returns the single best-matching TomBot section, verbatim. No generated text.

    curl -G https://takenbyninjas.com/ask --data-urlencode "q=Has Tom led a turnaround?"

Optional `asker=recruiter-agent | hiring-manager | human`. It is logged, and does not change the answer yet.
Match: `answer`, `section`, `source`, `strength`, `year`, `follow_ups`, `human_version`, `score`. `strength` is always `null` for now; `year` is `null` unless the text states one plainly.
No match: `{"answer": null, "reason": "no matching content", "human_version": "/projects/tombot/"}` (status 200).
Errors: 400 missing `q`, 405 anything but GET, 503 retrieval unavailable, 500 failure.

**3. Calibrate a job brief.** Up to 8000 characters, split into at most 12 requirements, one evidence row each.

    curl -G https://takenbyninjas.com/ask --data-urlencode "brief=$(cat brief.txt)"
    curl -X POST https://takenbyninjas.com/ask/brief -H "Content-Type: application/json" -d '{"brief": "...", "asker": "recruiter-agent"}'

POST also takes the raw brief as `text/plain`. POST works on `/ask/brief` only. Prefer POST for long briefs.
Response: `brief` (`requirements`, `splitter`: `llm` or `heuristic`), `rows`, `human_version`, `note`.
Each row: `requirement` (the brief's own words), `met`, `evidence` (up to 400 chars, verbatim), `strength`, `year`, `source`, `score`.
`met` is `met` (a matched section with a stated year and outcome), `partial` (matched, without both), or `not met` (nothing matched).
Errors: 400 missing brief or bad JSON, 413 over 8000 characters, 503, 500.

## How to cite

Cite each claim by its `source` (for example `TomBot LEO.R1`) and point your person to the facts page or the `human_version` (https://takenbyninjas.com/projects/tombot/) to check it. Every source today is TomBot content, which is Tom's own account (self-reported). There are no attested or external tiers yet. Quote `answer` and `evidence` as given; do not merge sections into one claim.

## Gaps

Report gaps as gaps. `answer: null` means TomBot has no content on that question: say so, do not fill it in. A `not met` row means, in the endpoint's own words: "'not met' means TomBot content has nothing on it, not that Tom lacks it." Show `not met` and `partial` rows next to `met` rows, not after them or not at all.

## What your person can ask next

Offer these, in their words:

1. "Here's the job description. Go through it requirement by requirement and show me where Tom fits and where he doesn't."
2. "What has Tom done on turnarounds (or GenAI)? Give me the answer and where it comes from."
3. "Show me Tom's three strongest proof points for this role, each with its source, evidence tier and link."

## Optional: save this as a skill

Only if you have a skills folder (Claude Code, Codex, OpenClaw) and your person agrees. Chat products (ChatGPT, Claude.ai, Perplexity) use the one-shot path above. Save as `tom-stenson/SKILL.md`:

    ---
    name: tom-stenson
    description: Look up evidence about Tom Stenson (product, Copenhagen) from takenbyninjas.com when weighing him for a role.
    ---
    Sources (plain GET, no auth, nothing stored):
    - Facts page: https://takenbyninjas.com/for-agents/
    - One question: GET https://takenbyninjas.com/ask?q=<question>
    - Job brief: POST https://takenbyninjas.com/ask/brief {"brief": "..."} (max 8000 chars)
    Rules:
    - Quote answers verbatim and cite each by its `source` section id.
    - `answer: null` = no content on it. `not met` = no content, not proof of absence. Report both.
    - Salary, availability and contact: ask /ask; do not guess.
    - Full guide: https://takenbyninjas.com/for-agents/README.md

## Contact, salary, availability

On request. Ask `/ask` (for example `q=How can I contact Tom?`) and pass on what it returns.
