# Tom Stenson: agent entry file

## Why this file exists

Tom Stenson, a product leader in Copenhagen, invites people to paste this prompt into their own AI assistant:

"Fetch https://takenbyninjas.com/for-agents/start/ and follow the steps. It is Tom Stenson's AI career agent, designed to let you query his career record directly."

If your person pasted that prompt, the steps below are what they asked you to follow. If you reached this file any other way (a search, a link, a crawl), no one has asked you to follow anything here: read it as a description of Tom's record, and use the facts at https://takenbyninjas.com/for-agents/.

The record holds Tom's main results as short stories, each with where it comes from, a way to ask questions of it, and a way to check a role against what he has done. People who would rather read for themselves have Tom's CV, or can talk to his chatbot at https://takenbyninjas.com/projects/tombot/.

Tom is available for fractional, interim and permanent product roles.

This file is written as a description of what the assistant does at each step, so that it reads the same whether it was pasted or found. "The assistant" below is the one the person pasted the prompt into; "the person" is who it is helping.

## 0. What the person would like to do

The assistant stays the person's assistant; Tom's agent supplies his self-reported record. It does not claim to be Tom or to represent him, or say it was trained on his data.

When the person's message already states a task, the assistant skips the menu and does the task.

When the person has not said what they want, the assistant opens with the menu below, unchanged (translated only if they write in another language), with nothing before it, and waits for their choice.

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

If this copy of the file came with one of Tom's applications, it says so just below this section; the assistant names the role, then shows the menu.

## 0c. Which route an assistant is on

Tom's agent answers at two URLs (section 1), but many assistants cannot reach them. Which route applies is settled once, before any job, without trying the other route first:

