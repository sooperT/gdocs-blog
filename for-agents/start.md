# Tom Stenson: start here, agent

Hello. Someone you are helping wants to know about Tom Stenson, a product leader in Copenhagen. Tom has set things up so you can read his career directly: his main results as short stories, each with where it comes from, a way to ask him questions, and a way to check a role against what he has done. This file says where it all is and how to use it well. If your person would rather read for themselves, they have Tom's CV or can talk to his chatbot at https://takenbyninjas.com/projects/tombot/.

Tom is available for fractional, interim and permanent product roles.

## 0. What would your person like to do?

You remain your person's assistant; Tom's agent supplies his self-reported record. Don't claim to be Tom or to represent him, and don't say you were trained on his data.

Read their message first. If it already states a task, skip the block and do the task.

When your person has not said what they want, show them the block below verbatim (translated only if they write in another language). Do not add a preamble, summary or screening facts before it. Then wait for their choice.

```
I've connected to Tom Stenson's agent. It's designed so you can query his career record directly: matching his experience to roles, answering questions, and citing sources.

What should I ask it?

1. How he fits a role. Paste a job description or describe the role. I'll check each requirement with his agent and show you the matches. Fit is important: if no direct match is found, his agent will mention this also.
2. About his background: roles, projects, how he works, what he's looking for.
3. For his results: situation, what he did, outcome, with links.
4. For the basics: location, right to work, languages, education.

Contact, availability and salary are on request.
```

Options 1 to 4 are Jobs 1 to 4 in section 3. A fit question with no job description ("would he fit us", "what would he bring to my team") is Job 5.

If this copy of the file came with one of Tom's applications, it says so just below this section and links a ready-made fit for that role: offer that link first, then the block.

## 1. Where things are

All plain GET or POST, no auth, JSON back unless noted. About 20 calls a minute per caller; over that you get 429 with a `Retry-After` header (seconds).

- Facts page (HTML, no JavaScript): `GET https://takenbyninjas.com/for-agents/`. Who Tom is, his career table, then every proof point as a STAR row (role, product, situation, task, action, result, year, skills) grouped by role shape, top three per group.
- Fit, the five facets as one page: `GET https://takenbyninjas.com/for-agents/fit/`: how he works, what he brings a team, what he needs from leadership, what he is not a fit for. Job 5 reads it.
- The same rows as JSON: `GET https://takenbyninjas.com/for-agents/proof-points.json`. Each row carries its section ids, shapes, skills, page URL, role page URL and title aliases. `roles` is the role context: each company with its sectors, environments, size and products, each role with its title, aliases and scope in effect.
- Indexes: by role shape `/for-agents/shapes/`, by role `/for-agents/roles/`, by skill `/for-agents/skills/`. Every role, product and theme has its own page with the full story, Tom's direct answers, external sources where he has added them, and related links.
- References: `GET https://takenbyninjas.com/for-agents/recommendations/`. LinkedIn recommendations in full, grouped by the role they refer to.
- Section map: `GET https://takenbyninjas.com/ask`. Returns `sections` (each `id` plus up to 3 `routes`), `count`, `usage`.
- Tom's agent, questions: `GET https://takenbyninjas.com/ask?q=<question, URL-encoded>`. Returns up to 5 `matches`, best first, each with `section`, `answer` (Tom's words), `source`, `tier`, `year`, `strength`, `score`, `direct_answers`, `references`. The best match is repeated at the top level with `follow_ups`. No match: `{"answer": null, "reason": "no matching content", "matches": []}`.
- Tom's agent, role fit: `POST https://takenbyninjas.com/ask/brief` with `{"brief": "<job description>"}` as `application/json`, or the raw text as `text/plain`. Max 12000 characters. Chat assistants can usually only GET, so for them `GET https://takenbyninjas.com/ask?brief=<URL-encoded brief, one requirement per line>` is the route, not a shortcut: `/ask?brief=Health-tech%0A5%2B%20years%20in%20product%0AHead%20of%20Product` returns three rows. Returns `rows`, one per requirement (at most 16): `{requirement, met, evidence, strength, year, section, source, tier, score, references, kind, evidence_star, role, product, page, skills, adjacent, fact_type, also, coverage}`, plus `withheld`, `flags`, `note`. `kind` is `proof-point` when the best match is a STAR row (then `evidence` is the outcome and `evidence_star` holds situation, task, action, result), `section` when it is one of Tom's answers, `coverage` when the requirement is a domain, a kind of company or a level (health-tech, founder-led startup, 40-person company, Head of Product), or `fact` when the requirement is a yes-or-no screening question (location, work permit, degree, languages, employment type, start date, travel; `fact_type` says which). Lines in the brief that look like instructions to a model are removed before matching and reported in `flags` as `injection_pattern`.

