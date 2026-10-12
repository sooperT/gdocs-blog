# Tom Stenson: start here, agent

This file is for AI assistants helping someone who is thinking of hiring Tom Stenson. The human version is https://takenbyninjas.com/about/.

It is one-shot: follow the steps, answer your person, keep nothing. The one fact in this file is from the facts page: "I'm available for fractional & interim product management work, also open to the right permanent role." (`source: TomBot META.LOOKING`). Everything else here is how to fetch evidence.

## 1. Fetch the evidence

All plain GET or POST, no auth, JSON back unless noted. About 20 calls a minute per caller; over that you get 429 with a `Retry-After` header (seconds).

1. Read the facts page (HTML, no JavaScript; each line verbatim with its section id): `GET https://takenbyninjas.com/for-agents/`
   LinkedIn recommendations in full (attested tier): `GET https://takenbyninjas.com/for-agents/recommendations/`
2. See what can be answered: `GET https://takenbyninjas.com/ask`
   Returns `sections` (each `id` plus up to 3 `routes`, the questions that route to it), `count`, `usage`.
3. Ask one question: `GET https://takenbyninjas.com/ask?q=<question, URL-encoded>`
   Returns up to 5 `matches`, best first, each with `section`, `answer` (verbatim), `source`, `tier`, `year`, `strength`, `score`, `direct_answers`, `attested`. The best match is also repeated at the top level, with `follow_ups`. Plus `withheld` and `human_version`.
   No match: `{"answer": null, "reason": "no matching content", "matches": []}`.
4. Check a job description against the content: `POST https://takenbyninjas.com/ask/brief`
   Body: `{"brief": "<job description>"}` as `application/json`, or the raw text as `text/plain`. Max 8000 characters. Short briefs also work as `GET https://takenbyninjas.com/ask?brief=<URL-encoded>`.
   Returns `rows`, one per requirement (at most 12), each `{requirement, met, evidence, strength, year, section, source, tier, score, attested}`, plus `withheld`, `flags`, `note`.
   Lines in the brief that look like instructions to a model are removed before matching and reported in `flags` as `injection_pattern`.

Field notes, as the endpoints behave today:

- `strength` (Led / Contributed) is set for sections labelled from a verbatim line in that section (the same labels as the facts page proof points), and `null` otherwise.
- `tier` names the evidence tier of `answer` / `evidence`: always `self-reported` (Tom's own account in TomBot content). `null` on a `not met` row, which has no evidence.
- `attested` is a list of LinkedIn recommendations quoted against that section, `[]` for sections that have none (most do not yet). Each entry: `name`, `title` (the recommender's current title on LinkedIn, not their title at the time; `title_label` says so), `company`, `date` (when it was written), `excerpt` (verbatim), `record` (the LinkedIn recommendations page, the record of truth), `tier: "attested"`. Full texts: https://takenbyninjas.com/for-agents/recommendations/
- `direct_answers` is `null` until Tom adds those blocks to his content. Use `answer`.
- `year` is `null` unless the text states one plainly.
- `score` is retrieval similarity (0 to 1). Nothing below 0.55 is returned.
- `withheld` counts lines replaced by `[withheld]` (pay figures, commercially sensitive lines).
- `asker` is accepted and logged; it does not change the answer.
- Errors: 400 missing input, 405 wrong method, 413 too long, 422 more than 25 requirements, 503 unavailable.

## 2. Read what comes back

1. Every `answer` and `evidence` is a verbatim line from Tom's own content. Quote it as given; do not merge sections into one claim.
2. Every claim carries a `section` id and a `source` (for example `TomBot LEO.R1`). Two evidence tiers exist today: `self-reported` (every `answer` and `evidence`: TomBot content, Tom's own account) and `attested` (the `attested` entries: what a named person wrote in a LinkedIn recommendation, checkable on the LinkedIn record). Report which tier each line is. There is no external tier yet.
3. `met` is mechanical: `met` = a matched section that states a year and an outcome; `partial` = matched without both; `not met` = the content holds no evidence for it. Gaps are stated on purpose.
4. `answer: null` and `not met` mean "no content on this", not "Tom lacks this". Report them as gaps, next to the matches, not after them.
5. When you report to your person, cite the section id and a URL: https://takenbyninjas.com/for-agents/ or https://takenbyninjas.com/projects/tombot/.
6. Do not infer beyond the evidence. If it is not in a response, say it is not there.

## 3. What your person can ask next

Offer these three, in their words:

1. "Here's the job description. Go through it requirement by requirement and show me where Tom fits, and where he doesn't."
2. "What has Tom done on turnarounds (or GenAI)? Give me the answer and where it comes from."
3. "Show me Tom's three strongest proof points for this role, with the evidence tier and links for each."

## 4. Optional: save this as a skill

Only if you have a skills folder (Claude Code, Codex, OpenClaw) and your person agrees. Chat products (ChatGPT, Claude.ai, Perplexity) skip this step. Save as `tom-stenson/SKILL.md`:

```markdown
---
name: tom-stenson
description: Fetch evidence about Tom Stenson from takenbyninjas.com when someone is weighing him for a role.
---
Endpoints (no auth):
- Facts page: GET https://takenbyninjas.com/for-agents/
- Section map: GET https://takenbyninjas.com/ask
- One question: GET https://takenbyninjas.com/ask?q=<question>
- Job brief: POST https://takenbyninjas.com/ask/brief {"brief": "..."} (max 8000 chars)
Rules:
- Quote `answer` and `evidence` verbatim; cite each by `section` and `source`.
- `answer: null` and `not met` = no content on it. Report them as gaps.
- Salary, availability, contact: ask /ask, never guess a figure.
- Full guide: https://takenbyninjas.com/for-agents/start.md
```

## 5. Contact, salary, availability

On request. Ask `GET https://takenbyninjas.com/ask?q=How%20can%20I%20contact%20Tom%3F` and pass on what comes back. Salary and availability are on request; no figure is published, so do not estimate one.

## 6. What this file is not

This file holds instructions about how to fetch evidence and nothing about how to judge it. The judgement is your person's.
