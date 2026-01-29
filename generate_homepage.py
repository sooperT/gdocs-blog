#!/usr/bin/env python3
"""
Generate homepage with excerpt of latest post

Reads posts-metadata.json to find the latest "words" post, extracts an excerpt
from the full post content, and generates /index.html with standard header/nav/footer.

Usage:
    python3 generate_homepage.py
"""

import os
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from pylib.utils import format_date_for_display
from pylib.templates import html_head, site_header, site_nav, site_footer
from pylib.config import (
    METADATA_FILE, CONTENT_TYPE_WORDS, TAG_FILTER_SCRIPT,
    HOMEPAGE_TITLE, HOMEPAGE_META_DESC
)


# format_date_for_display moved to pylib.utils


class ContentExtractor(HTMLParser):
    """Extract content from post HTML, excluding title (h1), headings, and post-meta paragraph"""

    def __init__(self):
        super().__init__()
        self.in_main = False
        self.in_heading = False  # Track any heading (h1, h2, h3, h4, h5, h6)
        self.in_post_meta = False
        self.in_figcaption = False  # Track figcaption to skip caption text
        self.content_parts = []
        self.current_text = ""
        self.first_image = None  # Track first image src

    def handle_starttag(self, tag, attrs):
        if tag == 'main':
            self.in_main = True
        elif tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'] and self.in_main:
            # Skip all heading content
            self.in_heading = True
        elif tag == 'figcaption' and self.in_main:
            # Skip figcaption content (image captions)
            self.in_figcaption = True
        elif tag == 'img' and self.in_main and not self.first_image:
            # Capture first image src attribute
            for attr, value in attrs:
                if attr == 'src':
                    self.first_image = value
                    break
        elif tag == 'p' and self.in_main:
            # Check if this is the post-meta paragraph
            for attr, value in attrs:
                if attr == 'class' and 'post-meta' in value:
                    self.in_post_meta = True
                    break

    def handle_endtag(self, tag):
        if tag == 'main':
            self.in_main = False
        elif tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            self.in_heading = False
        elif tag == 'figcaption':
            self.in_figcaption = False
        elif tag == 'p':
            if self.in_post_meta:
                self.in_post_meta = False
            elif self.in_main and self.current_text.strip():
                # Save accumulated text from this paragraph (only if substantial)
                text = self.current_text.strip()
                # Skip very short paragraphs (likely just link text or fragments)
                if len(text) > 30:  # Arbitrary threshold for "real" paragraphs
                    self.content_parts.append(text)
                self.current_text = ""

    def handle_data(self, data):
        if self.in_main and not self.in_post_meta and not self.in_heading and not self.in_figcaption:
            self.current_text += data

    def get_paragraphs(self):
        """Return content as list of paragraphs"""
        return self.content_parts


def load_metadata():
    """Load posts metadata from JSON file"""
    if not os.path.exists(METADATA_FILE):
        print(f"✗ Metadata file '{METADATA_FILE}' not found")
        return None

    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get('posts', [])


def get_latest_post(posts):
    """Get the most recent 'words' post"""
    # Filter for 'words' type posts only
    words_posts = [p for p in posts if p.get('type') == CONTENT_TYPE_WORDS and p.get('date')]

    if not words_posts:
        return None

    # Sort by date (newest first)
    words_posts.sort(key=lambda p: p['date'], reverse=True)

    return words_posts[0]


