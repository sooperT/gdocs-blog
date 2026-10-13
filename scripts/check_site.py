#!/usr/bin/env python3
"""Site validation gate for takenbyninjas.com.

Walks every *.html file under a root (default ".") and reports:
  1. tag     - unclosed, mismatched or stray tags (open-tag stack; void
               elements and optional-end-tag elements are not errors)
  2. link    - internal a/img/link/script/source URLs that do not resolve to
               a file in the repo (directory URLs resolve to index.html;
               #fragment and ?query are stripped; _redirects sources count
               as resolving)
  3. meta    - pages missing <title>, <meta name="description"> or
               <link rel="canonical"> (see META_EXEMPT)
  4. jsonld  - <script type="application/ld+json"> blocks that fail json.loads

Output: one line per finding "path: kind: detail", then a summary line.
Exit code 1 on any finding, 0 when clean. Read-only: never writes files.

Usage: python3 scripts/check_site.py [ROOT]
"""

import json
import os
import sys
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

# Directories never walked (relative to root).
SKIP_DIRS = {"mockups", "node_modules", ".claude", "docs", ".netlify", ".git"}

# Pages that are not public content pages: exempt from the meta checks only
# (tag, link and JSON-LD checks still apply). Entries ending in "/" are
# path prefixes; others are exact relative paths.
META_EXEMPT = [
    "playground.html",          # internal CSS style playground
    "projects/kitten-pm-v0/",   # standalone prototype app
    "downloads/",               # file drop (PDFs, images), not pages
]

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}

# Elements whose end tag HTML allows to be omitted: left open, not an error.
OPTIONAL_END = {"p", "li", "dt", "dd", "option", "optgroup", "tr", "td", "th",
                "thead", "tbody", "tfoot", "colgroup", "rt", "rp",
                "html", "head", "body"}

LINK_ATTRS = {("a", "href"), ("img", "src"), ("link", "href"),
              ("script", "src"), ("source", "src")}

SKIP_SCHEMES = ("http://", "https://", "mailto:", "tel:", "data:", "//",
                "javascript:")


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []          # (tag, line)
        self.tag_issues = []
        self.links = []          # (url, line)
        self.has_title = False
        self.has_desc = False
        self.has_canonical = False
        self.in_jsonld = False
        self.jsonld = []         # (text, line)
        self._buf = []
        self._jsonld_line = 0

    def _check_attrs(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        for t, attr in LINK_ATTRS:
            if tag == t and a.get(attr):
                self.links.append((a[attr].strip(), self.getpos()[0]))
        if tag == "source" and a.get("srcset"):
            for part in a["srcset"].split(","):
                url = part.strip().split(" ")[0]
                if url:
                    self.links.append((url, self.getpos()[0]))
        if tag == "title":
            self.has_title = True
        if tag == "meta" and a.get("name", "").lower() == "description" \
                and a.get("content", "").strip():
            self.has_desc = True
        if tag == "link" and "canonical" in a.get("rel", "").lower().split() \
                and a.get("href"):
            self.has_canonical = True
        return a

    def handle_starttag(self, tag, attrs):
        a = self._check_attrs(tag, attrs)
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self.in_jsonld = True
            self._buf = []
            self._jsonld_line = self.getpos()[0]
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        self._check_attrs(tag, attrs)  # self-closing: nothing pushed

    def handle_data(self, data):
        if self.in_jsonld:
            self._buf.append(data)

    def handle_endtag(self, tag):
        line = self.getpos()[0]
        if tag == "script" and self.in_jsonld:
            self.jsonld.append(("".join(self._buf), self._jsonld_line))
            self.in_jsonld = False
        if tag in VOID:
            return
        names = [t for t, _ in self.stack]
        if tag not in names:
            self.tag_issues.append(f"stray </{tag}> at line {line}")
            return
        while self.stack:
            open_tag, open_line = self.stack.pop()
            if open_tag == tag:
                break
            if open_tag not in OPTIONAL_END:
                self.tag_issues.append(
                    f"<{open_tag}> opened at line {open_line} closed "
                    f"implicitly by </{tag}> at line {line}")

    def finish(self):
        self.close()
        for open_tag, open_line in self.stack:
            if open_tag not in OPTIONAL_END:
                self.tag_issues.append(
                    f"<{open_tag}> opened at line {open_line} never closed")


def load_redirects(root):
    sources = set()
    path = os.path.join(root, "_redirects")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    sources.add(line.split()[0].rstrip("/") or "/")
    return sources


def resolves(root, page_rel, url, redirects):
    parts = urlsplit(url)
    path = unquote(parts.path)
    if not path:
        return True  # pure #fragment or ?query
    if path.startswith("/"):
        site_path = path
    else:
        base = "/" + os.path.dirname(page_rel).replace(os.sep, "/")
        site_path = os.path.normpath(os.path.join(base, path))
        if path.endswith("/"):
            site_path += "/"
    if (site_path.rstrip("/") or "/") in redirects:
        return True
    fs = os.path.join(root, site_path.lstrip("/"))
    if os.path.isfile(fs):
        return True
    return os.path.isfile(os.path.join(fs, "index.html"))


def is_meta_exempt(rel):
    rel = rel.replace(os.sep, "/")
    return any(rel.startswith(e) if e.endswith("/") else rel == e
               for e in META_EXEMPT)


def html_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        dirnames.sort()
        for name in sorted(filenames):
            if name.endswith(".html"):
                yield os.path.relpath(os.path.join(dirpath, name), root)


def check_page(root, rel, redirects):
    findings = []
    with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as f:
        text = f.read()
    p = PageParser()
    p.feed(text)
    p.finish()

    for issue in p.tag_issues:
        findings.append(("tag", issue))

    for url, line in p.links:
        if not url or url.lower().startswith(SKIP_SCHEMES) or url.startswith("#"):
            continue
        if not resolves(root, rel, url, redirects):
            findings.append(("link", f"{url} (line {line}) does not resolve"))

    if not is_meta_exempt(rel):
        if not p.has_title:
            findings.append(("meta", "missing <title>"))
        if not p.has_desc:
            findings.append(("meta", 'missing <meta name="description">'))
        if not p.has_canonical:
            findings.append(("meta", 'missing <link rel="canonical">'))

    for block, line in p.jsonld:
        try:
            json.loads(block)
        except json.JSONDecodeError as e:
            findings.append(("jsonld", f"block at line {line}: {e}"))
    return findings


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    redirects = load_redirects(root)
    counts = {"tag": 0, "link": 0, "meta": 0, "jsonld": 0}
    pages = 0
    for rel in html_files(root):
        pages += 1
        for kind, detail in check_page(root, rel, redirects):
            counts[kind] += 1
            print(f"{rel.replace(os.sep, '/')}: {kind}: {detail}")
    total = sum(counts.values())
    summary = ", ".join(f"{k} {v}" for k, v in counts.items())
    print(f"check_site: {pages} pages, {total} findings ({summary}); "
          f"meta-exempt: {', '.join(META_EXEMPT)}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