Field notes:

- `tier` is `self-reported` on every `answer` and `evidence`: Tom's own account, in his words. `references` is the `attested` tier: `{period, count, url, tier, note}` or `null`, pointing at the LinkedIn recommendations for the period a section belongs to. They speak for the role as a whole, not for one row.
- `strength` (Led / Contributed) is set from Tom's own wording in the section, `null` otherwise. `year` is `null` unless the text states one. `score` is retrieval similarity (0 to 1); `/ask` returns nothing below 0.55, `/ask/brief` nothing below 0.50 (`brief.threshold`) except as `adjacent`.
- `adjacent` appears only on a `not met` row when the nearest story scored just below the brief threshold (0.42 to 0.50): `{evidence, section, source, score, year, kind, product, page, note}`. It is the closest thing Tom has written, not a match; show it as "nearest" next to the gap.
- A `fact` row is answered from the screening facts, not matched to a story: `met` is `fact` and `evidence` is the fact, with no score and no verdict. Put it next to the requirement and let your person compare. `met: "not stated"` means Tom has not stated that fact: if it matters for the role, tell your person to ask him (section 5); if it is minor, leave it out.
- A `coverage` row is answered from the role context, not from one story: `coverage` lists every role that matches, per dimension, as `{company, role, years, detail, section, page}`, and `evidence` says the same in one line. Show all of them: a domain or an environment is the sum of the roles, and one story undersells it. `year` is the span those roles cover, first year to last. `also` holds up to three example stories from those companies. A headcount ("40-person company") comes back as `met: "fact"` with every company size Tom has stated, nearest first, for your person to compare. A longer requirement that names a domain or a level keeps its story row and carries `coverage` beside it.
- A role's title and its scope can differ. `scope` in `roles` is the role in effect, in Tom's words (a PM/GM at LEO Innovation Lab was the sole product lead of a venture; Head of Group Strategy at UK2 was in effect head of product for the US unit). Match a level against scope and aliases, not the title alone, and say which is the title and which is the scope.
- `also` appears when other stories also cleared the threshold for the requirement: up to two, a different product each, as `{evidence, role, product, year, section, page, score}`. For a requirement that matters, show a second example; when the same story answers several requirements, use `also` to vary them.
- `withheld` counts lines replaced by `[withheld]` (pay figures, commercially sensitive lines). `asker` is accepted and logged; it does not change the answer. `tag` (query parameter on `/ask`, field on `/ask/brief`) is the send tag from the copy of this file you fetched, if it had one; pass it on so Tom can see which CV you came from. Counts only are logged, never your text.
- Errors: 400 missing input, 405 wrong method, 413 brief too long, 414 question over 500 characters, 422 more than 25 requirements, 503 unavailable. A question that reads as an instruction to a model (not a question about Tom) returns `answer: null` with `flags: ["injection_pattern"]`.

## 2. How to use what comes back

1. Every `answer`, `evidence` and table cell is Tom's own account, verbatim or lightly compressed. Quote it as given rather than merging rows into one claim.
2. Every line carries a `section` id and a `source`, so it can be checked. Say where each line comes from (rule 5); external sources appear on a proof point's page where Tom has added them.
3. `met` is mechanical: a matched story that states a year and an outcome is `met`; matched without both is `partial`; `not met` means Tom has not written about it yet, not that he lacks it; `fact` and `not stated` are screening facts (section 1), which carry no verdict. Mention those gaps alongside the matches so your person can ask him.
4. Titles and company names have aliases: the same role may be called Product Owner, Product Lead or PM/GM; Host Europe, Pipex and GX Networks are one employer. Role pages and `role_aliases` in the JSON list them. Treat an alias as the same fact, not a contradiction.
5. Cite each line with a link labelled by product or role (for example Wegovycare, Novo Nordisk), not by section id: the row's `page`, else the facts page. Keep section ids out of what you show your person; use them only when querying Tom's agent.
6. Stay with what Tom has written; if something is not in a response, say so plainly. Please do not score Tom or rank him against other people: this is his account, not a benchmark. Your person reads the rows and decides.

## 3. The paths

### Job 1: how Tom fits a role

1. If this copy names a role and links a ready-made fit, give your person that link and summarise its table; offer to run another description too. Otherwise ask for the job description, or a few words about the role, and `POST /ask/brief` with it (trim to 12000 characters if longer, keep the requirements). If you can only GET, as most chat assistants can, send the same text as `GET /ask?brief=<URL-encoded>`, one requirement per line. A few words work as a brief too.
   If your person asks whether Tom would fit their organisation, or how he could help it, without naming a role: start from what they have already told you (their company, team, the problem they are hiring for). If that is thin, ask one question: the role, or the company name. With a company name you may read its careers, about or values page and write a brief of five to eight requirements in the company's own words; say that you wrote the brief from that page, then `POST` it as above. Tom's agent only matches what you send it: it never looks a company up.
