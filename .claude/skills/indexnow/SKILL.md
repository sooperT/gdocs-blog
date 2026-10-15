---
name: indexnow
description: Tell Bing (via IndexNow) which takenbyninjas.com pages changed, so Copilot answers from the new content instead of its stale copy. Use after any push that regenerates agent pages or publishes a post, or when Tom says "ping Bing", "resubmit to Bing", "tell Bing it changed", or asks why Copilot is behind.
argument-hint: "[--changed [rev-range] | --all | /path/ ...] [--dry-run]"
allowed-tools: Bash, Read
---

# /indexnow — tell Bing the pages changed

Copilot grounds on Bing's index. Bing crawls this site rarely, so a regenerated agent page is stale in Copilot until Bing is told. IndexNow is one POST with every changed URL, no daily quota, shared with Yandex, Seznam and Naver. Key file is `fc3c395c151aeaf226a0299dd43dce31.txt` at the site root; `scripts/indexnow.py` holds the key and the endpoint.

## When

After the Netlify deploy has landed, never straight after `git push`: the script fetches every URL first and refuses any that is not live with a 200 and no noindex. Wait for the deploy (about 30 seconds; confirm by curling one changed page for the new text), then run.

## Run

```bash
python3 scripts/indexnow.py --changed                   # pages changed by HEAD (HEAD~1..HEAD)
python3 scripts/indexnow.py --changed e088e14..f8f8937  # pages changed in a range (a batch of commits)
python3 scripts/indexnow.py --all                       # every URL in both sitemaps (after a template change)
python3 scripts/indexnow.py /for-agents/ /words/kitten-pm/
python3 scripts/indexnow.py --changed --dry-run         # list without pinging
```

`--changed` maps `*/index.html`, `llms.txt` and `for-agents/start.md` in the diff to URLs and keeps only those in `sitemap.xml` or `sitemap-agent.xml`, so unlisted fit pages and the noindexed `/for-agents/skills/*` pages are never pinged.

## Read the result

- `✓ IndexNow 200` or `202`: accepted. Bing usually recrawls within hours; Webmaster Tools → IndexNow shows the submissions arriving.
- `✗ ... (noindex)` or a non-200 on a URL: that URL was skipped and the exit code is 1. Usually the deploy has not landed; wait and rerun.
- `403`: the key file is not being served. `422`: a URL is not on takenbyninjas.com. `429`: too many pings; wait.

## Not covered

- Bing's manual "Request indexing" button is separate, ten a day, and is only worth it for a page Bing has never crawled. IndexNow is for pages Bing already knows.
- Google ignores IndexNow. The sitemaps cover Google.
- This is a live call to a third party, so the night shift does not run it; Tom's day session does, after he approved the push.
