#!/usr/bin/env python3
"""
Generate archive page for /words/

Scans all published posts in /words/ directory and creates an index page
sorted by date (newest first).

Usage:
    python3 generate_archive.py
"""

import os
import json
from datetime import datetime
from html.parser import HTMLParser


class PostMetadataExtractor(HTMLParser):
    """Extract metadata from published HTML files"""

    def __init__(self):
        super().__init__()
        self.title = None
        self.date = None
        self.tags = []
        self.in_title = False
        self.in_meta = False
        self.meta_text = ""

    def handle_starttag(self, tag, attrs):
        if tag == 'title':
            self.in_title = True
        elif tag == 'p':
            # Check if this is the post-meta paragraph
            for attr, value in attrs:
                if attr == 'class' and value == 'post-meta':
                    self.in_meta = True
        elif tag == 'h1' and not self.title:
            # First h1 is the post title
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == 'title' or tag == 'h1':
            self.in_title = False
        elif tag == 'p' and self.in_meta:
            self.in_meta = False
            # Parse the meta text
            self._parse_meta_text()

    def handle_data(self, data):
        if self.in_title and not self.title:
            # Extract title (remove " - taken" suffix if present)
            self.title = data.replace(' - taken', '').strip()
        elif self.in_meta:
            self.meta_text += data

    def _parse_meta_text(self):
        """Parse 'Published on: 2026-01-05. Filed under: ai, product'"""
        if 'Published on:' in self.meta_text:
            parts = self.meta_text.split('Published on:')[1]
            date_part = parts.split('.')[0].strip()
            self.date = date_part

        if 'Filed under:' in self.meta_text:
            tags_part = self.meta_text.split('Filed under:')[1].strip()
            self.tags = [tag.strip() for tag in tags_part.split(',')]


def extract_post_metadata(post_path):
    """Extract metadata from a published post HTML file"""
    with open(post_path, 'r', encoding='utf-8') as f:
        html = f.read()

    parser = PostMetadataExtractor()
    parser.feed(html)

    return {
        'title': parser.title,
        'date': parser.date,
        'tags': parser.tags
    }


def scan_posts():
    """Scan all posts in /words/ directory"""
    posts = []
    words_dir = 'words'

    if not os.path.exists(words_dir):
        print(f"✗ Directory '{words_dir}' not found")
        return posts

    # Scan all subdirectories
    for slug in os.listdir(words_dir):
        post_dir = os.path.join(words_dir, slug)

        if not os.path.isdir(post_dir):
            continue

        index_file = os.path.join(post_dir, 'index.html')

        if not os.path.exists(index_file):
            continue

        # Extract metadata
        metadata = extract_post_metadata(index_file)

        if metadata['title'] and metadata['date']:
            posts.append({
                'slug': slug,
                'title': metadata['title'],
                'date': metadata['date'],
                'tags': metadata['tags'],
                'url': f'/words/{slug}/'
            })
            print(f"✓ Found: {metadata['title']} ({metadata['date']})")

    return posts


def generate_archive_html(posts):
    """Generate the archive page HTML"""

    # Sort by date (newest first)
    posts_sorted = sorted(posts, key=lambda p: p['date'], reverse=True)

    html_parts = []

    # HTML head
    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<html lang="en">')
    html_parts.append('<head>')
    html_parts.append('    <meta charset="UTF-8">')
    html_parts.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    html_parts.append('    <title>Words - taken</title>')
    html_parts.append('    <link rel="stylesheet" href="../styles.css">')
    html_parts.append('</head>')
    html_parts.append('<body>')
    html_parts.append('    <div class="crt-overlay"></div>')
    html_parts.append('')

    # Header
    html_parts.append('    <!-- HEADER -->')
    html_parts.append('    <header class="site-header">')
    html_parts.append('        <div class="identity">')
    html_parts.append('            <h1 class="logo"><span class="logo-t">T</span><span class="logo-aken">aken</span></h1>')
    html_parts.append('            <div class="ninja-icon">🥷</div>')
    html_parts.append('            <p class="tagline">Words on product, systems thinking and life.</p>')
    html_parts.append('        </div>')
    html_parts.append('    </header>')
    html_parts.append('')

    # Navigation
    html_parts.append('    <!-- NAVIGATION -->')
    html_parts.append('    <nav class="site-nav">')
    html_parts.append('        <a href="/" class="nav-red">Home</a>')
    html_parts.append('        <a href="/words/" class="nav-green active">Words</a>')
    html_parts.append('        <a href="/projects/" class="nav-yellow">Projects</a>')
    html_parts.append('        <a href="/about/" class="nav-blue">About</a>')
    html_parts.append('    </nav>')
    html_parts.append('')

    # Main content
    html_parts.append('    <!-- MAIN CONTENT -->')
    html_parts.append('    <main>')
    html_parts.append('        <h1>Words</h1>')
    html_parts.append('        <p>Writing on product, systems thinking and life.</p>')
    html_parts.append('')
    html_parts.append('        <div class="post-listing">')

    # Add each post
    for post in posts_sorted:
        html_parts.append('            <article class="post-preview">')
        html_parts.append(f'                <h3><a href="{post["url"]}">{post["title"]}</a></h3>')

        # Metadata
        meta_parts = []
        if post['date']:
            meta_parts.append(f'Published on: {post["date"]}.')
        if post['tags']:
            tag_list = ', '.join(post['tags'])
            meta_parts.append(f'Filed under: {tag_list}')

        if meta_parts:
            html_parts.append(f'                <p class="post-meta">{" ".join(meta_parts)}</p>')

        html_parts.append('            </article>')

    html_parts.append('        </div>')
    html_parts.append('    </main>')
    html_parts.append('')

    # Footer
    html_parts.append('    <!-- FOOTER -->')
    html_parts.append('    <footer class="site-footer">')
    html_parts.append('        <p>Code created with AI — Words are my own</p>')
    html_parts.append('    </footer>')
    html_parts.append('</body>')
    html_parts.append('</html>')

    return '\n'.join(html_parts)


def main():
    print("="*60)
    print("GENERATING ARCHIVE PAGE")
    print("="*60)
    print()

    # Scan posts
    print("Scanning /words/ directory...")
    posts = scan_posts()

    if not posts:
        print("\n✗ No posts found")
        return

    print(f"\n✓ Found {len(posts)} posts")

    # Generate HTML
    print("\nGenerating archive HTML...")
    html = generate_archive_html(posts)

    # Save to file
    output_file = 'words/index.html'
    print(f"Saving to {output_file}...")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print("✓ Archive page generated")
    print("\n" + "="*60)
    print("✓ SUCCESS!")
    print("="*60)
    print(f"Archive page: {output_file}")
    print(f"Total posts: {len(posts)}")


if __name__ == '__main__':
    main()
