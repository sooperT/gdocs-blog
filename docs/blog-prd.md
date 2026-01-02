# Product Requirements Document: Flat File Blog

**Project Owner:** Product/Tech Professional
**Created:** November 11, 2025
**Last Updated:** January 2, 2026
**Status:** Phase 5 Planning - Multi-Post Architecture

---

## 1. Project Overview

### Purpose
Build a simple flat file blog to sharpen AI-assisted web development skills, focusing on modern tooling and deployment practices. The blog serves as a platform for sharing thoughts on product, systems thinking, and life, while re-establishing a long-running online identity (takenbyninjas.com, originally created in 2005).

### Goals
- Learn modern web development workflows with AI pair programming
- Deploy a live, publicly accessible blog at **takenbyninjas.com**
- Use Google Docs as CMS to write/edit posts in a natural workflow
- Create a modern evolution of the original 2005 portfolio/blog aesthetic
- Build foundation for future AI-assisted development projects

### Identity & Theme
- **Domain:** takenbyninjas.com (live since 2005, relaunched 2026)
- **Visual Theme:** Teletext/CRT retro aesthetic (evolution of 2005 design)
- **Brand Element:** Ninja imagery (callback to original site)
- **Voice:** "Modern behaviour, old soul" - contemporary blog UX with nostalgic design elements

---

## 2. Core Requirements

### 2.1 Content Management
- [x] **Google Docs as CMS** - write posts in natural workflow ✓
- [x] Sync/convert Google Docs to flat files (HTML) ✓
- [x] All source files version-controlled in GitHub repository ✓
- [x] Simple file-based structure (no database) ✓
- [ ] Support for post metadata via frontmatter (date, tags, SEO description, custom URL)
- [ ] Multi-post support (words, projects, pages)
- [ ] Archive/listing pages with pagination

### 2.2 Technical Stack
**Inspiration:** https://thenanyu.com / https://github.com/thenanyu/sss

**Decided:**
- [x] Deployment: **Netlify** ✓
- [x] CMS: **Google Docs** ✓
- [x] Framework: **Vanilla HTML/CSS** (keep it simple like inspiration) ✓
- [x] Approach: **Incremental phases** - Hello World → Manual Post → Automation ✓
- [x] Sync method: **GitHub Actions + Google Docs API** (Phase 3) ✓

**Decided:**
- [x] Styling approach: **Vanilla CSS with custom teletext/CRT theme** ✓
- [x] Repository name: **gdocs-blog** ✓
- [x] Custom domain: **takenbyninjas.com** ✓ (configured and live)

### 2.3 Deployment & Hosting
- [x] Live website publicly accessible ✓
- [x] GitHub repository as single source of truth ✓
- [x] Automated deployment on push to main branch ✓
- [x] Custom domain: **takenbyninjas.com** ✓

### 2.4 Why GitHub?
**Rationale for including GitHub in the workflow:**
- **Learn industry-standard workflows** - Practice git operations (commit, push, pull) used in professional development
- **Enable automation** - GitHub Actions provide CI/CD pipeline for Google Docs sync
- **Version control** - Full history of all code and generated content, ability to rollback
- **Separation of concerns** - Source code (GitHub) vs content authoring (Google Docs)
- **Transferable skills** - Foundation for future AI-assisted development projects
- **Developer mindset** - Part of "skilling up like a developer" learning goal

---

## 3. Functional Requirements

### 3.1 Blog Features (MVP)
- [ ] Homepage shows latest post (modern blog pattern)
- [x] Individual blog post pages ✓
- [ ] Persistent header with identity (TAKEN logo + ninja + tagline)
- [ ] Site navigation (Words / Projects / About)
- [ ] Site footer (AI disclaimer)
- [x] Responsive design (mobile + desktop) ✓

### 3.2 Content Features
- [x] HTML rendering from Google Docs ✓ (chose HTML over Markdown)
- [x] Code block styling ready in CSS ✓
- [ ] Post metadata display (date, tags)
- [ ] Three content types: **words** (blog posts), **projects** (portfolio), **pages** (about)
- [ ] Archive/listing page for words (`/words/`)
- [ ] Projects showcase page (`/projects/`) - stealth mode initially
- [ ] About page (`/about/`) - sourced from Google Docs

---

## 4. Non-Functional Requirements

### 4.1 Performance
- [x] Fast load times (< 2 seconds) ✓ (static HTML)
- [x] Static generation for optimal performance ✓

### 4.2 Development Experience
- [x] Easy to add new posts via `python3 publish.py "Post Title"` ✓
- [x] Local development environment ✓
- [x] Clear documentation for future reference ✓ (see /docs)

---

