# Technical Architecture

**Last Updated:** December 28, 2025

---

## Overview

gdocs-blog is a flat-file blog that uses **Google Docs as a CMS**. Content flows from Google Docs through a Python publishing script to a static HTML site deployed on Netlify.

---

## System Diagram

```
┌─────────────────┐
│   Google Docs   │  ← You write here
│  (Lab/Blog posts)│
└────────┬────────┘
         │
         │ Google Docs API
         ▼
┌─────────────────┐
│   publish.py    │  ← Converts Doc → HTML
│  (local script) │
└────────┬────────┘
         │
         │ git commit & push
         ▼
┌─────────────────┐
│     GitHub      │  ← Source of truth
│   (gdocs-blog)  │
└────────┬────────┘
         │
         │ webhook trigger
         ▼
┌─────────────────┐
│    Netlify      │  ← Auto-deploys
│   (hosting)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Live Blog     │  ← Readers see this
│  (public URL)   │
└─────────────────┘
```

---

## Publishing Workflow

### How to Publish a Post

```bash
python3 publish.py "My Post Title"
```

### What Happens

1. **Authentication** - Script authenticates with Google via OAuth2
2. **Find Document** - Searches for the doc in `Lab/Blog posts` folder on Drive
3. **Fetch Content** - Retrieves document content via Google Docs API
4. **Convert to HTML** - Transforms Google Doc structure to semantic HTML
5. **Preview** - Opens `preview.html` in browser for review
6. **Approval** - You confirm or cancel
7. **Publish** - Saves to `index.html`, commits, and pushes to GitHub
8. **Deploy** - Netlify automatically deploys the update

---

## File Structure

```
gdocs-blog/
├── docs/                    # Documentation
│   ├── architecture.md      # This file
│   └── blog-prd.md          # Product requirements
│
├── index.html               # The published blog post
├── styles.css               # Teletext CRT theme
├── playground.html          # CSS style reference
│
├── publish.py               # Main publishing script
├── test_gdocs.py            # API testing utility
│
├── client_secret_*.json     # Google OAuth credentials (gitignored)
├── token.json               # Cached auth token (gitignored)
│
├── .gitignore               # Protects credentials
└── LICENSE                  # MIT
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **CMS** | Google Docs | Write and edit posts naturally |
| **API** | Google Drive + Docs APIs | Fetch document content |
| **Script** | Python 3 | Convert and publish |
| **Frontend** | Vanilla HTML/CSS | No framework overhead |
| **Styling** | Custom CSS | Teletext/CRT retro theme |
| **Version Control** | Git + GitHub | Track changes, trigger deploys |
| **Hosting** | Netlify | Free static hosting with auto-deploy |

---

## Google Docs Integration

### APIs Used

- **Google Drive API v3** - Navigate folders, find documents
- **Google Docs API v1** - Read document content and structure

### Authentication

- OAuth 2.0 with offline access
- Credentials stored in `client_secret_*.json` (from Google Cloud Console)
- Token cached in `token.json` for subsequent runs

### Document Location

Posts must be in: `My Drive / Lab / Blog posts`

---

## HTML Conversion

### Style Mapping

| Google Docs Style | HTML Element |
|-------------------|--------------|
| TITLE | `<h1>` |
| HEADING_1 | `<h2>` |
| HEADING_2 | `<h3>` |
| HEADING_3 | `<h4>` |
| NORMAL_TEXT | `<p>` |

### Text Formatting

| Google Docs | HTML |
|-------------|------|
| Bold | `<strong>` |
| Italic | `<em>` |
| Link | `<a href="...">` |

---

## Teletext CRT Theme

The visual design mimics 1980s teletext/CRT monitors:

### Features
- Monospace typography (Courier New)
- Neon color palette (green, cyan, yellow, magenta)
- CRT effects: scanlines, phosphor glow, flicker
- Screen artifacts: vignette, dust, curvature

### Color Scheme
```css
--bg-color: #000000;      /* Black background */
--text-color: #00FF00;    /* Green text */
--heading-color: #00FFFF; /* Cyan headings */
--link-color: #00FFFF;    /* Cyan links */
--code-color: #FFFF00;    /* Yellow code */
```

### Reference
See `playground.html` for all available styles.

---

## Deployment

### Netlify Configuration

- **Build command:** None (static files)
- **Publish directory:** `/` (root)
- **Deploy trigger:** Push to `main` branch

### Deploy Flow

```
git push origin main
    ↓
GitHub webhook notifies Netlify
    ↓
Netlify pulls latest code
    ↓
Site goes live (usually < 30 seconds)
```

---

## Current Limitations

1. **Single post only** - `index.html` is overwritten each publish
2. **No post archive** - No listing of multiple posts
3. **No metadata** - No dates, tags, or reading time
4. **Manual trigger** - Must run `publish.py` locally

---

## Future Improvements

- [ ] Multi-post support with `/posts/` directory
- [ ] Homepage with post listing
- [ ] Post metadata (date, reading time, tags)
- [ ] RSS feed generation
- [ ] Custom domain
