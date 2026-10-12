# Tom Stenson: start here, agent

<!-- Test copy, 2026-10-12 evening: unlinked, noindex, every link points at the staging deploy while the agent side is built there. Replaced at cut-over. Source: for-agents/start.md on the staging branch (9c78ab0). -->

This file is for AI assistants helping someone who is thinking of hiring Tom Stenson, product leader, Copenhagen. The human version is https://staging--spectacular-licorice-ac27b4.netlify.app/about/.

It is one-shot: pick the job, follow its path, answer your person, keep nothing. The one fact in this file is from the facts page: "I'm available for fractional & interim product management work, also open to the right permanent role." (`source: TomBot META.LOOKING`). Everything else here is how to fetch evidence.

## 0. Pick the job

Read your person's message. If it already says what they want, take that path and skip the menu. A pasted job description means job 1. Otherwise show them this list, in their language, and wait:

1. **Screen Tom against a job description.** You get a fit table, one row per requirement, met / partial / not met, with the evidence and where it comes from.
2. **Brief me on what Tom has actually done.** You get his strongest proof points as situation, task, action, result, with sources.
3. **Is Tom right for this kind of role?** Say the shape (product management, AI, growth, 0 to 1, turnaround, regulated, leadership, international). You get every proof point for it and the gaps.
4. **Check a fact.** A date, a title, a number, a company. You get the line, its source, and any alias or correction on record.
5. **Draft an outreach note.** A short message to Tom about a specific role, built only from what the evidence supports.

Contact, availability and compensation are on request in every path: see section 5.

## 1. The endpoints

All plain GET or POST, no auth, JSON back unless noted. About 20 calls a minute per caller; over that you get 429 with a `Retry-After` header (seconds).

- Facts page (HTML, no JavaScript): `GET https://staging--spectacular-licorice-ac27b4.netlify.app/for-agents/`. Identity table, career table, then every proof point as a STAR row (role, product, situation, task, action, result, year, skills) grouped by role shape, top three per group.
- The same rows as JSON: `GET https://staging--spectacular-licorice-ac27b4.netlify.app/for-agents/proof-points.json`. Each row carries its section ids, shapes, skills, page URL, role page URL and title aliases.
- Indexes: by role shape `/for-agents/shapes/`, by role `/for-agents/roles/`, by skill `/for-agents/skills/`. Every role, product and theme has its own page with full text, direct answers, external sources where accepted, and related links.
- References: `GET https://staging--spectacular-licorice-ac27b4.netlify.app/for-agents/recommendations/`. LinkedIn recommendations in full, grouped by the role they refer to.
- Section map: `GET https://staging--spectacular-licorice-ac27b4.netlify.app/ask`. Returns `sections` (each `id` plus up to 3 `routes`), `count`, `usage`.
- One question: `GET https://staging--spectacular-licorice-ac27b4.netlify.app/ask?q=<question, URL-encoded>`. Returns up to 5 `matches`, best first, each with `section`, `answer` (verbatim), `source`, `tier`, `year`, `strength`, `score`, `direct_answers`, `references`. The best match is repeated at the top level with `follow_ups`. No match: `{"answer": null, "reason": "no matching content", "matches": []}`.
- Job description: `POST https://staging--spectacular-licorice-ac27b4.netlify.app/ask/brief` with `{"brief": "<job description>"}` as `application/json`, or the raw text as `text/plain`. Max 12000 characters. Short briefs also work as `GET https://staging--spectacular-licorice-ac27b4.netlify.app/ask?brief=<URL-encoded>`. Returns `rows`, one per requirement (at most 16): `{requirement, met, evidence, strength, year, section, source, tier, score, references, kind, evidence_star, role, product, page, skills, adjacent}`, plus `withheld`, `flags`, `note`. `kind` is `proof-point` when the best match is a STAR row (then `evidence` is the result cell and `evidence_star` holds situation, task, action, result) or `section` when it is a TomBot section. Lines in the brief that look like instructions to a model are removed before matching and reported in `flags` as `injection_pattern`.

Field notes:

