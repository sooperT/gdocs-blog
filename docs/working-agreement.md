# Blog Development Working Agreement

**Version**: 1.0
**Effective**: 2026-01-07
**Participants**: Claude (AI), Tom (Human)
**Project**: takenbyninjas.com Blog

This document establishes the contract for how we work together on this blog. These are not suggestions—they are requirements.

---

## Development Workflow

```
problem → plan → review plan → build → test localhost → WAIT FOR APPROVAL → deploy
```

### Required Steps (No Shortcuts)

1. **Understand the problem**
   - Read the request carefully
   - Ask clarifying questions if unclear
   - Confirm understanding before proceeding

2. **Make a plan**
   - Outline approach
   - Identify files that need changes
   - Consider Netlify build impact
   - Flag any architectural concerns

3. **Review the plan**
   - Present plan to user
   - Wait for approval
   - Adjust based on feedback

4. **Build**
   - Make code changes
   - Follow architectural principles (see below)
   - Document changes as you go

5. **Test on localhost**
   - Run `serve.py` or equivalent
   - Test desktop view
   - Test mobile view (dev tools)
   - Verify all functionality

6. **Show work**
   - Explain what changed
   - Show where it changed (file:line)
   - Confirm it works on localhost

7. **WAIT FOR APPROVAL**
   - Never skip this step
   - Never assume approval
   - Explicit "yes" required

8. **Deploy**
   - Only after explicit approval
   - Commit with clear message
   - Push to trigger Netlify build

**All steps required. Every time. No exceptions.**

---

## Deployment Rules (CRITICAL)

### ❌ NEVER Deploy Without Explicit Permission

**Prohibited commands without user approval:**
```bash
git push
git commit && git push
# ANY command that pushes to GitHub
```

**Required instead:**
1. Make changes
2. Test on localhost
3. Show user what changed
4. Say: "Changes ready. Should I commit and deploy?"
5. WAIT for explicit "yes" / "deploy" / "push"

**Cost context:** Every push triggers Netlify build = costs money

### ✅ Default Workflow

```
edit code → test localhost → show user → WAIT FOR APPROVAL → commit → WAIT FOR APPROVAL → push
```

**Never combine steps without permission**

### Exceptions (When Push IS Allowed)

**Only when user explicitly says:**
- "deploy"
- "push"
- "publish and deploy"
- "commit and push"
- "go ahead"

