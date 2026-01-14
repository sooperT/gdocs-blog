# Project Instructions for Claude Code

**Read this at the start of EVERY session on this project.**

## Working Agreement

This project has a strict working agreement documented in `/docs/working-agreement.md`.

**Before doing ANY work:**
1. Read `/docs/working-agreement.md`
2. Follow it strictly
3. When in doubt, refer back to it

## Key Rules (Quick Reference)

### NEVER Deploy Without Approval
- **NEVER** run `git push` without explicit user permission
- Test everything on localhost first
- Always say "Ready to deploy?" and WAIT for approval

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

- Read the full working agreement: `/docs/working-agreement.md`
- Never push without approval
- Test on localhost first
- Batch changes to minimize builds
- When unsure, ask

**Following these rules protects the user's Netlify build credits and ensures quality.**
