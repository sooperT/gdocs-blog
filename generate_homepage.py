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
from html.parser import HTMLParser


class ContentExtractor(HTMLParser):
    """Extract content from post HTML, excluding post-meta paragraph"""

    def __init__(self):
        super().__init__()
        self.in_main = False
        self.in_post_meta = False
        self.content_parts = []
        self.current_text = ""

    def handle_starttag(self, tag, attrs):
        if tag == 'main':
            self.in_main = True
        elif tag == 'p' and self.in_main:
            # Check if this is the post-meta paragraph
            for attr, value in attrs:
                if attr == 'class' and 'post-meta' in value:
                    self.in_post_meta = True
                    break

    def handle_endtag(self, tag):
        if tag == 'main':
            self.in_main = False
        elif tag == 'p':
            if self.in_post_meta:
                self.in_post_meta = False
            elif self.in_main and self.current_text.strip():
                # Save accumulated text from this paragraph
                self.content_parts.append(self.current_text.strip())
                self.current_text = ""

    def handle_data(self, data):
        if self.in_main and not self.in_post_meta:
            self.current_text += data

    def get_content(self):
        """Return all content as plain text, space-separated"""
        return ' '.join(self.content_parts)


def load_metadata():
    """Load posts metadata from JSON file"""
    metadata_file = 'posts-metadata.json'

    if not os.path.exists(metadata_file):
        print(f"✗ Metadata file '{metadata_file}' not found")
        return None

    with open(metadata_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get('posts', [])


def get_latest_post(posts):
    """Get the most recent 'words' post"""
    # Filter for 'words' type posts only
    words_posts = [p for p in posts if p.get('type') == 'words' and p.get('date')]

    if not words_posts:
        return None

    # Sort by date (newest first)
    words_posts.sort(key=lambda p: p['date'], reverse=True)

    return words_posts[0]


def extract_excerpt(post_url, max_chars=500):
    """
    Extract excerpt from post HTML content

    Args:
        post_url: URL path like '/words/ai-glossary/'
        max_chars: Maximum characters for excerpt (default 500)

    Returns:
        Truncated excerpt with '...' if content was cut
    """
    # Convert URL to file path
    # /words/ai-glossary/ -> words/ai-glossary/index.html
    url_parts = [p for p in post_url.split('/') if p]
    post_path = os.path.join(*url_parts, 'index.html')

    if not os.path.exists(post_path):
        print(f"✗ Post file not found: {post_path}")
        return ""

    # Read and parse HTML
    with open(post_path, 'r', encoding='utf-8') as f:
        html = f.read()

    parser = ContentExtractor()
    parser.feed(html)
    content = parser.get_content()

    # Truncate to max_chars at word boundary
    if len(content) <= max_chars:
        return content

    # Find the last space before max_chars
    truncated = content[:max_chars]
    last_space = truncated.rfind(' ')

    if last_space > 0:
        truncated = truncated[:last_space]

    return truncated + "..."


def generate_homepage_html(post):
    """Generate homepage HTML with post excerpt"""

    html_parts = []

    # HTML head
    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<html lang="en">')
    html_parts.append('<head>')
    html_parts.append('    <meta charset="UTF-8">')
    html_parts.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    html_parts.append(f'    <title>{post["meta-title"]}</title>')

    # Use post's meta-desc if available
    if post.get('meta-desc'):
        html_parts.append(f'    <meta name="description" content="{post["meta-desc"]}">')

    html_parts.append('    <link rel="stylesheet" href="/styles.css">')
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

    # Navigation (Home is active)
    html_parts.append('    <!-- NAVIGATION -->')
    html_parts.append('    <nav class="site-nav">')
    html_parts.append('        <a href="/" class="nav-red active">Home</a>')
    html_parts.append('        <a href="/words/" class="nav-green">Words</a>')
    html_parts.append('        <a href="/projects/" class="nav-yellow">Projects</a>')
    html_parts.append('        <a href="/about/" class="nav-blue">About</a>')
    html_parts.append('    </nav>')
    html_parts.append('')

    # Main content
    html_parts.append('    <!-- MAIN CONTENT -->')
    html_parts.append('    <main>')
    html_parts.append(f'        <h1>{post["title"]}</h1>')

    # Post metadata (date and tags)
    meta_parts = []
    if post.get('date'):
        meta_parts.append(f'Published on: {post["date"]}.')
    if post.get('tags'):
        # Convert tags to clickable links (uppercase via CSS)
        tag_links = [f'<a href="/words/?tag={tag}">{tag}</a>' for tag in post['tags']]
        tag_list = ', '.join(tag_links)
        meta_parts.append(f'Filed under: {tag_list}')

    if meta_parts:
        html_parts.append(f'        <p class="post-meta">{" ".join(meta_parts)}</p>')

    # Extract and display excerpt
    excerpt = extract_excerpt(post['url'])
    if excerpt:
        html_parts.append('')
        html_parts.append(f'        <p class="post-excerpt">{excerpt}</p>')

    # Read full article link
    html_parts.append('')
    html_parts.append(f'        <p class="read-more"><a href="{post["url"]}">Read full article →</a></p>')
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
