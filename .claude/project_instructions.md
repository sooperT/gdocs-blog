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

## Documentation Reference

**Architecture & Technical Design:**
- `/docs/architecture.md` - Complete technical architecture, content flow, file structure
- `/docs/blog-prd.md` - Product requirements, development phases, feature specs

**When to read these:**
- Before making architectural changes
- When exploring "how does X work?"
- When planning new features

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
- Read the full working agreement: `/docs/working-agreement.md`
- Test on localhost first
- Batch changes to minimize builds
- When unsure, ask

**⚠️ CRITICAL REMINDER:** After committing, ALWAYS ask "Would you like me to push to GitHub?" and WAIT for approval. Never push automatically.
