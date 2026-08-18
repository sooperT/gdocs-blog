# takenbyninjas.com

Static blog published from Google Docs, plus TomBot — a RAG chatbot about
Tom's career. Vanilla HTML/CSS with a CRT/teletext theme, hosted on Netlify.

## 🚨 Read this first

All project rules, architecture, and ways of working live in
**[CLAUDE.md](CLAUDE.md)** — the single source of truth. Key rules:

- ⛔ Never `git push` without explicit approval (every push = a Netlify build)
- ✅ Test on localhost before claiming "done"
- ✅ Verify actual output; never assume code changes work

## Quick start

```bash
# Preview locally
npx http-server -p 8000

# Publish a post (interactive — preview + approval)
python3 publish.py "Post Title"

# TomBot locally
unset ANTHROPIC_API_KEY && netlify dev --port 8888
```

## Project structure

```
/
├── CLAUDE.md                    ← Rules + architecture (start here)
├── publish.py                   ← Google Docs → HTML publishing
├── generate_homepage.py         ← Builds index.html
├── generate_archive.py          ← Builds words/index.html
├── pylib/                       ← Templates + shared config
├── posts-metadata.json          ← Source of truth for posts
├── words/                       ← Blog posts (generated)
├── projects/tombot/             ← TomBot frontend (hand-edited)
├── netlify/functions/           ← TomBot backend (RAG + Claude)
├── scripts/                     ← TomBot content pipeline
├── lib/
│   ├── styles/styles.css        ← All CSS
│   └── img/                     ← Images
└── docs/                        ← Private docs (gitignored)
```

## Publishing workflow

1. Write post in Google Docs
2. Run `python3 publish.py "Post Title"`
3. Review preview in browser
4. Type "yes" to publish
5. Script commits; push (with approval) → Netlify deploys to takenbyninjas.com

## Tech stack

- **Blog**: Vanilla HTML/CSS, Python publish pipeline, Google Docs as CMS
- **TomBot**: Netlify Function (Node.js), Claude, Voyage AI embeddings, Nile pgvector
- **Hosting**: Netlify (auto-deploys on push to main)
- **Domain**: takenbyninjas.com