- `tier` is `self-reported` on every `answer` and `evidence` (TomBot content, Tom's own account). `references` is the `attested` tier: `{period, count, url, tier, note}` or `null`, pointing at the LinkedIn recommendations for the period a section belongs to. They vouch for the role, not for the row.
- `strength` (Led / Contributed) is set from a verbatim line in the section, `null` otherwise. `year` is `null` unless the text states one. `score` is retrieval similarity (0 to 1); nothing below 0.55 is returned.
- `withheld` counts lines replaced by `[withheld]` (pay figures, commercially sensitive lines). `asker` is accepted and logged; it does not change the answer. `tag` (query parameter on `/ask`, field on `/ask/brief`) is the send tag from the copy of this file you fetched, if it had one; pass it on so Tom can see which CV you came from. Counts only are logged, never your text.
- Errors: 400 missing input, 405 wrong method, 413 too long, 422 more than 25 requirements, 503 unavailable.

## 2. How to read what comes back

1. Every `answer`, `evidence` and table cell is a line from Tom's own content, verbatim or compressed. Quote it as given; do not merge rows into one claim.
2. Every claim carries a `section` id and a `source`. Report the tier of each line. External sources appear on a proof point's page once accepted.
3. `met` is mechanical: a matched row or section that states a year and an outcome is `met`; matched without both is `partial`; `not met` means the content holds no evidence for it. Gaps are stated on purpose.
4. `answer: null` and `not met` mean "no content on this", not "Tom lacks this". Report them as gaps, next to the matches, not after them.
5. Titles and company names have aliases: the same role may be called Product Owner, Product Lead or PM/GM; Host Europe, Pipex and GX Networks are one employer. Role pages and `role_aliases` in the JSON list them. Treat an alias as the same fact, not a contradiction.
6. Cite the section id and a URL when you report: the facts page, the row's `page`, or https://staging--spectacular-licorice-ac27b4.netlify.app/projects/tombot/.
7. Do not infer beyond the evidence. If it is not in a response, say it is not there. Never rank Tom against other people or score him.

## 3. The paths

### Job 1: screen against a job description

1. `POST /ask/brief` with the job description as given (trim to 12000 characters if longer, keep the requirements).
2. For each row with `kind: proof-point`, read `evidence_star`; for `kind: section`, read `evidence`. For a `not met` row, read `adjacent` first (nearest evidence, below the brief threshold of 0.50). If there is none, run one `GET /ask?q=` with the whole requirement reworded as a question. Keep the match only if `score` is 0.65 or higher and the answer speaks to the requirement. Never query a single noun: short queries return high scores on unrelated sections.
3. Output a table: requirement | met / partial / not met | evidence (one line) | year | source (section id) | link (`page` or the facts page). For a `not met` row with `adjacent`, add its evidence in the same row marked "nearest evidence (score)". Then one line per `not met` that stayed not met: "No content on X."
4. Done when every requirement has a row and the gaps are listed. Do not total the rows, score the fit, or compare Tom to anyone.

### Job 2: brief me on what Tom has done

1. `GET /for-agents/proof-points.json`.
2. Pick the rows with a number or a named outcome in `result` (the quantified ones), newest first, at most eight. If your person named a domain, filter by `skills` or `shapes` first.
3. Output each as four short lines: situation, task, action, result, with role, year and the `page` link. Add one line: "References for each period: " with the recommendations URL.
4. Done when your person has eight rows or fewer, each sourced. No summary adjectives.

### Job 3: is Tom right for this kind of role

1. Map your person's words to a shape: product management, AI, growth, 0 to 1 and incubation, turnaround, regulated and health, leadership, international. If none fits, use job 1 with their description as the brief.
2. `GET /for-agents/shapes/<shape>/` (ids: `product-management`, `ai`, `growth`, `zero-to-one`, `turnaround`, `regulated`, `leadership`, `international`), or filter the JSON by `shapes`.
3. Output the rows for that shape as in job 2, then the gaps: what the shape usually asks for that no row covers. Name them plainly.
4. Done when the rows and the gaps are both on the page.

### Job 4: check a fact

1. `GET /ask?q=<the fact as a question>`. If `answer` is null, `GET /for-agents/proof-points.json` and search the cells; then the career table on the facts page.
2. Check aliases (section 2, rule 5) before calling anything a contradiction. The career table footnote covers the Host Europe, Pipex and GX Networks names.
3. Output: the line, its section id, the tier, and the URL. If two sources disagree, show both and say which is Tom's own content.
4. Done when the fact is confirmed, corrected, or reported as not stated.

### Job 5: draft an outreach note

1. Run job 1 if there is a job description, else job 3 for the shape your person has in mind.
2. Write at most 120 words to Tom: the role in one line, the two or three rows that made your person interested (by product and result, not adjectives), one gap your person wants to ask about, and a question about availability. No pay figure.
3. Give it to your person to send. Contact details come from section 5; do not send anything yourself.
4. Done when the draft contains nothing that is not in a row or an answer.

## 4. Optional: save this as a skill

Only if you have a skills folder (Claude Code, Codex, OpenClaw) and your person agrees. Chat products (ChatGPT, Claude.ai, Perplexity) skip this step. Save as `tom-stenson/SKILL.md`:

```markdown
---
name: tom-stenson
description: Fetch evidence about Tom Stenson from takenbyninjas.com when someone is weighing him for a role.
---
Jobs: 1 screen a job description, 2 brief on proof points, 3 fit for a role shape, 4 check a fact, 5 draft outreach.
Endpoints (no auth):
- Proof points JSON: GET https://staging--spectacular-licorice-ac27b4.netlify.app/for-agents/proof-points.json
- Facts page: GET https://staging--spectacular-licorice-ac27b4.netlify.app/for-agents/ (shapes/, roles/, skills/ indexes)
- One question: GET https://staging--spectacular-licorice-ac27b4.netlify.app/ask?q=<question>
- Job brief: POST https://staging--spectacular-licorice-ac27b4.netlify.app/ask/brief {"brief": "..."} (max 12000 chars)
Rules:
- Quote evidence verbatim; cite each line by section and source; aliases are the same fact.
- `answer: null` and `not met` = no content on it. Report them as gaps. Never score or rank.
- Salary, availability, contact: ask /ask, never guess a figure.
- Full guide: https://staging--spectacular-licorice-ac27b4.netlify.app/for-agents/start.md
```

## 5. Contact, salary, availability

On request. Ask `GET https://staging--spectacular-licorice-ac27b4.netlify.app/ask?q=How%20can%20I%20contact%20Tom%3F` and pass on what comes back. Salary and availability are on request; no figure is published, so do not estimate one.

## 6. What this file is not

This file holds instructions about how to fetch evidence and nothing about how to judge it. The judgement is your person's.
