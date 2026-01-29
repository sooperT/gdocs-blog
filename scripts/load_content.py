#!/usr/bin/env python3
"""Parse content and load into database with embeddings."""

import os
import re
import json
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
import requests
from html.parser import HTMLParser

load_dotenv()

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
NILEDB_URL = os.getenv("NILEDB_URL")


class HTMLTextExtractor(HTMLParser):
    """Extract text content from HTML."""
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip_tags = {'script', 'style', 'nav', 'header', 'footer'}
        self.current_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.current_skip += 1
        elif tag in ('p', 'h1', 'h2', 'h3', 'h4', 'li', 'br', 'hr'):
            self.text.append('\n')

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.current_skip -= 1
        elif tag in ('p', 'h1', 'h2', 'h3', 'h4', 'li'):
            self.text.append('\n')

    def handle_data(self, data):
        if self.current_skip == 0:
            self.text.append(data)

    def get_text(self):
        return ''.join(self.text)


def extract_text_from_html(html: str) -> str:
    """Extract clean text from HTML."""
    parser = HTMLTextExtractor()
    parser.feed(html)
    text = parser.get_text()
    # Clean up whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings from Voyage AI."""
    response = requests.post(
        "https://api.voyageai.com/v1/embeddings",
        headers={
            "Authorization": f"Bearer {VOYAGE_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "input": texts,
            "model": "voyage-3"
        }
    )
    response.raise_for_status()
    data = response.json()
    return [item["embedding"] for item in data["data"]]


def chunk_text(text: str, title: str, max_chars: int = 1500) -> list[str]:
    """Split text into chunks, preserving paragraphs."""
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = f"# {title}\n\n"

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) > max_chars and current_chunk != f"# {title}\n\n":
            chunks.append(current_chunk.strip())
            current_chunk = f"# {title} (continued)\n\n"

        current_chunk += para + "\n\n"

    if current_chunk.strip() and current_chunk != f"# {title}\n\n":
        chunks.append(current_chunk.strip())

    return chunks


def load_blog_posts(conn):
    """Load all blog posts from words/ directory."""
    cur = conn.cursor()

    # Load metadata
    metadata_file = Path("posts-metadata.json")
    if not metadata_file.exists():
        print("⚠️  No posts-metadata.json found")
        return

    with open(metadata_file) as f:
        metadata = json.load(f)

    all_chunks = []

    for post in metadata["posts"]:
        if post["type"] != "words":
            continue

        # Build path to HTML file
        slug = post["url"].strip("/").split("/")[-1]
        html_path = Path(f"words/{slug}/index.html")

        if not html_path.exists():
            print(f"  ⚠️  Missing: {html_path}")
            continue

        html_content = html_path.read_text()

        # Extract main content (between <main> tags)
        main_match = re.search(r'<main>(.*?)</main>', html_content, re.DOTALL)
        if main_match:
            main_html = main_match.group(1)
        else:
            main_html = html_content

        text_content = extract_text_from_html(main_html)
        chunks = chunk_text(text_content, post["title"])

        for chunk in chunks:
            all_chunks.append({
                "source": post["url"],
                "source_type": "blog",
                "title": post["title"],
                "content": chunk,
                "metadata": {
                    "date": post["date"],
                    "tags": post["tags"],
                    "description": post.get("meta-desc", "")
                }
            })
        print(f"  📝 {post['title']}: {len(chunks)} chunks")

    if not all_chunks:
        print("  No blog posts found")
        return

    # Get embeddings in batches
    print(f"\n  Getting embeddings for {len(all_chunks)} chunks...")
    batch_size = 20
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i+batch_size]
        texts = [c["content"] for c in batch]
        embeddings = get_embeddings(texts)

        for chunk, embedding in zip(batch, embeddings):
            cur.execute("""
                INSERT INTO chunks (source, source_type, title, content, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                chunk["source"],
                chunk["source_type"],
                chunk["title"],
                chunk["content"],
                embedding,
                json.dumps(chunk["metadata"])
            ))

        print(f"    Inserted batch {i//batch_size + 1}/{(len(all_chunks)-1)//batch_size + 1}")

    conn.commit()
    print(f"  ✅ Loaded {len(all_chunks)} blog chunks")


def load_projects(conn):
    """Load projects page content."""
    cur = conn.cursor()
    projects_file = Path("projects/index.html")

    if not projects_file.exists():
        print("⚠️  No projects/index.html found")
        return

    content = projects_file.read_text()

    # Extract main content
    main_match = re.search(r'<main>(.*?)</main>', content, re.DOTALL)
    if main_match:
        main_html = main_match.group(1)
    else:
        main_html = content

    text_content = extract_text_from_html(main_html)
    chunks = chunk_text(text_content, "Projects")

    all_chunks = []
    for chunk in chunks:
        all_chunks.append({
            "source": "/projects/",
            "source_type": "page",
            "title": "Projects",
            "content": chunk,
            "metadata": {}
        })

    if all_chunks:
        texts = [c["content"] for c in all_chunks]
        embeddings = get_embeddings(texts)

        for chunk, embedding in zip(all_chunks, embeddings):
            cur.execute("""
                INSERT INTO chunks (source, source_type, title, content, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                chunk["source"],
                chunk["source_type"],
                chunk["title"],
                chunk["content"],
                embedding,
                json.dumps(chunk["metadata"])
            ))

        conn.commit()
        print(f"  ✅ Loaded {len(all_chunks)} project chunks")