## 5. Out of Scope (v1)
- Comments system
- Search functionality
- RSS feed
- Analytics (can be added later)
- Authentication/admin panel
- Categories/tags filtering (tags are metadata only, no filtering UI)
- Dark mode (teletext theme is intentionally fixed)

---

## 6. Success Criteria
- [x] Live blog accessible via custom domain (takenbyninjas.com) ✓
- [x] Can add new post via publish.py and auto-deploy ✓
- [x] Gained practical experience with chosen stack ✓
- [x] Documented learning and setup process ✓
- [ ] Multi-post architecture with three content types (words/projects/pages)
- [ ] Persistent site header/nav/footer across all pages
- [ ] Archive listing page for words
- [ ] At least 2-3 test posts published
- [ ] Working navigation between homepage, archive, and individual posts

---

## 7. Decisions Made

### Design & Architecture
1. ~~**Styling approach:** Vanilla CSS or use a minimal framework?~~ → **Decided: Custom teletext/CRT theme** ✓
2. ~~**Repository name:** What to call it?~~ → **Decided: gdocs-blog** ✓
3. ~~**Custom domain:** Do we need one, or use Netlify subdomain?~~ → **Decided: takenbyninjas.com** ✓
4. ~~**Post metadata:** How to handle (frontmatter, separate file, embedded in Doc)?~~ → **Decided: Frontmatter in Google Docs** ✓
5. ~~**Multi-post support:** How to handle post archive/listing page?~~ → **Decided: Multi-post architecture (Phase 5)** ✓

### Site Structure (Phase 5)
- **Homepage pattern:** Latest post from /words/ (modern blog UX) + persistent header/nav
- **Content taxonomy:** Three types - words (blog), projects (portfolio), pages (static)
- **URL structure:**
  - `/` - Homepage (latest post)
  - `/words/` - Archive listing
  - `/words/{slug}/` - Individual post
  - `/projects/` - Projects showcase (stealth mode initially)
  - `/projects/{slug}/` - Individual project
  - `/about/` - About page
- **Custom URLs:** Set via frontmatter `url:` field (full SEO control)
- **Navigation:** Persistent header/nav on all pages (Words / Projects / About)
- **Footer:** Simple AI disclaimer on all pages

### Google Drive Organization
- **Folder structure mirrors site:**
  - `My Drive/Lab/Blog posts/words/` - Blog posts
  - `My Drive/Lab/Blog posts/projects/` - Project pages
  - `My Drive/Lab/Blog posts/pages/` - Static pages (about, etc.)

### Metadata Format
- **Frontmatter in Google Docs:**
  ```
  ---
  type: words
  url: custom-slug-here
  date: 2026-01-02
  meta-desc: SEO description
  tags: ai, product, systems-thinking
  ---
  ```

### Design Elements
- **Header:** TAKEN logo + small ninja icon + tagline (vertically shallow, ~100-150px max)
- **Tagline:** "Words on product, systems thinking and life."
- **Nav style:** Teletext-themed buttons/links
- **Footer:** "Code created with AI — Words are my own"
- **Ninja placement:** Small icon in header (not homepage hero)

---

## 8. Development Approach

**Philosophy:** Build like an engineer - incremental, automated, tested end-to-end at each phase.

### Phase 1: Hello World (Validate Pipeline) ✅ COMPLETE
**Goal:** Get the full deployment pipeline working with minimal code

- [x] Create basic `index.html` ✓
- [x] Initialize GitHub repository ✓
- [x] Push to GitHub ✓
- [x] Connect GitHub repo to Netlify ✓
- [x] Verify live deployment ✓
- [x] Test: Change file → commit → auto-deploy ✓

**Success:** Live website that auto-deploys on git push ✅

### Phase 2: Manual Blog Post (Validate Structure) ✅ COMPLETE
**Goal:** Add one blog post manually to validate site structure

- [x] Create simple blog post page ✓ (index.html serves as post page)
- [ ] Add post listing to homepage (skipped - single post for now)
- [ ] Implement basic navigation (not yet needed)
- [x] Style with custom teletext/CRT theme ✓ (exceeded expectations!)
- [x] Push and deploy ✓

**Success:** Working blog with visual theme, looks amazing ✅

### Phase 3: Google Docs Integration (Automate Content) ✅ COMPLETE
**Goal:** Build automation to sync Google Docs → GitHub

- [x] Set up Google Docs API access ✓ (OAuth2 with Drive + Docs APIs)
- [x] Build conversion script (Docs → HTML) ✓ (`publish.py`)
- [x] Test with one document ✓ ("My first blog post")
- [x] Configure trigger: on-demand via CLI ✓
- [x] Document the "publish" workflow ✓