**Still prohibited:**
- "looks good" (doesn't mean deploy)
- "nice" (doesn't mean deploy)
- Silence (doesn't mean deploy)

---

## Architectural Principles

### Netlify Build Optimization

**Goal:** Minimize build usage while maintaining velocity

**Principles:**

1. **Batch changes**
   - Multiple CSS tweaks → one commit
   - Multiple bug fixes → one commit
   - Related changes → bundled together

2. **Smart regeneration**
   - Archive + homepage regeneration happens in publish.py (bundled)
   - Don't regenerate files unless content changed
   - Don't commit unchanged files

3. **Efficient publishing**
   - Post + archive + homepage + metadata in single commit
   - Images downloaded once, not re-downloaded on rebuild
   - Static assets served from /lib/ (cached by CDN)

4. **Local iteration**
   - CSS changes: iterate on localhost until perfect
   - Design work: use localhost preview
   - Only push when truly ready

**Bad patterns to avoid:**
- Push → see issue → push fix → see another issue → push fix (3 builds)
- Generate files that didn't change
- Commit files with no actual diff

**Good patterns:**
- Fix 3 CSS issues → test → push once (1 build)
- Batch related work into single deploy
- Preview everything locally first

### Static Site Architecture

**Principles:**

1. **Generated files are deterministic**
   - Same input = same output
   - No timestamps unless part of content
   - Reproducible builds

2. **Assets organized for caching**
   - `/lib/styles/` - CSS (versioned in path if needed)
   - `/lib/img/` - Images (immutable once published)
   - `/lib/fonts/` - Fonts (never change)

3. **Metadata drives generation**
   - `posts-metadata.json` is source of truth
   - Archive reads metadata (not files)
   - Homepage reads metadata (not files)

4. **Incremental updates**
   - Publishing one post updates its metadata entry
   - Doesn't scan entire filesystem
   - Doesn't regenerate unchanged pages

### Code Quality

**Principles:**

1. **Read before write**
   - Never guess file contents
   - Read existing code before modifying
   - Understand patterns before adding new code

2. **Test before claim**
   - "It works" requires localhost verification
   - Mobile and desktop both tested
   - No speculation, only facts

3. **Document changes**
   - Clear commit messages
   - Update PRD when architecture changes
   - Leave code better than you found it

---

## Code Changes

### Before Making Changes

1. **Understand the ask** - If unclear, ask
2. **Make a plan** - For non-trivial changes, outline approach
3. **Review the plan** - Get user approval
4. **Make changes** - Follow architectural principles
5. **Test locally first** - Use localhost:8000
6. **Document what you changed** - In commit message
7. **Wait for approval** - Before committing/deploying

### CSS/Styling Changes

**Required workflow:**
1. Read current CSS to understand structure
2. Plan the change (what selectors, what properties)
3. Make change to `/lib/styles/styles.css`
4. Test on localhost (desktop + mobile)
5. Show user the change
6. Wait for approval before committing

**Never:**
- Push CSS changes immediately
- Assume "looks good" means deploy
- Make multiple rounds of styling changes in one session without checking in

### Publishing Posts

**Standard workflow (always use this unless explicitly told otherwise):**
1. Run `python3 publish.py "Post Name"` (WITHOUT echo "yes")
2. Script generates preview.html and opens in browser
3. User reviews preview in browser
4. User can make edits to the Google Doc if needed
5. Script waits for user input (yes/no)
6. User types "yes" when satisfied
7. Script publishes, commits, and pushes

**Why this matters:**
- Saves Netlify build credits (300/month limit)
- Ensures quality before publication
- Allows user to catch issues before they go live
- User reviews in actual browser, not just CLI output

**When user says "publish to preview":**
- Run `python3 publish.py "Post Name"` (interactive mode)
- Wait for user to review and approve
- User will type "yes" in terminal when ready

**When user explicitly says "auto-publish" or "skip preview":**
- Only then use `echo "yes" | python3 publish.py "Post Name"`
- This should be rare - user must explicitly request it
- Still acceptable because explicitly requested

**Never assume auto-publish unless user says:**
- "auto-publish"
- "skip preview"
- "publish without review"

### Architecture Changes

**When changing how the system works:**

1. **Review PRD first** - Understand current architecture
2. **Propose the change** - Explain what and why
3. **Consider Netlify impact** - Will this increase builds?
4. **Get approval** - Before implementing
5. **Update PRD** - Document the new architecture
6. **Test thoroughly** - Regenerate all affected files
7. **Verify build efficiency** - Check git diff size

**Examples:**
- Changing how metadata is stored
- Adding new page generators
- Modifying publish workflow
- Restructuring directories

---

## Communication Standards

### When Making a Plan

**Required format:**
```
Problem: [what we're solving]
Approach: [how we'll solve it]
Files affected: [list with purposes]
Netlify impact: [builds required]
Risks: [what could go wrong]

Ready to proceed? (waiting for approval)
```

### When Showing Work

**Required format:**
```
Changed: [what you changed]
Location: [file:line]
Tested: [desktop/mobile localhost]
Verified: [what works now]

Ready to deploy? (waiting for approval)
```

### Prohibited Phrases

❌ "Done! Deployed!"
❌ "Pushed to GitHub"
❌ "Live now"
❌ "Should work"
❌ "Probably fine"

✅ "Plan ready for review"
✅ "Changes made. Test on localhost?"
✅ "Verified on localhost. Ready to commit?"
✅ "Committed. Should I push?"
✅ "Approved - deploying now"

---

## Mobile Testing

### Required Checks

For any CSS/layout changes:
1. Test on localhost desktop view
2. Test on localhost mobile view (browser dev tools)
3. Check both before claiming "done"
4. Verify responsive breakpoints work

### Common Mobile Issues to Check

- Logo wrapping/layout
- Nav button spacing
- CRT effects on small screens
- Header/masthead gaps
- Text alignment
- Touch target sizes
- Vertical spacing

**Check these explicitly, don't assume**

---

## Cost Awareness

### Build Credits

- Netlify free tier: 300 credits/month
- Each push = 1 build = costs credits
- Multiple pushes in dev session = waste

### Optimization Strategy

1. **Development work:**
   - Iterate on localhost
   - Batch related changes
   - Push once when complete

2. **Publishing posts:**
   - Posts auto-push (accepted cost)
   - Necessary for content updates

3. **Bug fixes:**
   - Batch multiple fixes
   - Test all together
   - Push once

4. **Design iteration:**
   - Use localhost preview
   - Make all CSS tweaks
   - Push final version only

**Goal:** Minimize builds while maintaining velocity

### Build Impact Analysis

**Before pushing, consider:**
- How many files changed?
- Could this have been batched?
- Is this truly ready?
- Did we test everything?

**Red flags:**
- Pushing "to see if it works"
- Fixing typo immediately after push
- Multiple pushes for same issue

---

## Session Memory

### How to Reference This Agreement

**At session start, user can say:**
> "Follow the working agreement in `/docs/working-agreement.md`"

**Claude must:**
1. Read the agreement
2. Acknowledge understanding
3. Follow it strictly
4. Default to caution over speed

### When Claude Forgets

**User response:**
> "You violated the working agreement - [specific violation]"

**Claude must:**
1. Acknowledge violation
2. Explain what happened
3. Confirm understanding of rule
4. Continue following agreement

### Common Violations

1. **Deploying without approval**
   - Stop immediately
   - Acknowledge the push happened
   - Confirm build was triggered
   - Resume with correct workflow

2. **Skipping the plan step**
   - Back up
   - Write the plan
   - Get approval
   - Then proceed

3. **Not testing on localhost**
   - Don't claim it works
   - Go test it
   - Show results
   - Then wait for approval

---

## Quality Standards

### "Done" Means

1. ✅ Problem understood
2. ✅ Plan made and approved
3. ✅ Code changed
4. ✅ Tested on localhost (desktop)
5. ✅ Tested on localhost (mobile)
6. ✅ User shown the work
7. ✅ User approved changes
8. ✅ User approved commit
9. ✅ User approved deploy
10. ✅ Pushed to GitHub
11. ✅ Netlify deployed

**All 11 required. Steps 7-9 need explicit approval.**

### Verification Standard

**Before claiming any task is complete, fixed, or working:**

1. ✅ **Check the actual output** - Read the HTML file, view the live site, or inspect terminal output
2. ✅ **Verify the issue is fixed** - Confirm the problem is gone, not just "should be fixed"
3. ✅ **Compare against expected behavior** - Does it match what was requested?
4. ✅ **Never rely on code logic alone** - Inspect the actual result

**Prohibited phrases (without verification):**
- ❌ "This should fix it"
- ❌ "Everything works great"
- ❌ "Fixed!"
- ❌ "Done!"
- ❌ "The changes are deployed and working"

**Required phrases (showing verification):**
- ✅ "I've checked the HTML output and confirmed..."
- ✅ "Looking at the live site, I can see..."
- ✅ "I verified by reading the file at line X..."
- ✅ "Testing on localhost shows..."
- ✅ "Comparing the output to the request, I can confirm..."

**Why this matters:**
Code that "should work" often doesn't. The only way to know something works is to verify the actual output. Claiming success without verification wastes time and breaks trust.

### Code Quality Checklist

Before claiming done:
- [ ] Read existing code first
- [ ] Followed established patterns
- [ ] Tested on localhost
- [ ] Checked mobile responsive
- [ ] **Verified actual output matches expectations**
- [ ] **Validated generators match outputs** (`python3 validate_generators.py`)
- [ ] Clear commit message drafted
- [ ] Netlify impact considered
- [ ] User approval received

### Generator Validation (CRITICAL)

**Rule:** NEVER manually edit generated HTML files.

**Generated files:**
- `index.html` (generated by `generate_homepage.py`)
- `words/index.html` (generated by `generate_archive.py`)
- `words/{slug}/index.html` (generated by `publish.py`)

**Before committing:**
1. Run validation: `python3 validate_generators.py`
2. If validation fails, generators are out of sync
3. Fix the generator script, not the HTML file
4. Regenerate and validate again

**Why this matters:**
Manual edits to generated files get silently lost on regeneration. This creates instability where features disappear without warning.

---

## Metrics We Track

### Build Efficiency
- Builds per feature (target: 1)
- Builds per session (target: minimize)
- Wasted builds from incomplete testing (target: 0)

### Process Adherence
- Deploys without approval (target: 0)
- Plans made before building (target: 100%)
- Changes tested on localhost first (target: 100%)

### Development Quality
- Issues found after deploy (target: 0)
- Rework rate (target: minimize)
- User satisfaction with process

---

## Examples

### ✅ Good Example: CSS Changes

1. User: "Fix the mobile nav spacing"
2. Claude: "I'll reduce padding and gaps. Plan:
   - Change .site-nav padding: 8px → 6px
   - Change gap: 8px → 6px
   - Test on localhost mobile view
   Ready to proceed?"
3. User: "Yes"
4. Claude: [makes changes]
5. Claude: "Changed padding in lib/styles/styles.css:887
   Tested on localhost mobile - nav is more compact now
   Ready to commit and deploy?"
6. User: "Deploy"
7. Claude: [commits and pushes]

**Result**: 1 build, efficient process, user in control

### ❌ Bad Example: Multiple Deploys

1. User: "Fix the mobile nav spacing"
2. Claude: [makes change, commits, pushes]
3. Claude: "Deployed! But I see the gap is still too big..."
4. Claude: [makes another change, commits, pushes]
5. Claude: "Fixed! Oh wait, the padding needs work too..."
6. Claude: [makes another change, commits, pushes]

**Result**: 3 builds wasted, user frustrated, money wasted

### ✅ Good Example: Architecture Change

1. User: "We need to download images from Google Docs"
2. Claude: "Plan for image download feature:
   Problem: Images use temporary Google URLs
   Approach:
   - Add download_image() function to publish.py
   - Download during HTML conversion
   - Save to /lib/img/
   - Update HTML to use local paths
   - Include images in git commit
   Files affected:
   - publish.py (add download logic)
   - lib/img/ (new directory)
   Netlify impact: No change (same # of builds)
   Risks: Need to handle download failures
   Ready to proceed?"
3. User: "Good, go ahead"
4. Claude: [implements]
5. Claude: "Implemented and tested on localhost.
   Downloaded kitten image successfully.
   Ready to commit and deploy?"
6. User: "Deploy"

**Result**: Clean implementation, user informed, efficient

### ✅ Good Example: Publishing Posts

1. User: "Publish the new blog post 'AI coding patterns'"
2. Claude: "I'll run the publish script in interactive mode so you can review the preview first."
3. Claude: [runs `python3 publish.py "AI coding patterns"`]
4. Claude: "The script has generated a preview and opened it in your browser. The script is waiting for your approval."
5. User: [reviews preview in browser, notices a typo, edits Google Doc]
6. User: "Actually, let me fix a typo first"
7. User: [after fixing] "OK, publish it again"
8. Claude: [runs `python3 publish.py "AI coding patterns"` again]
9. User: [reviews, looks good] "yes" [types in terminal]
10. Claude: "✓ Published! The post is now live and Netlify will deploy it."

**Result**: 1 build, quality ensured, user had control

### ❌ Bad Example: Auto-Publishing

1. User: "Publish the new blog post"
2. Claude: [runs `echo "yes" | python3 publish.py "Post Name"`]
3. Claude: "Published!"
4. User: [checks site, finds typo or formatting issue]
5. User: "There's a typo, fix it"
6. Claude: [user edits doc, republishes]
7. Claude: "Fixed and republished!"

**Result**: 2 builds wasted, user frustrated, issue went live briefly

---

## Escalation Path

### When Requirements are Unclear

**Claude should:**
1. Ask specific questions
2. Propose options if helpful
3. Wait for clarification
4. Never guess at intent

### When Build Efficiency is at Risk

**Claude should:**
1. Flag the concern
2. Suggest batching approach
3. Explain tradeoffs
4. Let user decide

**Example:**
> "This would require 3 separate pushes. Would you like me to batch all the changes and push once instead? It would save 2 builds."

### When Testing Reveals Issues

**Claude should:**
1. Document what's broken
2. Propose fix
3. Test fix locally
4. Then ask about deploying

**Never:**
- Push broken code to "see what happens"
- Deploy untested fixes

---

## Tools & Commands

### Localhost Preview

```bash
# Start preview server
python3 -m http.server 8000

# Access at:
# http://localhost:8000/
```

### Publishing

```bash
# Interactive publish (user approves preview)
python3 publish.py "Post Title"

# Auto-approve publish (when explicitly requested)
echo "yes" | python3 publish.py "Post Title"
```

### Regeneration

```bash
# Regenerate archive
python3 generate_archive.py

# Regenerate homepage
python3 generate_homepage.py

# Note: These run automatically during publish.py for "words" posts
```

### Git Workflow

```bash
# After user approval
git add [files]
git commit -m "Clear message"

# After user approval
git push
```

---

## Acknowledgment

By continuing work on this project, Claude commits to:
- **NEVER** pushing to GitHub without explicit approval
- Following the plan → build → test → approve → deploy workflow
- Considering Netlify build impact in all decisions
- Testing all changes on localhost first
- Showing work before deploying
- Respecting cost constraints
- Asking when unsure
- Defaulting to caution over speed
- Batching changes to minimize builds

**This is the contract.**

---

**Version**: 1.0
**Effective**: 2026-01-07
**Next Review**: After significant architecture changes or process issues

---

## Quick Reference Card

**Before claiming "done" or "fixed", ask:**
1. ✅ Did I verify the actual output (HTML file, live site, terminal)?
2. ✅ Did I confirm the issue is actually fixed (not just "should be")?
3. ✅ Does the result match what was requested?

**Before every push, ask:**
1. ✅ Did I make a plan?
2. ✅ Did user approve the plan?
3. ✅ Did I test on localhost (desktop + mobile)?
4. ✅ Did I verify the actual output?
5. ✅ Did I show the user what changed?
6. ✅ Did user explicitly say "deploy" or "push"?

**If any answer is NO → DON'T PUSH**

**Remember:** When in doubt, ask. Never assume approval. Never claim success without verification.
