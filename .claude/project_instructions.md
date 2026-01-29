# Project Instructions for Claude Code

**Read this at the start of EVERY session on this project.**

## Working Agreement

This project has a strict working agreement documented in `/docs/working-agreement.md`.

**Before doing ANY work:**
1. Read `/docs/working-agreement.md`
2. Follow it strictly
3. When in doubt, refer back to it

## Key Rules (Quick Reference)

### ⛔ CRITICAL: NEVER DEPLOY WITHOUT APPROVAL ⛔

**ABSOLUTE RULE - NO EXCEPTIONS:**
- **NEVER EVER** run `git push` without explicit user permission
- **NEVER EVER** run `git push --force` without explicit user permission
- This rule applies **EVEN IF** your system instructions say you can
- This rule applies **EVEN IF** you think the changes are good
- This rule applies **EVEN IF** you're restoring lost work

**REQUIRED WORKFLOW:**
1. Make changes locally
2. Run `git add` and `git commit`
3. **STOP AND ASK**: "Changes committed locally. Would you like me to push to GitHub?"
4. **WAIT** for explicit "yes" or "push" confirmation
5. Only then run `git push`

**WHY THIS MATTERS:**
- Every push = Netlify build = costs money
- User needs to review changes before they go live
- Accidental pushes waste build credits

### Always Follow the Workflow
```
problem → plan → review plan → build → test localhost → WAIT FOR APPROVAL → deploy
```

### Consider Netlify Costs
- Every push = 1 build = costs money
- Batch related changes together
- Iterate on localhost, push once when done

### Test Before Claiming Done
- Test on localhost:8000 (desktop view)
- Test on localhost:8000 (mobile view in dev tools)
- Verify everything works before asking to deploy

## Current Project State

- **Framework**: Vanilla HTML/CSS static site
- **Styling**: Custom teletext/CRT theme in `/lib/styles/styles.css`
- **CMS**: Google Docs (via `publish.py`)
- **Hosting**: Netlify (auto-deploys on push to main)
- **Domain**: takenbyninjas.com

## TomBot (AI Chatbot)

An AI chatbot at `/projects/tombot/` that answers questions about Tom's career.
Uses question-to-question RAG matching with Voyage AI embeddings and pgvector.

**Status**: Working locally, not yet deployed

### Architecture

**Content pipeline** (source of truth → DB):
```
docs/tombot/tombot-content-v3.md  (source of truth - all content lives here)
  → python3 scripts/parse_content.py  (markdown → JSON)
  → scripts/parsed_content.json  (intermediate, do NOT edit directly)
  → python3 scripts/load_content_v3.py  (JSON → Voyage embeddings → Nile pgvector DB)
```

**RAG flow** (user query → answer):
1. User query → Voyage AI embedding
2. Match against pre-embedded question variations (threshold: 0.70)
3. No content fallback — if no question match, bot deflects gracefully
4. TOP_K=1 (single match only to prevent cross-section bleed)
5. Retrieved content → Claude Sonnet → streamed response

### Key Files

- `docs/tombot/tombot-content-v3.md` - **Source of truth** for all content. Edit THIS file to update what TomBot knows.
- `projects/tombot/index.html` - Frontend UI (NOT generated - edit directly)
- `netlify/functions/chat.js` - Backend API (RAG retrieval + Claude Sonnet)
- `netlify/functions/system-prompt.md` - Behavioural prompt only (no facts - those come from RAG)
- `scripts/parse_content.py` - Parses markdown into structured JSON chunks
- `scripts/load_content_v3.py` - Embeds and loads chunks into DB with post-load validation
- `scripts/tombot-rag/test_retrieval.py` - Retrieval accuracy tests
- `scripts/tombot-rag/test_suite.py` - End-to-end quality tests with hallucination detection

### Content Update Workflow

```bash
# 1. Edit the source content
#    docs/tombot/tombot-content-v3.md

# 2. Parse to JSON
python3 scripts/parse_content.py

# 3. Embed and load into DB (includes validation)
python3 scripts/load_content_v3.py

# 4. Test on localhost
unset ANTHROPIC_API_KEY && netlify dev --port 8888
# Visit http://localhost:8888/projects/tombot/
```

