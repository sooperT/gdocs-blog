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


def format_date_for_display(iso_date):
    """
    Convert ISO date (YYYY-MM-DD) to display format (DD/MM/YYYY)
    """
    try:
        date_obj = datetime.strptime(iso_date, '%Y-%m-%d')
        return date_obj.strftime('%d/%m/%Y')
    except:
        return iso_date  # Return original if parsing fails


class PostMetadataExtractor(HTMLParser):
    """Extract metadata from published HTML files"""

    def __init__(self):
        super().__init__()
        self.title = None
        self.date = None
        self.tags = []
        self.excerpt = None
        self.in_h1 = False
        self.in_meta = False
        self.in_main = False
        self.in_p = False
        self.meta_text = ""
        self.paragraphs_after_meta = 0
        self.excerpt_ended = False

    def handle_starttag(self, tag, attrs):
        if tag == 'main':
            self.in_main = True
        elif tag == 'h1' and self.in_main and not self.title:
            # First h1 in main is the post title
            self.in_h1 = True
        elif tag == 'figure' and self.in_main and self.date:
            # Track figure elements - they don't count as paragraphs for excerpt detection
            # This allows us to skip figures and capture the first actual text paragraph
            pass
        elif tag == 'p' and self.in_main:
            # Check if this is the post-meta paragraph
            is_meta = False
            for attr, value in attrs:
                if attr == 'class' and value == 'post-meta':
                    is_meta = True
                    self.in_meta = True
                    break

            # If not meta and we've seen meta, capture paragraphs until EXCERPT_END marker
            # Allow a few non-paragraph elements (figures) before capturing excerpt
            # Stop if we've hit the excerpt end marker
            if not is_meta and self.date and not self.excerpt_ended:
                self.in_p = True

    def handle_endtag(self, tag):
        if tag == 'main':
            self.in_main = False
        elif tag == 'h1':
            self.in_h1 = False
        elif tag == 'p':
            if self.in_meta:
                self.in_meta = False
                self._parse_meta_text()
                self.paragraphs_after_meta = 0
            elif self.in_p:
                self.in_p = False
                # Add space between paragraphs if we're accumulating multiple
                if self.excerpt:
                    self.excerpt += " "
                self.paragraphs_after_meta += 1

    def handle_comment(self, data):
        """Handle HTML comments - look for EXCERPT_END marker"""
        if data.strip() == 'EXCERPT_END':
            self.excerpt_ended = True
            # If we're currently in a paragraph, close it
            if self.in_p:
                self.in_p = False
                if self.excerpt:
                    self.excerpt = self.excerpt.strip()

    def handle_data(self, data):
        if self.in_h1:
            self.title = data.strip()
        elif self.in_meta:
            self.meta_text += data
        elif self.in_p and not self.excerpt_ended:
            # Accumulate all text from the paragraph (handles inline formatting)
            if not self.excerpt:
                self.excerpt = data
            else:
                self.excerpt += data

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
        'tags': parser.tags,
        'excerpt': parser.excerpt
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
                'excerpt': metadata.get('excerpt', ''),
                'url': f'/words/{slug}/'
            })
            print(f"✓ Found: {metadata['title']} ({metadata['date']})")

    return posts


def generate_archive_html(posts):
    """Generate the archive page HTML"""

    # Sort by date (newest first)
    # Handle both ISO format (YYYY-MM-DD) and display format (DD/MM/YYYY)
    def parse_date(date_str):
        if not date_str:
            return datetime.min
        try:
            # Try ISO format first
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            # Try display format
            return datetime.strptime(date_str, '%d/%m/%Y')

    posts_sorted = sorted(posts, key=lambda p: parse_date(p['date']), reverse=True)

    html_parts = []

    # HTML head
    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<!-- GENERATED FILE - DO NOT EDIT MANUALLY -->')
    html_parts.append('<!-- Generated by: generate_archive.py -->')
    html_parts.append('<!-- To modify: Edit generate_archive.py and regenerate -->')
    html_parts.append('<html lang="en">')
    html_parts.append('<head>')
    html_parts.append('    <meta charset="UTF-8">')
    html_parts.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    html_parts.append('    <title>Words - taken</title>')
    html_parts.append('    <link rel="stylesheet" href="/lib/styles/styles.css">')
    html_parts.append('    <script src="/tag-filter.js" defer></script>')
    html_parts.append('</head>')
    html_parts.append('<body>')
    html_parts.append('    <div class="crt-overlay"></div>')
    html_parts.append('')

    # Header
    html_parts.append('    <!-- HEADER -->')
    html_parts.append('    <header class="site-header">')
    html_parts.append('        <div class="identity">')
    html_parts.append('            <div class="logo-container">')
    html_parts.append('                <h2 class="logo">Taken</h2>')
    html_parts.append('                <img class="ninja-icon" src="/lib/img/ninja-trans.png" alt="Ninja">')
    html_parts.append('            </div>')
    html_parts.append('            <p class="tagline">Words on product, systems thinking and AI.</p>')
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
            display_date = format_date_for_display(post["date"])
            meta_parts.append(f'Published on: {display_date}.')
        if post['tags']:
            tag_list = ', '.join(post['tags'])
            meta_parts.append(f'Filed under: {tag_list}')

        if meta_parts:
            html_parts.append(f'                <p class="post-meta">{" ".join(meta_parts)}</p>')

        # Excerpt
        if post.get('excerpt'):
            html_parts.append(f'                <p class="post-excerpt">{post["excerpt"]}</p>')

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
