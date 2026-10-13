#!/usr/bin/env python3
"""
Generate sitemap.xml (human pages) and sitemap-agent.xml (agent side)

sitemap.xml reads posts-metadata.json and lists the human pages only
(PRD R1012-4 b):
- Homepage
- Archive pages (/words/, /projects/)
- Individual posts (hidden posts excluded)
- Static pages (/about/)

sitemap-agent.xml lists the agent side: /for-agents/, its case study pages,
the recommendations page,
/for-agents/start.md and /llms.txt. robots.txt lists both.

lastmod is the file's last git commit date (N1010-1), so running the
generator twice changes nothing. A file git does not know yet gets today.

Usage:
    python3 generate_sitemap.py
"""

import os
import json
import subprocess
from datetime import date
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString
from pylib.config import METADATA_FILE

SITE_URL = "https://takenbyninjas.com"
OUTPUT_FILE = "sitemap.xml"
AGENT_OUTPUT_FILE = "sitemap-agent.xml"

# Agent side (R1012-1): (url, file). Case studies come from generate_agent_page.py.
AGENT_PAGES = [
    ("/for-agents/", "for-agents/index.html"),
    ("/for-agents/wegovycare/", "for-agents/wegovycare/index.html"),
    ("/for-agents/treat-turnaround/", "for-agents/treat-turnaround/index.html"),
    ("/for-agents/recommendations/", "for-agents/recommendations/index.html"),
    ("/for-agents/working-style/", "for-agents/working-style/index.html"),   # Insights profiles (R1013-7)
    ("/for-agents/fit/", "for-agents/fit/index.html"),   # the five FIT sections (item 76)
    ("/for-agents/start/", "for-agents/start/index.html"),   # the paste URL (N1012-16)
    ("/for-agents/start.md", "for-agents/start.md"),
    ("/llms.txt", "llms.txt"),
]


def get_file_modified_date(filepath):
    """Last git commit date of a file (YYYY-MM-DD); today if git does not know it yet."""
    if not os.path.exists(filepath):
        return None
    result = subprocess.run(
        ["git", "log", "-1", "--format=%cs", "--", filepath],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() or date.today().isoformat()


def collect_pages():
    """Collect all pages for the sitemap"""
    pages = []

    # Homepage
    pages.append({
        "url": "/",
        "lastmod": get_file_modified_date("index.html"),
        "priority": 1.0
    })

    # Archive pages
    pages.append({
        "url": "/words/",
        "lastmod": get_file_modified_date("words/index.html"),
        "priority": 0.9
    })

    pages.append({
        "url": "/projects/",
        "lastmod": get_file_modified_date("projects/index.html"),
        "priority": 0.8
    })

    # About page
    pages.append({
        "url": "/about/",
        "lastmod": get_file_modified_date("about/index.html"),
        "priority": 0.7
    })

    # Load posts from metadata
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for post in data.get('posts', []):
            # Skip pages we've already added (like /about/)
            if post.get('type') == 'pages':
                continue
            # Hidden posts stay live but are linked from nowhere
            if post.get('hidden'):
                continue

            url = post.get('url', '')
            if url:
                # Determine file path from URL
                filepath = url.strip('/') + '/index.html'

                pages.append({
                    "url": url,
                    "lastmod": get_file_modified_date(filepath),
                    "priority": 0.6
                })

    return pages


def collect_agent_pages():
    """Collect the agent-side URLs for sitemap-agent.xml: the fixed list plus every
    page in for-agents/pages.json (written by generate_agent_page.py)."""
    pages = list(AGENT_PAGES)
    if os.path.exists("for-agents/pages.json"):
        with open("for-agents/pages.json", encoding="utf-8") as f:
            for slug, p in json.load(f)["pages"].items():
                if slug.startswith("fit/"):
                    continue   # per-send fit pages are unlisted (scripts/cv_appendix.py)
                if (p["path"], p["file"]) not in pages:
                    pages.append((p["path"], p["file"]))
    return [{"url": url, "lastmod": get_file_modified_date(path)}
            for url, path in pages if os.path.exists(path) and not is_noindex(path)]


def is_noindex(path):
    """A page that asks not to be indexed is not listed (N1012-16: the skill pages)."""
    if not path.endswith(".html"):
        return False
    with open(path, encoding="utf-8") as f:
        head = f.read(4000)
    return 'name="robots" content="noindex' in head


def generate_sitemap(pages):
    """Generate sitemap XML from list of pages"""
    urlset = Element("urlset")
    urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

    for page in pages:
        url_elem = SubElement(urlset, "url")

        loc = SubElement(url_elem, "loc")
        loc.text = f"{SITE_URL}{page['url']}"

        if page.get("lastmod"):
            lastmod = SubElement(url_elem, "lastmod")
            lastmod.text = page["lastmod"]

        if page.get("priority"):
            priority = SubElement(url_elem, "priority")
            priority.text = str(page["priority"])

    # Pretty print
    xml_string = tostring(urlset, encoding="unicode")
    pretty_xml = parseString(xml_string).toprettyxml(indent="  ")

    # Remove extra declaration line from minidom and clean up
    lines = pretty_xml.split("\n")
    # Keep declaration, skip empty lines after it
    cleaned_lines = [lines[0]]  # XML declaration
    for line in lines[1:]:
        if line.strip():  # Skip empty lines
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def main():
    print("=" * 60)
    print("GENERATING SITEMAP")
    print("=" * 60)
    print()

    for output, pages in ((OUTPUT_FILE, collect_pages()), (AGENT_OUTPUT_FILE, collect_agent_pages())):
        print(f"{output}: {len(pages)} URLs")
        for page in pages:
            print(f"  {page['url']}  {page['lastmod']}")
        with open(output, 'w', encoding='utf-8') as f:
            f.write(generate_sitemap(pages))
        print()

    print("=" * 60)
    print("SUCCESS!")
    print("=" * 60)


if __name__ == '__main__':
    main()