def load_about(conn):
    """Load about page content."""
    cur = conn.cursor()
    about_file = Path("about/index.html")

    if not about_file.exists():
        print("⚠️  No about/index.html found")
        return

    content = about_file.read_text()

    # Extract main content
    main_match = re.search(r'<main>(.*?)</main>', content, re.DOTALL)
    if main_match:
        main_html = main_match.group(1)
    else:
        main_html = content

    text_content = extract_text_from_html(main_html)
    chunks = chunk_text(text_content, "About Tom Stenson")

    all_chunks = []
    for chunk in chunks:
        all_chunks.append({
            "source": "/about/",
            "source_type": "about",
            "title": "About Tom Stenson",
            "content": chunk,
            "metadata": {}
        })

    if all_chunks:
        texts = [c["content"] for c in all_chunks]
        embeddings = get_embeddings(texts)

        for chunk, embedding in zip(all_chunks, embeddings):
            cur.execute("""
                INSERT INTO chunks (source, source_type, title, content, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                chunk["source"],
                chunk["source_type"],
                chunk["title"],
                chunk["content"],
                embedding,
                json.dumps(chunk["metadata"])
            ))

        conn.commit()
        print(f"  ✅ Loaded {len(all_chunks)} about chunks")


def load_aliases(conn):
    """Load name aliases."""
    cur = conn.cursor()

    aliases = [
        ("tom", "Tom Stenson", "person"),
        ("tom stenson", "Tom Stenson", "person"),
        ("stenson", "Tom Stenson", "person"),
        ("author", "Tom Stenson", "person"),
        ("you", "Tom Stenson", "person"),
        ("your", "Tom Stenson", "person"),
    ]

    for alias, canonical, entity_type in aliases:
        cur.execute("""
            INSERT INTO aliases (alias, canonical, entity_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (alias) DO NOTHING
        """, (alias, canonical, entity_type))

    conn.commit()
    print(f"  ✅ Loaded {len(aliases)} aliases")


def main():
    print("Setting up database...")
    conn = psycopg2.connect(NILEDB_URL)

    # Clear existing data
    cur = conn.cursor()
    cur.execute("TRUNCATE chunks, aliases RESTART IDENTITY;")
    conn.commit()
    print("  Cleared existing data")

    print("\nLoading content...")
    print("\n📚 Blog posts:")
    load_blog_posts(conn)

    print("\n🔧 Projects:")
    load_projects(conn)

    print("\n👤 About:")
    load_about(conn)

    print("\n🏷️  Aliases:")
    load_aliases(conn)

    # Summary
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM chunks")
    chunk_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM aliases")
    alias_count = cur.fetchone()[0]

    print(f"\n✅ Done! Loaded {chunk_count} chunks and {alias_count} aliases")

    conn.close()


if __name__ == "__main__":
    main()