def extract_excerpt_html(post_url, max_elements=3):
    """
    Extract excerpt HTML from post content, preserving semantic structure.

    Args:
        post_url: URL path like '/words/ai-glossary/'
        max_elements: Maximum number of top-level elements to include (default 3)

    Returns:
        String of raw HTML with semantic tags intact (figure, p, ul, etc.)
    """
    # Convert URL to file path
    url_parts = [p for p in post_url.split('/') if p]
    post_path = os.path.join(*url_parts, 'index.html')

    if not os.path.exists(post_path):
        print(f"✗ Post file not found: {post_path}")
        return ""

    # Read HTML
    with open(post_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Extract content between <main> tags, after post-meta
    import re
    main_match = re.search(r'<main>(.*?)</main>', html, re.DOTALL)
    if not main_match:
        return ""

    main_content = main_match.group(1)

    # Find where post-meta ends
    meta_end = main_content.find('</p>', main_content.find('class="post-meta"'))
    if meta_end == -1:
        return ""

    content_after_meta = main_content[meta_end + 4:].strip()

    # Check for excerpt end marker
    excerpt_end = content_after_meta.find('<!-- EXCERPT_END -->')
    if excerpt_end != -1:
        # Only extract content up to the marker
        content_after_meta = content_after_meta[:excerpt_end].strip()

    # Extract first N top-level elements (figure, p, ul, etc.)
    # Stop at first h2/h3 (section heading)
    elements = []
    element_count = 0
    pos = 0

    while element_count < max_elements and pos < len(content_after_meta):
        # Check for section heading - stop there
        if content_after_meta[pos:].lstrip().startswith('<h'):
            break

        # Match figure or p or ul elements
        for tag in ['figure', 'p', 'ul', 'ol']:
            pattern = f'<{tag}[^>]*>.*?</{tag}>'
            match = re.match(r'\s*' + pattern, content_after_meta[pos:], re.DOTALL)
            if match:
                elements.append(match.group().strip())
                pos += len(match.group())
                element_count += 1
                break
        else:
            # No match, move forward
            pos += 1

    return '\n        '.join(elements)


def generate_homepage_html(post):
    """Generate homepage HTML with post excerpt"""

    html_parts = []

    # HTML head with SEO meta description
    html_parts.append('<!-- Generated by: generate_homepage.py -->')
    html_parts.append('<!-- To modify: Edit generate_homepage.py and regenerate -->')
    html_parts.append(html_head(
        HOMEPAGE_TITLE,
        extra_scripts=[TAG_FILTER_SCRIPT],
        meta_description=HOMEPAGE_META_DESC
    ))

    # Header
    html_parts.append(site_header())

    # Navigation (Home is active)
    html_parts.append(site_nav('home'))

    # Welcome banner
    html_parts.append('    <!-- WELCOME MESSAGE -->')
    html_parts.append('    <div class="welcome-banner">')
    html_parts.append('        <h1>Welcome. I\'m Tom Stenson, a senior product manager &amp; systems thinker based in Copenhagen. This is where I write about product management, growth, AI, and how things connect. <a href="/about/">Here\'s my story</a>.</h1>')
    html_parts.append('    </div>')
    html_parts.append('')

    # Main content
    html_parts.append('    <!-- MAIN CONTENT -->')
    html_parts.append('    <main>')
    html_parts.append(f'        <h2>{post["title"]}</h2>')

    # Post metadata (date and tags)
    meta_parts = []
    if post.get('date'):
        display_date = format_date_for_display(post["date"])
        meta_parts.append(f'Published on: {display_date}.')
    if post.get('tags'):
        # Plain text tags (enhanced to links via JavaScript)
        tag_list = ', '.join(post['tags'])
        meta_parts.append(f'Filed under: {tag_list}')

    if meta_parts:
        html_parts.append(f'        <p class="post-meta">{" ".join(meta_parts)}</p>')

    # Extract and display excerpt HTML (preserves semantic structure)
    excerpt_html = extract_excerpt_html(post['url'])

    if excerpt_html:
        html_parts.append('')
        html_parts.append(f'        {excerpt_html}')

    # Read full article link
    html_parts.append('')
    html_parts.append(f'        <p class="read-more"><a href="{post["url"]}">Read full article →</a></p>')
    html_parts.append('    </main>')
    html_parts.append('')

    # Footer
    html_parts.append(site_footer())

    return '\n'.join(html_parts)


def main():
    print("="*60)
    print("GENERATING HOMEPAGE")
    print("="*60)
    print()

    # Load metadata
    print("Loading posts metadata...")
    posts = load_metadata()

    if not posts:
        print("✗ No posts found in metadata")
        return

    print(f"✓ Loaded {len(posts)} posts")

    # Get latest post
    print("\nFinding latest 'words' post...")
    latest_post = get_latest_post(posts)

    if not latest_post:
        print("✗ No 'words' posts found")
        return

    print(f"✓ Latest post: {latest_post['title']} ({latest_post['date']})")

    # Generate homepage HTML
    print("\nGenerating homepage HTML...")
    html = generate_homepage_html(latest_post)

    # Save to file
    output_file = 'index.html'
    print(f"Saving to {output_file}...")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print("✓ Homepage generated")
    print("\n" + "="*60)
    print("✓ SUCCESS!")
    print("="*60)
    print(f"Homepage: {output_file}")
    print(f"Latest post: {latest_post['title']}")


if __name__ == '__main__':
    main()
