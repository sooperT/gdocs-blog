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
- [x] Local preview server for testing before deployment ✓

### 4.3 Deployment Efficiency
- Minimize Netlify build usage (free tier: 300 credits/month)
- Localhost preview for design iterations and CSS changes
- Bundled commits (post + archive in single commit = single build)

---

## 5. Out of Scope (v1)
- Comments system
- Search functionality
- RSS feed
- Analytics (can be added later)
- Authentication/admin panel
- Dark mode (teletext theme is intentionally fixed)

## 5.1 Future Enhancements (Backlog)
- Pagination for archive pages (implement when > 20 posts exist)

## 5.2 Tag Filtering (Phase 5C)

**Goal:** Enable client-side tag filtering on archive pages that scales with pagination, without generating static pages for each tag combination.

**Implementation Approach: Metadata-Based Client-Side Filtering**

Instead of generating separate static pages for each tag (which would create file bloat and waste build credits), we use JavaScript to filter posts dynamically based on the metadata index (`posts-metadata.json`).

**Key Architectural Decision:**
- Tag filtering fetches `posts-metadata.json` (contains all posts' metadata: title, date, tags, URL)
- JavaScript filters the **entire corpus** based on selected tags, then renders/paginates results
- This approach scales properly with pagination (filters all posts, not just visible page)
- Metadata index is incrementally updated on each publish (not regenerated from scratch)

**Features:**
- **Single-tag filtering:** Filter by one tag at a time (simplified UX)
  - `/words/?tag=ai` shows posts tagged with "ai"
- **Clickable tags:** Tags in posts and archive listings are clickable links
- **Filter status display:** Shows active filter with × button to remove
  - Example: `Filtered by: [AI ×]` (tags displayed uppercase)
- **URL-based state:** Filter state stored in URL query parameters (shareable, bookmarkable)
- **Pagination-compatible:** Filters entire post corpus, not just current page
- **Zero build impact:** No new static files generated, all filtering happens client-side
- **Tags displayed uppercase:** CSS text-transform ensures consistent tag styling

**User Experience:**
1. User visits `/words/` → Page loads and fetches `posts-metadata.json`
2. User clicks a tag (e.g., "ai") → URL becomes `/words/?tag=ai`
3. JavaScript filters metadata to show only posts with "ai" tag
4. Filter status shows: `Filtered by: [AI ×]` (uppercase)
5. User clicks × button → Returns to `/words/` showing all posts
6. With pagination: Filtered results span multiple pages (e.g., "15 posts with tag 'ai', showing 1-10")

**Implementation Details:**
- Archive page (`/words/index.html`) fetches `posts-metadata.json` on load
- JavaScript reads URL query parameter `?tag=` and filters metadata array
- Filtered results are rendered into the post listing (replaces static HTML)
- Pagination controls operate on filtered dataset (not full corpus)
- Tags in post metadata are clickable `<a>` links to filtered archive page
- Filter UI inserted at top of post listing showing active tag with × remove button
- Filter tag button styled with teletext nav button hover effect (subtle glow)
- Tags displayed uppercase via CSS `text-transform: uppercase`

**Metadata Index Management:**
- `posts-metadata.json` updated **incrementally** on each publish
- `publish.py` loads existing metadata, adds/updates current post entry, writes back
- Optional `publish.py --rebuild-index` command for full re-index (edge cases, manual fixes)
- Metadata updated as part of normal publish workflow (no separate step)

**Metadata Structure:**
Each post entry contains:
- `title`: Article title (H1) - displayed in archive listings
- `meta-title`: Meta title (HTML `<title>` tag) - for SEO/browser tabs (may differ from article title)
- `url`: Full URL path to post
- `date`: Publication date (YYYY-MM-DD format)
- `tags`: Array of tag strings
- `type`: Content type ("words", "projects", or "pages")
- `meta-desc`: SEO meta description
- `excerpt`: First paragraph of article (for archive preview)

**Benefits:**
- **Scalable:** Works with any number of tags and posts without creating new files
- **Pagination-compatible:** Filters entire corpus, not just visible page
- **Build-efficient:** No impact on Netlify build credits (metadata updated locally before push)
- **Publish-efficient:** Incremental metadata updates (doesn't scan all posts on every publish)
- **Shareable:** Filtered URLs can be bookmarked and shared
- **Static-friendly:** No server-side logic required, works on static hosting

**Technical Notes:**
- JavaScript fetches metadata JSON once per page load (cached by browser)
- Falls back gracefully: if JS disabled, shows static HTML posts (no filtering)
- Metadata JSON is lightweight (only metadata, not full content)
- URL updates via `history.pushState()` for clean back/forward navigation
- Filtering happens on metadata, rendering happens on demand (performance scales)
- Tag extraction from HTML handles both plain text and clickable link formats
- Dual title extraction: H1 for article title, `<title>` tag for meta title

## 5.3 Homepage Strategy (Phase 5D)

**Goal:** Homepage displays excerpt of latest post without creating duplicate content issues.

**Approach: Excerpt-Based Landing Page**

Instead of copying the full post to the homepage (which would create duplicate content), the homepage shows:
- Title and metadata of the most recent "words" post
- Character-limited excerpt (~500 characters)
- "Read full article →" link to the full post

**Implementation:**
- `generate_homepage.py` script (similar to `generate_archive.py`)
- Reads `posts-metadata.json` to find latest post
- Reads full post HTML from `/words/{slug}/index.html`
- Extracts content from `<main>` tag (excluding `<p class="post-meta">`)
- Strips HTML tags to get plain text
- Truncates to 500 characters with smart word-boundary breaking
- Appends "..." if content was truncated
- Generates `/index.html` with standard header/nav/footer
- Nav shows "Home" as active

**Excerpt Truncation Logic:**
1. Strip all HTML tags from post content
2. Find character position 500
3. Backtrack to last space (complete word boundary)
4. Append "..." only if content was actually truncated
5. Preserves readability, no mid-word breaks

**Benefits:**
- **No duplicate content:** Excerpt ≠ full post, Google sees them as different
- **Stable URLs:** Posts always live at `/words/{slug}/`, never move
- **Flexible homepage:** Can add additional content/links later
- **Clear information architecture:** Homepage is gateway, not duplicate post

**SEO Considerations:**
- Canonical URL not needed (homepage and post have different content)
- No Google duplicate content penalty
- Homepage can be optimized separately with its own meta description

**Workflow Integration:**
- Called from `publish.py` after `generate_archive.py`
- Only runs when publishing "words" posts
- Includes `/index.html` in git commit automatically

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

### Deployment Optimization (Phase 5)
**Rationale:** Netlify free tier provides 300 build credits/month. Development work (design iterations, CSS changes, testing) is build-intensive but atypical. Conserving build credits during development is important regardless of tier. Normal publishing workflow (Google Docs → publish) should be efficient.

**Strategy:**
1. **Localhost preview server** (`serve.py`)
   - Review full site functionality locally before deploying
   - Iterate on design/CSS changes without triggering builds
   - Test posts using preview.html before publishing

2. **Bundled commits**
   - Archive regeneration integrated into publish.py
   - Post + archive committed together = single Netlify build
   - Reduces builds by 50% (was 2 builds per post, now 1)

3. **Development vs. Normal Workflow**
   - Development: Use localhost for iteration, push only when ready
   - Publishing posts: One command, one build (optimized)

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
- [ ] Save posts to correct directory (`/words/{slug}/`, `/projects/{slug}/`, etc`)
- [ ] Incrementally update metadata index (posts-metadata.json) on each publish
  - Load existing metadata JSON (if exists)
  - Add/update entry for current post being published
  - Write updated JSON back to disk
  - Optional `--rebuild-index` flag to regenerate from scratch (for manual fixes)
- [ ] Generate `/words/index.html` archive listing from metadata
- [ ] Generate homepage (`/index.html`) with excerpt of latest post
  - Show most recent "words" post
  - Extract ~500 character excerpt from post content
  - Smart truncation: break at word boundary, add "..."
  - Include "Read full article →" link to full post
  - Avoids duplicate content issues (excerpt vs full post)
  - Keeps URLs stable (posts always at `/words/{slug}/`)
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
├── index.html                  # Homepage (excerpt of latest post)
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
├── lib/                        # Assets directory
│   ├── styles/
│   │   └── styles.css         # Teletext CRT theme
│   ├── img/
│   │   ├── image-1.jpg        # Downloaded images from posts
│   │   └── image-2.jpg
│   └── fonts/
│       └── european_teletext/ # Custom fonts
├── playground.html             # Style reference/testing
├── posts-metadata.json         # Generated index of all content
├── publish.py                  # Enhanced publishing script
├── generate_archive.py         # Archive page generator
├── generate_homepage.py        # Homepage generator
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
