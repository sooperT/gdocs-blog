#!/usr/bin/env python3
"""
Generate sitemap.xml for SEO

Reads posts-metadata.json and generates a sitemap including:
- Homepage
- Archive pages (/words/, /projects/)
- Individual posts
- Static pages (/about/)

Usage:
    python3 generate_sitemap.py
"""

import os
import json
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString
from pylib.config import METADATA_FILE

SITE_URL = "https://takenbyninjas.com"
OUTPUT_FILE = "sitemap.xml"


def get_file_modified_date(filepath):
    """Get last modified date of a file in YYYY-MM-DD format"""
    if os.path.exists(filepath):
        mtime = os.path.getmtime(filepath)
        return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
    return None


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

            url = post.get('url', '')
            if url:
                # Determine file path from URL
                filepath = url.strip('/') + '/index.html'

                pages.append({
                    "url": url,
                    "lastmod": post.get('date') or get_file_modified_date(filepath),
                    "priority": 0.6
                })

    return pages


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

    # Collect pages
    print("Collecting pages...")
    pages = collect_pages()
    print(f"Found {len(pages)} pages")

    for page in pages:
        print(f"  {page['url']}")

    # Generate XML
    print("\nGenerating sitemap XML...")
    sitemap_xml = generate_sitemap(pages)

    # Write to file
    print(f"Saving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(sitemap_xml)

    print(f"\n{'=' * 60}")
    print("SUCCESS!")
    print("=" * 60)
    print(f"Sitemap saved to: {OUTPUT_FILE}")
    print(f"Total URLs: {len(pages)}")


if __name__ == '__main__':
    main()