**Note:** Chose local Python script over GitHub Actions for simpler workflow.

**Success:** Write in Google Docs → run publish.py → auto-appears on blog ✅

### Phase 4: Polish & Domain Setup ✅ COMPLETE
- [x] Improve styling ✓ (teletext CRT theme complete)
- [x] Configure custom domain ✓ (takenbyninjas.com live)
- [x] Create style playground ✓ (playground.html for testing theme)

**Success:** Beautiful teletext theme + custom domain live ✅

### Phase 5: Multi-Post Architecture ⏳ CURRENT
**Goal:** Transform single-post page into full blog with multiple content types

**Philosophy:** Design first, then wire up the engine
- Part A: Build static prototype (clickable mockups, test design)
- Part B: Enhance publishing engine (automate multi-post workflow)

**Part A: Static Prototype Design** (Do This First)
- [ ] Update playground.html with new components (header/nav/footer/listings)
- [ ] Enhance styles.css with header/nav/footer styling
- [ ] Update individual post template (add header/nav/footer to existing working template)
- [ ] Re-publish existing post to test new layout
- [ ] Build static mock: `/words/index.html` (archive listing with 2-3 mock posts)
- [ ] Build static mock: `/projects/index.html` (stealth ninja placeholder)
- [ ] Build static mock: `/about/index.html` (about page content)
- [ ] Test navigation flow between all pages
- [ ] Iterate on design until approved

**Part B: Publishing Engine Enhancement** (Do This Second - After Design Approval)
- [ ] Parse frontmatter from Google Docs (type, url, date, meta-desc, tags)
- [ ] Detect content type from Google Drive folder location
- [ ] Generate URL slug from `url:` frontmatter field
- [ ] Save posts to correct directory (`/words/{slug}/`, `/projects/{slug}/`, etc.)
- [ ] Build metadata index (posts-metadata.json) tracking all content
- [ ] Generate `/words/index.html` archive listing from metadata
- [ ] Auto-copy latest `/words/` post to root `/index.html`
- [ ] Update git commit messages to include content type
- [ ] Support publishing pages (about, etc.) from `pages/` folder

**Success Criteria:**
- [ ] Persistent header/nav/footer on all pages
- [ ] Can publish posts to `/words/` via `publish.py "Post Title"`
- [ ] Can publish about page via `publish.py "About"`
- [ ] Homepage automatically shows latest post
- [ ] `/words/` shows archive listing of all posts
- [ ] Navigation works between homepage, archive, and individual posts
- [ ] Projects page shows stealth ninja placeholder
- [ ] At least 2-3 test posts published

---

## 9. Technical Architecture

### Content Flow
```
Google Docs (CMS)
Write in: /words/, /projects/, /pages/ folders
    ↓
Local publish.py script
    ↓
Converts Doc → HTML + parses frontmatter
    ↓
Saves to appropriate directory structure
    ↓
Git commit & push to GitHub
    ↓
Netlify auto-deploys (< 30 seconds)
    ↓
Live Website (takenbyninjas.com)
```

### Repository Structure (Phase 5)
```
/
├── index.html                  # Homepage (auto-copy of latest /words/ post)
├── words/
│   ├── index.html             # Archive listing (generated)
│   ├── first-post/
│   │   └── index.html         # Individual post
│   └── second-post/
│       └── index.html         # Individual post
├── projects/
│   ├── index.html             # Projects showcase (stealth mode)
│   └── project-slug/
│       └── index.html         # Individual project
├── about/
│   └── index.html             # About page (from Google Doc)
├── styles.css                  # Teletext CRT theme
├── playground.html             # Style reference/testing
├── posts-metadata.json         # Generated index of all content
├── publish.py                  # Enhanced publishing script
├── docs/                       # Documentation
│   ├── blog-prd.md
│   └── architecture.md
└── .gitignore                  # Protects credentials
```

### Google Drive Structure
```
My Drive/
  └── Lab/
      └── Blog posts/          # Parent folder (BLOG_FOLDER_PATH)
          ├── words/           # Blog posts
          │   ├── My first blog post
          │   ├── Second post title
          │   └── ...
          ├── projects/        # Portfolio projects
          │   └── (empty for now)
          └── pages/           # Static pages
              └── About
```

### Page Templates

All pages share common structure:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{Page Title}</title>
    <meta name="description" content="{meta-desc from frontmatter}">
    <link rel="stylesheet" href="/styles.css">
