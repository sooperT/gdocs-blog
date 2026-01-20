# takenbyninjas.com Blog

A static blog built with vanilla HTML/CSS, using Google Docs as a CMS.

## 🚨 IMPORTANT: Read This First

**Before working on this project, ALWAYS read:**
- `.claude/project_instructions.md` - Project overview and key rules
- `docs/working-agreement.md` - Development workflow (READ THIS!)

These documents contain critical information about:
- How the publishing workflow works
- Validation requirements before claiming "done"
- Deployment rules (NEVER push without approval)
- Testing procedures
- Cost considerations (Netlify builds)

## Quick Start

```bash
# Preview locally
python3 serve.py
# Opens http://localhost:8000

# Publish a post (interactive, requires approval)
python3 publish.py "Post Title"
```

## Project Structure

```
/
├── .claude/
│   ├── project_instructions.md  ← READ THIS FIRST
│   └── skills/
├── docs/
│   ├── working-agreement.md     ← READ THIS TOO
│   ├── architecture.md
│   └── blog-prd.md
├── words/                       ← Blog posts
├── projects/                    ← Portfolio items
├── lib/
│   ├── styles/styles.css       ← Main stylesheet
│   └── img/                    ← Downloaded images
├── publish.py                   ← Main publishing script
├── generate_archive.py
└── generate_homepage.py
```

## Documentation

- **[Project Instructions](.claude/project_instructions.md)** - Start here
- **[Working Agreement](docs/working-agreement.md)** - Development workflow rules
- **[Architecture](docs/architecture.md)** - Technical architecture
- **[Publishing Guide](.claude/skills/blog-publisher/docs/publishing.md)** - How to publish posts

## Publishing Workflow

1. Write post in Google Docs (in `09 Lab/Taken/words/` folder)
2. Run `python3 publish.py "Post Title"`
3. Review preview in browser
4. Type "yes" to publish
5. Script commits and pushes to GitHub
6. Netlify auto-deploys to takenbyninjas.com

## Key Rules

⛔ **NEVER run `git push` without explicit user approval**
✅ **ALWAYS test on localhost before claiming "done"**
✅ **ALWAYS verify actual output, never assume code changes work**
✅ **Follow the workflow:** plan → build → test → verify → approve → deploy

## Tech Stack

- **Framework**: Vanilla HTML/CSS (no build tools)
- **Styling**: Custom teletext/CRT theme
- **CMS**: Google Docs + Python publishing script
- **Hosting**: Netlify (auto-deploys on push to main)
- **Domain**: takenbyninjas.com

## Need Help?

Read the docs first:
1. `.claude/project_instructions.md`
2. `docs/working-agreement.md`
3. `docs/architecture.md`

When in doubt, ask before making changes.