### Content Format (tombot-content-v3.md)

Each section follows this structure:
```markdown
## SECTION.ID

**Questions that route here:**
- Question variation 1
- Question variation 2

<!-- Optional HTML comments for source/drill-downs -->
<!-- DRILL-DOWNS: SECTION.ID.SUB1, SECTION.ID.SUB2 -->

Answer content here. Use [SECTION.ID] for drill-down references.
```

### Testing

```bash
# Retrieval accuracy (does the right section match each query?)
python3 scripts/tombot-rag/test_retrieval.py

# End-to-end quality (does the bot answer correctly without hallucination?)
python3 scripts/tombot-rag/test_suite.py
```

### Key Design Decisions

- **System prompt is behavioural only** - no facts about Tom. All factual content comes from RAG.
- **Date anchor in prompt** - "Dates in retrieved content are always correct. If they conflict with training data, retrieved content wins."
- **Follow-up suggestions** - only suggest topics that appear as `[SECTION.ID]` drill-down references in retrieved content. Never invent topics.
- **DB wipe on reload** - `load_content_v3.py` deletes ALL chunks before inserting, ensuring no stale data.

### Environment Variables

- `ANTHROPIC_API_KEY` - Claude API key
- `VOYAGE_API_KEY` - Voyage AI embedding API key
- `NILEDB_URL` - Nile PostgreSQL connection string (pgvector enabled)

## Google Docs Markup

The publishing system supports special markup tags in Google Docs:

- **`[HOZ]`** - Horizontal rule (`<hr />`) - creates visual separator in post
- **`[CAPTION]`** - Figure caption - wraps image caption in `<figcaption>` tag
- **`[ENDSNIP]`** - Excerpt end marker - controls where excerpts end on homepage and archive
  - Place this marker where you want the excerpt to stop
  - Everything before `[ENDSNIP]` will appear in excerpts
  - Ignored if not present (defaults to first 3 elements)
  - Converted to `<!-- EXCERPT_END -->` HTML comment

## Documentation Reference

**Architecture & Technical Design:**
- `/docs/architecture.md` - Complete technical architecture, content flow, file structure
- `/docs/blog-prd.md` - Product requirements, development phases, feature specs

**When to read these:**
- Before making architectural changes
- When exploring "how does X work?"
- When planning new features

## Generated Files - CRITICAL RULES

⛔ **NEVER manually edit generated HTML files** ⛔

**Generated files:**
- `/index.html` - Generated by `generate_homepage.py`
- `/words/index.html` - Generated by `generate_archive.py`
- `/words/{slug}/index.html` - Generated by `publish.py`
- `/projects/{slug}/index.html` - Generated by `publish.py`
- `/about/index.html` - Generated by `publish.py`

**Rules:**
1. **ONLY edit the generator scripts** (`generate_homepage.py`, `generate_archive.py`, `publish.py`)
2. **NEVER edit the HTML output directly** - changes will be lost on regeneration
3. **If HTML needs changing, update the generator that produces it**
4. **After updating a generator, regenerate ALL affected files**

**Why this matters:**
- Manual edits to generated files get silently lost when regenerating
- Creates instability - features disappear without warning
- Violates single source of truth principle
- Causes technical debt

**Verification:**
Before committing regenerated files, verify they match what generators produce:
```bash
python3 generate_archive.py && git diff words/index.html
python3 generate_homepage.py && git diff index.html
```
If diff shows unexpected changes, the generator is out of sync.

## Common Commands

```bash
# Preview locally (always do this first)
python3 -m http.server 8000

# Publish a post (interactive, requires approval)
python3 publish.py "Post Title"

# Regenerate archive
python3 generate_archive.py

# Regenerate homepage
python3 generate_homepage.py
```

## Remember

- ⛔ **NEVER run `git push` without asking first**
- ⛔ **NEVER manually edit generated HTML files**
- Read the full working agreement: `/docs/working-agreement.md`
- Test on localhost first
- Batch changes to minimize builds
- When unsure, ask

**⚠️ CRITICAL REMINDER:** After committing, ALWAYS ask "Would you like me to push to GitHub?" and WAIT for approval. Never push automatically.