</head>
<body>
    <div class="crt-overlay"></div>

    <!-- HEADER: Appears on all pages -->
    <header class="site-header">
        <div class="identity">
            <h1 class="logo">TAKEN</h1>
            <div class="ninja-icon">[ninja graphic]</div>
            <p class="tagline">Words on product, systems thinking and life.</p>
        </div>
    </header>

    <!-- NAV: Appears on all pages -->
    <nav class="site-nav">
        <a href="/words/">Words</a>
        <a href="/projects/">Projects</a>
        <a href="/about/">About</a>
    </nav>

    <!-- MAIN: Content area (varies by page type) -->
    <main>
        {Page-specific content here}
    </main>

    <!-- FOOTER: Appears on all pages -->
    <footer class="site-footer">
        <p>Code created with AI — Words are my own</p>
    </footer>
</body>
</html>
```

### Frontmatter Parsing

Google Docs contain frontmatter at the top:

```
---
type: words
url: my-custom-slug
date: 2026-01-02
meta-desc: A brief description for SEO
tags: ai, product, systems-thinking
---

# Post Title

Content starts here...
```

`publish.py` parses this to:
- Determine content type and target directory
- Generate canonical URL
- Set SEO metadata
- Extract tags for metadata index
- Set publish date

---

## 10. Next Steps (Current Phase: 5A - Static Prototype)

**Immediate actions for Part A (Design First):**
1. [ ] Update `playground.html` with new components:
   - Site header (TAKEN + ninja + tagline)
   - Site navigation (Words / Projects / About)
   - Site footer (AI disclaimer)
   - Post metadata display (date, tags)
   - Archive listing layout (multiple posts)
   - Pagination controls

2. [ ] Enhance `styles.css` with styling for:
   - `.site-header` - Vertically shallow (100-150px max)
   - `.logo` - Large yellow "TAKEN" in teletext style
   - `.ninja-icon` - Small ninja graphic placement
   - `.tagline` - Subtitle styling
   - `.site-nav` - Teletext-themed navigation
   - `.site-footer` - Simple footer styling
   - `.post-meta` - Date/tags display
   - `.post-listing` - Archive page layout
   - `.pagination` - Navigation controls

3. [ ] Update individual post template in `publish.py`:
   - Add header/nav/footer to existing template
   - Keep existing `<main>` content generation
   - Re-publish "My first blog post" to test

4. [ ] Build static mockups:
   - `/words/index.html` - Archive listing (2-3 mock posts)
   - `/projects/index.html` - Stealth ninja placeholder
   - `/about/index.html` - About page content

5. [ ] Test and iterate:
   - View all pages live on takenbyninjas.com
   - Test navigation flow
   - Verify header stays shallow (doesn't push content below fold)
   - Approve design before moving to Part B

**Part B actions (After Design Approval):**
- Enhance `publish.py` with frontmatter parsing
- Build metadata index generation
- Auto-generate archive pages
- Auto-copy latest post to root

---

## 11. Design Philosophy & Constraints

### Visual Design Principles
- **Modern behaviour, old soul** - Contemporary UX patterns with nostalgic aesthetics
- **Identity without delay** - Header establishes voice but never pushes content below fold
- **Restraint over dominance** - Retro elements signal personality, don't overwhelm
- **Content leads** - Design supports reading, doesn't compete with it

### Header Design Constraints (Critical)
- **Maximum height:** 100-150px on desktop
- **No hero sections** - Header is an identity strip, not a landing page
- **Persistent across all pages** - Same header everywhere builds consistency
- **Vertically shallow** - First paragraph of content must be above fold on desktop

### Navigation Philosophy
- **Zero-friction reading** - Homepage = latest post (modern blog pattern)
- **Clear wayfinding** - Three top-level sections (Words / Projects / About)
- **Deliberate visual callbacks** - Ninja imagery in header, not obligatory on every page
- **Clean separation** - Archive at `/words/`, individual posts at `/words/{slug}/`

### Content Taxonomy
- **Words** - Blog posts about AI, product, systems thinking, life
- **Projects** - Portfolio showcases (stealth mode initially)
- **Pages** - Static content (about, etc.)

### Why This Matters
This is not nostalgia for its own sake. The site:
- Reclaims a long-running identity (takenbyninjas.com since 2005)
- Uses modern delivery mechanics (Google Docs CMS, git, Netlify)
- Separates voice from content (persistent header + content-first pages)
- Designs for clarity rather than trend compliance

"If you do this well, it will not feel like a 'retro blog'. It will feel like someone who has been thinking in public for a very long time, and finally has the tools to do it cleanly."

---

## Notes
- **Incremental approach:** Ship each phase before moving to next
- **Design first, engine second:** Validate UX before building automation (Phase 5 philosophy)
- **Automate pain:** Script anything repeated more than twice
- **Learn by doing:** Focus on practical skills over perfect architecture
- **Document as you go:** Capture learnings for future reference
- **Preserve what works:** Individual post publishing already works, don't break it
