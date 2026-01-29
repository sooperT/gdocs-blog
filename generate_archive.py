#!/usr/bin/env python3
"""
Generate archive page for /words/

Reads posts-metadata.json and creates an index page
sorted by date (newest first).

Usage:
    python3 generate_archive.py
"""

import os
import json
from datetime import datetime
from pylib.utils import format_date_for_display
from pylib.templates import html_head, site_header, site_nav, site_footer
from pylib.config import (
    METADATA_FILE, CONTENT_TYPE_WORDS, TAG_FILTER_SCRIPT,
    ARCHIVE_TITLE, WORDS_ARCHIVE_FILE
)


# Note: This script now reads from posts-metadata.json instead of scanning files
# The PostMetadataExtractor class below is kept but no longer used


class PostMetadataExtractor:
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
                # Add paragraph delimiter if we're accumulating multiple
                if self.excerpt:
                    self.excerpt += "\n\n"
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
    """Read posts from posts-metadata.json"""
    posts = []

    if not os.path.exists(METADATA_FILE):
        print(f"✗ File '{METADATA_FILE}' not found")
        return posts

    # Load posts metadata
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Filter for 'words' type posts only (exclude pages)
    for post in data.get('posts', []):
        if post.get('type') == CONTENT_TYPE_WORDS and post.get('date'):
            posts.append({
                'slug': post['url'].strip('/').split('/')[-1],  # Extract slug from URL
                'title': post['title'],
                'date': post['date'],
                'tags': post.get('tags', []),
                'excerpt': post.get('excerpt', ''),
                'url': post['url']
            })
            # Display date in DD/MM/YYYY format for output
            display_date = format_date_for_display(post['date'])
            print(f"✓ Found: {post['title']} ({display_date})")

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

    # HTML head with tag-filter script
    html_parts.append('<!-- Generated by: generate_archive.py -->')
    html_parts.append('<!-- To modify: Edit generate_archive.py and regenerate -->')
    html_parts.append(html_head(ARCHIVE_TITLE, extra_scripts=[TAG_FILTER_SCRIPT]))

    # Header
    html_parts.append(site_header())

    # Navigation (words page is active)
    html_parts.append(site_nav('words'))

    # Main content
    html_parts.append('    <!-- MAIN CONTENT -->')
    html_parts.append('    <main>')
    html_parts.append('        <h1>Words</h1>')
    html_parts.append('        <p>Writing on product, systems thinking and life.</p>')
    html_parts.append('')
    html_parts.append('        <div class="post-listing">')

    # Add each post
    for post in posts_sorted:
        # Build data-tags attribute
        tags_attr = ','.join(post['tags']) if post['tags'] else ''
        html_parts.append(f'            <article class="post-preview" data-tags="{tags_attr}">')
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

        # Excerpt (support multi-paragraph excerpts split by \n\n)
        if post.get('excerpt'):
            paragraphs = post['excerpt'].split('\n\n')
            for para in paragraphs:
                if para.strip():  # Only add non-empty paragraphs
                    html_parts.append(f'                <p class="post-excerpt">{para.strip()}</p>')

        html_parts.append('            </article>')

    html_parts.append('        </div>')
    html_parts.append('    </main>')
    html_parts.append('')

    # Footer
    html_parts.append(site_footer())

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
    print(f"Saving to {WORDS_ARCHIVE_FILE}...")

    with open(WORDS_ARCHIVE_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    print("✓ Archive page generated")
    print("\n" + "="*60)
    print("✓ SUCCESS!")
    print("="*60)
    print(f"Archive page: {WORDS_ARCHIVE_FILE}")
    print(f"Total posts: {len(posts)}")


if __name__ == '__main__':
    main()
