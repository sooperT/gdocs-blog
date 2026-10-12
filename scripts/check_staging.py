#!/usr/bin/env python3
"""Free smoke check of the agent side on a deployed URL (backlog item 22).

Only plain GETs that cost nothing: no /ask?q= (that would call Voyage), no
brief. One line per check, exit 1 if any check fails.

    python3 scripts/check_staging.py --base https://staging--<site>.netlify.app
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser

UA = "tbn-check-staging/1.0 (+https://takenbyninjas.com/for-agents/)"
TIMEOUT = 20

# The facts page's first line routes three ways (PRD R1012-1, item 18d).
ROUTING_LINKS = ("/about/", "/for-agents/start.md", "/llms.txt")


class FirstParagraph(HTMLParser):
    """Collects the hrefs inside the first <p> of the page body."""

    def __init__(self):
        super().__init__()
        self.in_body = False
        self.depth = 0
        self.done = False
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.in_body = True
        if not self.in_body or self.done:
            return
        if tag == "p":
            self.depth += 1
        elif tag == "a" and self.depth:
            self.hrefs.append(dict(attrs).get("href") or "")

    def handle_endtag(self, tag):
        if tag == "p" and self.depth and not self.done:
            self.depth -= 1
            if self.depth == 0:
                self.done = True


def fetch(base, path):
    req = urllib.request.Request(base + path, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return res.status, res.headers.get("Content-Type", ""), res.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read().decode("utf-8", "replace")
    except Exception as e:  # network error, timeout, bad URL
        return None, "", f"{type(e).__name__}: {e}"


def check_routing(body):
    p = FirstParagraph()
    p.feed(body)
    missing = [link for link in ROUTING_LINKS if link not in p.hrefs]
    return (not missing), ("first line routes to " + ", ".join(ROUTING_LINKS)) if not missing else f"first <p> missing {', '.join(missing)}"


def check_robots(body):
    lines = [l.strip().lower() for l in body.splitlines()]
    missing = [s for s in ("sitemap.xml", "sitemap-agent.xml")
               if not any(l.startswith("sitemap:") and l.endswith("/" + s) for l in lines)]
    return (not missing), "names both sitemaps" if not missing else f"no Sitemap: line for {', '.join(missing)}"


def check_map(body):
    try:
        data = json.loads(body)
    except ValueError:
        return False, "not JSON"
    sections = data.get("sections") if isinstance(data, dict) else None
    if not isinstance(sections, list) or not sections:
        return False, "no sections in the map"
    return True, f"map lists {len(sections)} sections"


CHECKS = [
    # path, accepted content types, extra check
    ("/for-agents/", ("text/html",), check_routing),
    ("/for-agents/start.md", ("text/markdown", "text/plain", "text/x-markdown"), None),
    # Old entry file name: 301 to start.md (urllib follows it), served by agent-fetch.
    ("/for-agents/README.md", ("text/markdown", "text/plain", "text/x-markdown"), None),
    ("/for-agents/wegovycare/", ("text/html",), check_routing),
    ("/for-agents/treat-turnaround/", ("text/html",), check_routing),
    ("/llms.txt", ("text/plain", "text/markdown"), None),
    ("/robots.txt", ("text/plain",), check_robots),
    ("/sitemap.xml", ("application/xml", "text/xml"), None),
    ("/sitemap-agent.xml", ("application/xml", "text/xml"), None),
    ("/ask", ("application/json",), check_map),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", required=True, help="deployed site, e.g. https://staging--<site>.netlify.app")
    base = ap.parse_args().base.rstrip("/")

    failures = 0
    for path, types, extra in CHECKS:
        status, ctype, body = fetch(base, path)
        problems = []
        if status != 200:
            problems.append(f"status {status}" if status else body[:120])
        elif not ctype.lower().split(";")[0].strip() in types:
            problems.append(f"content type {ctype or '(none)'}, expected {' or '.join(types)}")
        detail = ""
        if not problems and extra:
            ok, detail = extra(body)
            if not ok:
                problems.append(detail)
        if problems:
            failures += 1
            print(f"FAIL {path}: {'; '.join(problems)}")
        else:
            print(f"ok   {path}: 200 {ctype.split(';')[0]}" + (f", {detail}" if detail else ""))

    print(f"\n{len(CHECKS) - failures}/{len(CHECKS)} passed" + ("" if not failures else ", SOME FAILED"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