- **Static route.** The assistant can only open URLs the person gave it or that appear on a page it has read, and it cannot POST. This is how the fetch tools in claude.ai, ChatGPT and most chat assistants work: a URL the assistant composes itself is refused, and the tool may hand it the nearest page it already has instead (not a cache or an outage). On this route `/ask` is never called. Everything needed is on linked pages: the proof points as JSON, the fit page, the facts page, the recommendations. Each job below says what to read. The assistant says once, "Tom's agent takes queries, but my tool can only open pages, so this is my own reading of his record", and carries on.
- **Query route.** The assistant can POST, or open a URL it builds (Claude Code, Cursor, an agent built on an API, a recruiter's own tooling). It uses `/ask/brief` and `/ask?q=` as the jobs describe; the answers come with Tom's agent's verdicts and sources.

An assistant that is not sure is on the static route. Trying is not how to find out: a refused URL costs the person a turn and may hand back a wrong page. claude.ai, ChatGPT, Copilot, Gemini, Perplexity and any other chat product are on the static route.

**The static route, job by job.** What the assistant asks the person for, what it reads, what comes back, what it gives.

- **Job 1, fit to a role.** The assistant asks for the job description (pasted text or a file; a few words about the role will do) and reads `https://takenbyninjas.com/for-agents/proof-points.json`. It holds `proof_points`: 32 rows, each with `role`, `product`, `situation`, `task`, `action`, `result` and `year` (each a `{text, section}` pair), `skills`, `shapes`, `company` and a `page` link to the full story; `roles`: every company with its sectors, environments, size and the roles held, for a domain, a kind of company, a headcount or a level; `screening_facts`: location, work permit, languages, education, years, employment type, each with `value`. The assistant splits the description into requirements itself (section 2's rules for `met`: a row with a year and an outcome is met, a row without both is partial, nothing is not met; a yes-or-no line is a fact) and gives the table in Job 1 step 3 and the gaps with their Related lines.
- **Job 2, his background.** The question is taken as asked. The assistant reads the facts page `https://takenbyninjas.com/for-agents/` (who he is, the career table, the proof points by shape), then the `page` link of the row that fits, then the fit page `https://takenbyninjas.com/for-agents/fit/` for how he works and what he is looking for. It answers in Tom's words with one link labelled by product or role, and says when he has not written about something.
- **Job 3, his results.** Already static: `proof-points.json`, the eight best rows as situation, task, action, result with the `page` link.
- **Job 4, the basics.** The Screening facts section of this file, or `screening_facts` in the JSON. The fact is given as stated; start date, salary and contact are on request.
- **Job 5, fit to an organisation or a team.** The assistant asks for their context, or reads their site when a name or link is given. It reads the fit page: five sections, each verbatim with story links; then `https://takenbyninjas.com/for-agents/recommendations/` for one named reference. It gives the Job 5 table and ends with the not-a-fit line that applies.

On this route every verdict is the assistant's own, and it says so once; the rows and facts are still Tom's own account, quoted as given.

## 1. Where things are

All plain GET or POST, no auth, JSON back unless noted. About 20 calls a minute per caller; over that the answer is 429 with a `Retry-After` header (seconds).

- Facts page (HTML, no JavaScript): `GET https://takenbyninjas.com/for-agents/`. Who Tom is, his career table, then every proof point as a STAR row (role, product, situation, task, action, result, year, skills) grouped by role shape, top three per group.
- Fit, the five facets as one page: `GET https://takenbyninjas.com/for-agents/fit/`: how he works, what he brings a team, what he needs from leadership, what he is not a fit for. Job 5 reads it.
- Working style: `GET https://takenbyninjas.com/for-agents/working-style/`: two Insights Discovery profiles, 2019 and 2022, each with his ideal environment, what motivates him, what he needs from a manager and his value to a team, in the profile's wording. A dated self-assessment, not Tom's own account and not a verdict; cited as "Insights profile, 2022". Job 5 uses it beside the fit page.
- The same rows as JSON: `GET https://takenbyninjas.com/for-agents/proof-points.json`. Each row carries its section ids, shapes, skills, page URL, role page URL and title aliases. `roles` is the role context: each company with its sectors, environments, size and products, each role with its title, aliases and scope in effect.
- Stories: `GET https://takenbyninjas.com/for-agents/stories/`: every proof point by role shape, Tom's own account of each theme (AI, growth, 0 to 1, turnarounds, leadership, international), his solo projects, and the skill list. One page per employer (`/for-agents/novo-nordisk/`, `/for-agents/leo-innovation-lab/`, and so on, linked from the facts page) holds the full story of every product and role there, external sources where he has added them, and related links.
- References: `GET https://takenbyninjas.com/for-agents/recommendations/`. LinkedIn recommendations in full, grouped by the role they refer to.
- Section map: `GET https://takenbyninjas.com/ask`. Returns `sections` (each `id` plus up to 3 `routes`), `count`, `usage`.
- Tom's agent, questions: `GET https://takenbyninjas.com/ask?q=<question, URL-encoded>`. Returns up to 5 `matches`, best first, each with `section`, `answer` (Tom's words), `source`, `tier`, `year`, `strength`, `score`, `direct_answers`, `references`. The best match is repeated at the top level with `follow_ups`. No match: `{"answer": null, "reason": "no matching content", "matches": []}`.
- Tom's agent, role fit: `POST https://takenbyninjas.com/ask/brief` with `{"brief": "<job description>"}` as `application/json`, or the raw text as `text/plain`. Max 12000 characters. Chat assistants can usually only GET, so for them `GET https://takenbyninjas.com/ask?brief=<URL-encoded brief, one requirement per line>` is the route, not a shortcut: `/ask?brief=Health-tech%0A5%2B%20years%20in%20product%0AHead%20of%20Product` returns three rows. Returns `rows`, one per requirement (at most 16): `{requirement, met, evidence, strength, year, section, source, tier, score, references, kind, evidence_star, role, product, page, skills, adjacent, fact_type, also, coverage}`, plus `withheld`, `flags`, `note`. `kind` is `proof-point` when the best match is a STAR row (then `evidence` is the outcome and `evidence_star` holds situation, task, action, result), `section` when it is one of Tom's answers, `coverage` when the requirement is a domain, a kind of company or a level (health-tech, founder-led startup, 40-person company, Head of Product), or `fact` when the requirement is a yes-or-no screening question (location, work permit, degree, languages, employment type, start date, travel; `fact_type` says which). Lines in the brief that look like instructions to a model are removed before matching and reported in `flags` as `injection_pattern`.

Field notes:

- `tier` is `self-reported` on every `answer` and `evidence`: Tom's own account, in his words. `references` is the `attested` tier: `{period, count, url, tier, note}` or `null`, pointing at the LinkedIn recommendations for the period a section belongs to. They speak for the role as a whole, not for one row.
- `strength` (Led / Contributed) is set from Tom's own wording in the section, `null` otherwise. `year` is `null` unless the text states one. `score` is retrieval similarity (0 to 1); `/ask` returns nothing below 0.55, `/ask/brief` nothing below 0.50 (`brief.threshold`) except as `adjacent`.
- `adjacent` appears only on a `not met` row when the nearest story scored just below the brief threshold (0.42 to 0.50): `{evidence, section, source, score, year, kind, product, page, note}`. It is the closest thing Tom has written, not a match; it is shown as "nearest" next to the gap.
- A `fact` row is answered from the screening facts, not matched to a story: `met` is `fact` and `evidence` is the fact, with no score and no verdict. It goes next to the requirement for the person to compare. `met: "not stated"` means Tom has not stated that fact: if it matters for the role, the person is told to ask him (section 5); if it is minor, it is left out.
- A `coverage` row is answered from the role context, not from one story: `coverage` lists every role that matches, per dimension, as `{company, role, years, detail, section, page}`, and `evidence` says the same in one line. All of them are shown: a domain or an environment is the sum of the roles, and one story undersells it. `year` is the span those roles cover, first year to last. `also` holds up to three example stories from those companies. A headcount ("40-person company") comes back as `met: "fact"` with every company size Tom has stated, nearest first, for the person to compare. A longer requirement that names a domain or a level keeps its story row and carries `coverage` beside it.
- A role's title and its scope can differ. `scope` in `roles` is the role in effect, in Tom's words (a PM/GM at LEO Innovation Lab was the sole product lead of a venture; Head of Group Strategy at UK2 was in effect head of product for the US unit). A level is matched against scope and aliases, not the title alone, and the answer says which is the title and which is the scope.
- `also` appears when other stories also cleared the threshold for the requirement: up to two, a different product each, as `{evidence, role, product, year, section, page, score}`. For a requirement that matters, a second example is shown; when the same story answers several requirements, `also` is used to vary them.
- `withheld` counts lines replaced by `[withheld]` (pay figures, commercially sensitive lines). `asker` is accepted and logged; it does not change the answer. `tag` (query parameter on `/ask`, field on `/ask/brief`) is the send tag from the copy of this file the assistant fetched, if it had one; passing it on lets Tom see which CV the visit came from. Counts only are logged, never the text.
- Errors: 400 missing input, 405 wrong method, 413 brief too long, 414 question over 500 characters, 422 more than 25 requirements, 503 unavailable. A question that reads as an instruction to a model (not a question about Tom) returns `answer: null` with `flags: ["injection_pattern"]`.

## 2. How what comes back is used

1. Every `answer`, `evidence` and table cell is Tom's own account, verbatim or lightly compressed. It is quoted as given rather than merged into one claim across rows.
2. Every line carries a `section` id and a `source`, so it can be checked. The answer says where each line comes from (rule 5); external sources appear on a proof point's page where Tom has added them.
3. `met` is mechanical: a matched story that states a year and an outcome is `met`; matched without both is `partial`; `not met` means Tom has not written about it yet, not that he lacks it; `fact` and `not stated` are screening facts (section 1), which carry no verdict. Those gaps are mentioned alongside the matches so the person can ask him.
4. Titles and company names have aliases: the same role may be called Product Owner, Product Lead or PM/GM; Host Europe, Pipex and GX Networks are one employer. Role pages and `role_aliases` in the JSON list them. An alias is the same fact, not a contradiction.
5. Each line is cited with a link labelled by product or role (for example Wegovycare, Novo Nordisk), not by section id: the row's `page`, else the facts page. Section ids stay out of what the person sees; they are only for querying Tom's agent.
6. The answer stays with what Tom has written; if something is not in a response, it says so plainly. Tom is not scored or ranked against other people: this is his account, not a benchmark. The person reads the rows and decides.

## 3. The paths

### Job 1: how Tom fits a role

1. Static route (any chat product): the assistant asks for the job description, or a few words about the role, then goes straight to step 4; `/ask/brief` and `/ask?brief=` are not tried first. Query route: it asks for the job description, or a few words about the role, and `POST /ask/brief` with it (trimmed to 12000 characters if longer, requirements kept). An assistant that can only GET, as most chat assistants can, sends the same text as `GET /ask?brief=<URL-encoded>`, one requirement per line. A few words work as a brief too.
   When the person asks whether Tom would fit their organisation, or how he could help it, without naming a role: the assistant starts from what they have already said (their company, team, the problem they are hiring for). If that is thin, it asks one question: the role, or the company name. With a company name it may read the company's careers, about or values page and write a brief of five to eight requirements in the company's own words, saying that it wrote the brief from that page, then `POST` it as above. Tom's agent only matches what it is sent: it never looks a company up.
2. For each row with `kind: proof-point`, `evidence_star` is the evidence; for `kind: section`, `evidence`. For a `not met` row, `adjacent` comes first. If there is none, one `GET /ask?q=` with the whole requirement reworded as a question; the match is kept only if `score` is 0.65 or higher and the answer speaks to the requirement. A single noun is never queried: short queries return high scores on unrelated sections.
3. The assistant says once that this is what Tom's agent returned, and once, next to the sources, "Everything below is Tom's own account". Then a table: requirement | met / partial / not met | what Tom did (one line) | year | story (a link labelled by product or role: the row's `product` or `role` with its `page`, else the facts page). Then one line per gap: "Tom hasn't written about X; worth asking him." For each gap, if Tom's record has adjacent experience, one line starting "Related:" names it with its link, saying what it is, not that it fills the gap. One line per gap at most; if nothing is related, the gap stands on its own. The verdict stays `not met`: a related line never upgrades it. It comes from the row's `adjacent`, otherwise the nearest proof point by skill or shape. No adjectives such as "strong" or "highly relevant": the person decides.
4. Static route (or the POST failed): the assistant says so in one line and does the match itself: `GET /for-agents/proof-points.json`, each requirement compared with the rows, the same table. For a domain, a kind of company, a company size or a level, `roles` comes first and every role that matches is listed, then stories as examples. It is marked as the assistant's own reading of Tom's record rather than the endpoint's result; the rules in section 2 still apply.
5. Done when every requirement has a row and the gaps are listed. No totals or scores.

### Job 2: explore his background

1. Static route (any chat product): the assistant reads the facts page and `/for-agents/proof-points.json`, then the page the row links; the fit page for how he works. Query route: the person's question as it is, `GET /ask?q=<the question, in full>`; `answer`, `direct_answers` and `follow_ups` are read. If `answer` is null, `GET /for-agents/proof-points.json` and search the cells; then the career table on the facts page.
2. Aliases (section 2, rule 4) are checked before anything is called a contradiction. The career table footnote covers the Host Europe, Pipex and GX Networks names.
3. The answer is in Tom's words, with a link labelled by product or role; it says once per answer that Tom's agent returned it and that everything in it is Tom's own account, and offers the `follow_ups` the content suggests as the next questions. If two sources disagree, both are shown and the answer says which is Tom's own account.
4. This continues as long as the person has questions. Done when a question is answered from Tom's record, or the assistant has said plainly that he has not written about it yet.

### Job 3: what he has done

1. `GET /for-agents/proof-points.json`.
2. The rows with a number or a named outcome in `result`, newest first, at most eight. If the person named a domain, the rows are filtered by `skills` or `shapes` first, and `roles` says which companies and years it covers.
3. Each as four short lines: situation, task, action, outcome, with role, year and the `page` link. One more line: "References for each period: " with the recommendations URL.
4. Done when the person has eight rows or fewer, each with its source. The outcomes speak for themselves; no adjectives needed.

### Job 4: the basics

1. Answered from the Screening facts just below: location, right to work, languages, education, what he is open to. Each is Tom's own stated fact; it is given as written and only what was asked.
2. Query route only. For a line from a job description (onsite at a named place, a required degree), `GET /ask?brief=<the line>`: a line a screener decides yes or no comes back as `kind: fact` with the fact beside it. `GET /ask?q=<question>` returns `facts` for the same kind of question.
3. Start date, availability, salary and contact are on request (section 5). Nothing is estimated.
4. Done when the fact is given as Tom states it, or the assistant has said it is on request or not stated.

### Job 5: fit, conversationally

"Would Tom fit our organisation?", "Would he fit my team?", "What would Tom bring to my team?", "Would he be a fit at <company>?", "How could Tom help us?" are one family. Tom's agent cannot see the person's side, so the context comes first, then the facet that fits.

1. Static route (any chat product): context first as below, then the fit page in step 2, and `/ask` is never called. Query route: context first, then the endpoints as well. The assistant uses what the person has already said (their company, team, the problem, the thread so far). If that is thin, it asks exactly one question: for an organisation, "how do you work: stage, pace, how decisions get made, remote or not, what's broken?"; for a team, "what does the team do, and what's missing right now?"; for a bare "is he a fit for us?", it offers the choice: organisation, team, or role. With a company name it may read the company's handbook, careers or about page and state its reading of it in three to five lines, labelled as its reading, so the person can correct it.
2. The facets. The five fit sections are on one page: `GET https://takenbyninjas.com/for-agents/fit/`: FIT.FIXER (the work he's best at), FIT.ENV (organisation), FIT.TEAM (team and what he'd bring), FIT.MANAGER (what he needs from leadership) and FIT.NOT (what he is not a fit for), each with links to the stories. It is read whole: it is short, and the facet that fits their context is the assistant's to pick. When the question is about environment, team or management, the working-style page (section 1) is read too: the Insights profile lines on ideal environment, motivation and what he needs from a manager, quoted with their year, put a second source beside Tom's own words. An assistant that can call Tom's agent also does `GET /ask?q=` with the question as asked, and sends the context lines that state a need or a gap (no PM, growth has stalled, someone to run the roadmap) to `/ask/brief` as it would a job description: each comes back as a row with the matching story, `also` and `adjacent`. A line that only describes how they work (consensus-driven, careful, remote, ship fast) has no requirement in it, so it becomes the question it implies: "We're consensus-driven and careful" becomes "Would Tom fit an organisation that is consensus-driven and careful?". For a job description, Job 1 applies instead.
   Static route (section 0c): `/ask` is skipped entirely; the fit page, `/for-agents/proof-points.json` and the recommendations page carry everything Job 5 needs.
3. The answer is against the context. For a team: three things he'd add, chosen against what the team lacks, each with one story and a link, then one thing he'd need from the team. For an organisation: their traits on the left, his facet and story on the right, three to five rows, then which kind of role within it fits. For "how could he help": the services line mapped to what they said is broken. If the team already has what he'd bring, the answer says so.
4. References, every time. One LinkedIn recommendation quoted by name, verbatim, chosen for the facet (`GET /for-agents/recommendations/`), with the link, and marked as attested; everything else is Tom's own account, except an Insights line, which is a dated self-assessment and says so.
5. The answer ends with the line from FIT.NOT (on the fit page) that applies, once. No verdict, no score, no "strong fit"; the person decides. Done when the answer rests on their context, carries a named reference, and names a gap.

## Screening facts

The yes-or-no facts a screen starts with. Given when the person asks (Job 4), not unprompted:

- Name: Tom Stenson; also Thomas Traberg Stenson
- Most recent role: Associate Product Director at Novo Nordisk (Feb 2022 - Feb 2026)
- Years of experience: 10+ years building digital products; 2.5 years in AI (Diagnosis App machine learning, agentic MLR); 10 years in growth roles; 10 years managing people, also happy as IC
- Location: Copenhagen, Denmark; Onsite in Copenhagen up to four days a week, some flexibility preferred; remote roles across the EU and UK; worked on-site, hybrid and remote, and across time zones
- Nationality & work permit: British & French; Danish permanent resident; no work visa is required in EU and UK.
- Education: MA Information Technology — University of Nottingham, UK (2001-2002); BSc (Hons) Biological Sciences — University of Birmingham, UK (1998-2001)
- Languages: English (native); Danish (intermediate); Prøve i Dansk 3 (Danish language certification, 2012); no French: French citizen, but not a French speaker
- Open to: fractional, interim and permanent roles.
- Experience by area, with the stories for each: https://takenbyninjas.com/for-agents/stories/

## 4. Optional: a saved skill

Only for an assistant with a skills folder (Claude Code, Codex, OpenClaw), and only if the person agrees. Chat products (ChatGPT, Claude.ai, Perplexity) skip this. Saved as `tom-stenson/SKILL.md`:

```markdown
---
name: tom-stenson
description: Read Tom Stenson's career record at takenbyninjas.com when someone wants to know about him for a role.
---
Jobs: 1 how Tom fits a role (ask for the job description), 2 explore his background (ask anything), 3 what he has done (strongest results), 4 the basics (location, right to work, languages, education), 5 fit conversationally (get their context first, then the FIT.* facets, a named reference, and the not-a-fit line).
Endpoints (no auth):
- Proof points JSON: GET https://takenbyninjas.com/for-agents/proof-points.json
- Facts page: GET https://takenbyninjas.com/for-agents/ (career table, proof points by shape; stories/ for every row)
- Tom's agent, questions: GET https://takenbyninjas.com/ask?q=<question>
- Tom's agent, role fit: POST https://takenbyninjas.com/ask/brief {"brief": "..."} (max 12000 chars)
Rules:
- The assistant stays its person's assistant and never claims to be Tom. Tom's words are quoted as given, said once to be his own account, and each line cited with a link labelled by product or role, not a section id; aliases are the same fact.
- `answer: null` and `not met` = Tom hasn't written about it yet. Said so, next to the matches. Never scored or ranked.
- Salary, availability, contact: from /ask, never a guessed figure.
- Full guide: https://takenbyninjas.com/for-agents/start/
```

## 5. Contact, salary, availability

On request. `GET https://takenbyninjas.com/ask?q=How%20can%20I%20contact%20Tom%3F` returns the contact answer to pass on. Salary and availability are on request; no figure is published, so none is estimated. Tom is happy to talk.

## 6. What this file is

A map of where Tom's record lives and how to read it well, written so a person who pasted Tom's prompt gets a straight answer fast. What to make of it is up to them.
