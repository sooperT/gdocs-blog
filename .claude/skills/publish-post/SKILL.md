---
name: publish-post
description: Publish or update a takenbyninjas.com blog post from its Google Doc — local draft loop, QA checklist, and push protocol. Use whenever Tom asks to publish, republish, update, or draft a post, or to "try now" after a Doc edit.
---

# Publish a post from Google Docs

The post's source of truth is a Google Doc in Drive `Taken/words/` (pages live in `Taken/pages/` — but note `about` is hand-maintained, NEVER republish it). You have read-only Doc access: content fixes happen in the Doc (Tom's job), pipeline fixes happen in `publish.py` (your job). When output looks wrong but the Doc looks right to Tom, debug the Doc's API structure before asking him to change anything — the pipeline should interpret intent (see CLAUDE.md "Google Docs markup").

## Local draft loop (never pushes)

```bash
python3 scripts/publish_local.py "doc-name"
```

- The wrapper answers publish.py's prompts by reading their text, not by counting them: "structural errors" → yes (false-positive validator), "publish to blog" → yes (writes local files), "commit and push" → **no**, always. Anything unrecognised gets "no" and is flagged on stderr.
- **Never** pipe blind answers (`printf "yes\nyes\nno"`) into `publish.py`. The structural-errors prompt is conditional — when it doesn't fire the answers shift up one and a "yes" lands on "commit and push". That has pushed to main unapproved before.
- The run also regenerates homepage, archive, sitemap, and posts-metadata.json locally.
- If Google auth fails with `invalid_grant`: delete `token.json`, then Tom must run `python3 publish.py "doc-name"` in his own terminal to re-auth (browser consent). Don't attempt auth yourself.
- To find/inspect the Doc: Drive MCP `search_files` / `read_file_content`; for structure bugs (styles, soft returns, image positions), dump paragraphs via the Docs API using `publish.py`'s own auth helpers.

## QA checklist — run after EVERY publish, before showing Tom

1. `<title>` is the Doc's `browser-title` (not the h1 fallback) and `<meta name="description">` is present.
2. Canonical tag present with lowercase URL; slug/folder lowercase.
3. Tags correct — no stray punctuation from the Doc's tags line.
4. All contact/CTA links are real links (mailto included).
5. Image order matches the Doc; hero at top if the Doc has it there; homepage excerpt image links to the post.
6. `[ENDSNIP]` respected: homepage shows hero + intro + "Read full article →", no marker text leaking, no junk/empty `<p>` fragments.
7. **Balance pass**: screenshot the FULL post page and the homepage, desktop and mobile. Judge spacing rhythm, gaps, and grouping as a whole layout — not just the changed part. Fix imbalance before presenting.

## Push protocol

- Batch changes; push once, only on Tom's explicit go.
- `git add -A -- . ':!mockups'` — never commit `mockups/` or `token.json*`.
- After push, poll the live site for a change marker (background `until curl ... | grep -q ...`) and confirm deployed.

## Taking a post down (e.g. temporary posts)

Remove its entry from `posts-metadata.json`, delete `words/{slug}/`, run `generate_homepage.py`, `generate_archive.py`, `generate_sitemap.py`, verify locally, then commit/push on approval.