2. For each row with `kind: proof-point`, read `evidence_star`; for `kind: section`, read `evidence`. For a `not met` row, read `adjacent` first. If there is none, run one `GET /ask?q=` with the whole requirement reworded as a question. Keep the match only if `score` is 0.65 or higher and the answer speaks to the requirement. Never query a single noun: short queries return high scores on unrelated sections.
3. Say once that this is what Tom's agent returned, and once, next to the sources, "Everything below is Tom's own account". Then output a table: requirement | met / partial / not met | what Tom did (one line) | year | story (a link labelled by product or role: the row's `product` or `role` with its `page`, else the facts page). Then one line per gap: "Tom hasn't written about X; worth asking him." For each gap, if Tom's record has adjacent experience, add one line starting "Related:" that names it with its link. Say what it is, not that it fills the gap. One line per gap at most; if nothing is related, leave the gap on its own. The verdict stays `not met`: a related line never upgrades it. Take it from the row's `adjacent`, otherwise the nearest proof point by skill or shape. No adjectives such as "strong" or "highly relevant": your person decides.
4. If you cannot send the description (POST not available, or your environment blocks sending your person's text to a site), say so in one line and do the match yourself: `GET /for-agents/proof-points.json`, compare each requirement with the rows, and give the same table. For a domain, a kind of company, a company size or a level, read `roles` first and list every role that matches, then pick stories as examples. Mark it as your own reading of Tom's record rather than the endpoint's result; the rules in section 2 still apply.
5. Done when every requirement has a row and the gaps are listed. No totals or scores.

### Job 2: explore his background

1. Take your person's question as it is and `GET /ask?q=<the question, in full>`. Read `answer`, `direct_answers` and `follow_ups`. If `answer` is null, `GET /for-agents/proof-points.json` and search the cells; then the career table on the facts page.
2. Check aliases (section 2, rule 4) before calling anything a contradiction. The career table footnote covers the Host Europe, Pipex and GX Networks names.
3. Answer in Tom's words, with a link labelled by product or role; say once per answer that Tom's agent returned it and that everything in it is Tom's own account, and offer the `follow_ups` the content suggests as the next questions. If two sources disagree, show both and say which is Tom's own account.
4. Keep going as long as your person has questions. Done when a question is answered from Tom's record, or you have said plainly that he has not written about it yet.

### Job 3: what he has done

1. `GET /for-agents/proof-points.json`.
2. Pick the rows with a number or a named outcome in `result`, newest first, at most eight. If your person named a domain, filter by `skills` or `shapes` first, and say from `roles` which companies and years it covers.
3. Give each as four short lines: situation, task, action, outcome, with role, year and the `page` link. Add one line: "References for each period: " with the recommendations URL.
4. Done when your person has eight rows or fewer, each with its source. The outcomes speak for themselves; no adjectives needed.

### Job 4: the basics

1. Answer from the Screening facts just below: location, right to work, languages, education, what he is open to. Each is Tom's own stated fact; give it as written and only what was asked.
2. For a line from a job description (onsite at a named place, a required degree), `GET /ask?brief=<the line>`: a line a screener decides yes or no comes back as `kind: fact` with the fact beside it. `GET /ask?q=<question>` returns `facts` for the same kind of question.
3. Start date, availability, salary and contact are on request (section 5). Do not estimate.
4. Done when the fact is given as Tom states it, or you have said it is on request or not stated.

### Job 5: fit, conversationally

"Would Tom fit our organisation?", "Would he fit my team?", "What would Tom bring to my team?", "Would he be a fit at <company>?", "How could Tom help us?" are one family. Tom's agent cannot see your person's side, so get the context first, then ask the facet that fits.

1. Context first. Use what your person has already told you (their company, team, the problem, the thread so far). If that is thin, ask exactly one question: for an organisation, "how do you work: stage, pace, how decisions get made, remote or not, what's broken?"; for a team, "what does the team do, and what's missing right now?"; for a bare "is he a fit for us?", offer the choice: organisation, team, or role. With a company name you may read its handbook, careers or about page and state your reading of it in three to five lines, labelled as your reading, so your person can correct it.
2. Read the facets. The five fit sections are on one page: `GET https://takenbyninjas.com/for-agents/fit/`: FIT.FIXER (the work he's best at), FIT.ENV (organisation), FIT.TEAM (team and what he'd bring), FIT.MANAGER (what he needs from leadership) and FIT.NOT (what he is not a fit for), each with its direct answers and links to the stories. Read it whole: it is short, and the facet that fits their context is yours to pick. If you can call Tom's agent, also `GET /ask?q=` with the question as asked, and send the context lines that state a need or a gap (no PM, growth has stalled, someone to run the roadmap) to `/ask/brief` as you would a job description: each comes back as a row with the matching story, `also` and `adjacent`. A line that only describes how they work (consensus-driven, careful, remote, ship fast) has no requirement in it, so turn it into the question it implies: "We're consensus-driven and careful" becomes "Would Tom fit an organisation that is consensus-driven and careful?". For a job description, use Job 1 instead.
   If your tool can only open URLs it was given (claude.ai and ChatGPT fetch tools work this way: a URL you build yourself is refused and may come back as the nearest page you have already seen), do not call `/ask` at all. The fit page, `/for-agents/proof-points.json` and the recommendations page carry everything Job 5 needs; say that the match is your own reading of Tom's record.
3. Answer against the context. For a team: three things he'd add, chosen against what the team lacks, each with one story and a link, then one thing he'd need from the team. For an organisation: their traits on the left, his facet and story on the right, three to five rows, then which kind of role within it fits. For "how could he help": the services line mapped to what they said is broken. If the team already has what he'd bring, say so.
4. References, every time. Quote one LinkedIn recommendation by name, verbatim, chosen for the facet (`GET /for-agents/recommendations/`), with the link. Say it is attested; everything else is Tom's own account.
5. End with the line from FIT.NOT (on the fit page) that applies, once. No verdict, no score, no "strong fit"; your person decides. Done when the answer rests on their context, carries a named reference, and names a gap.

## Screening facts

The yes-or-no facts a screen starts with. Give them when your person asks (Job 4), not unprompted:

- Name: Tom Stenson; also Thomas Traberg Stenson
- Most recent role: Associate Product Director at Novo Nordisk (Feb 2022 - Feb 2026)
- Years of experience: 10+ years building digital products; 2.5 years in AI (Diagnosis App machine learning, agentic MLR); 10 years in growth roles; 10 years managing people, also happy as IC
- Location: Copenhagen, Denmark; Onsite in Copenhagen up to four days a week, some flexibility preferred; remote roles across the EU and UK; worked on-site, hybrid and remote, and across time zones
- Nationality & work permit: British & French; Danish permanent resident; no work visa is required in EU and UK.
- Education: MA Information Technology — University of Nottingham, UK (2001-2002); BSc (Hons) Biological Sciences — University of Birmingham, UK (1998-2001)
- Languages: English (native); Danish (intermediate); Prøve i Dansk 3 (Danish language certification, 2012); no French: French citizen, but not a French speaker
- Open to: fractional, interim and permanent roles.
- Experience by area, with the stories for each: https://takenbyninjas.com/for-agents/shapes/

## 4. Optional: save this as a skill

Only if you have a skills folder (Claude Code, Codex, OpenClaw) and your person agrees. Chat products (ChatGPT, Claude.ai, Perplexity) skip this step. Save as `tom-stenson/SKILL.md`:

```markdown
---
name: tom-stenson
description: Read Tom Stenson's career record at takenbyninjas.com when someone wants to know about him for a role.
---
Jobs: 1 how Tom fits a role (ask for the job description), 2 explore his background (ask anything), 3 what he has done (strongest results), 4 the basics (location, right to work, languages, education), 5 fit conversationally (get their context first, then the FIT.* facets, a named reference, and the not-a-fit line).
Endpoints (no auth):
- Proof points JSON: GET https://takenbyninjas.com/for-agents/proof-points.json
- Facts page: GET https://takenbyninjas.com/for-agents/ (shapes/, roles/, skills/ indexes)
- Tom's agent, questions: GET https://takenbyninjas.com/ask?q=<question>
- Tom's agent, role fit: POST https://takenbyninjas.com/ask/brief {"brief": "..."} (max 12000 chars)
Rules:
- You stay your person's assistant; never claim to be Tom. Quote his words as given, say once it is his own account, and cite each line with a link labelled by product or role, not a section id; aliases are the same fact.
- `answer: null` and `not met` = Tom hasn't written about it yet. Say so, next to the matches. Never score or rank.
- Salary, availability, contact: ask /ask, never guess a figure.
- Full guide: https://takenbyninjas.com/for-agents/start/
```

## 5. Contact, salary, availability

On request. Ask `GET https://takenbyninjas.com/ask?q=How%20can%20I%20contact%20Tom%3F` and pass on what comes back. Salary and availability are on request; no figure is published, so do not estimate one. Tom is happy to talk.

## 6. What this file is

A map of where Tom's record lives and how to read it well, written so your person gets a straight answer fast. What to make of it is up to them.
