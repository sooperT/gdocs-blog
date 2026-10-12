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
    """Collect the agent-side URLs for sitemap-agent.xml"""
    return [{"url": url, "lastmod": get_file_modified_date(path)}
            for url, path in AGENT_PAGES if os.path.exists(path)]


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
