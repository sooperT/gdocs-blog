#!/usr/bin/env python3
"""
Regenerate all published posts/pages with updated templates
(e.g., after adding analytics tracking)
"""

import json
import subprocess
import sys

METADATA_FILE = "posts-metadata.json"

def main():
    print("=" * 60)
    print("REGENERATING ALL PUBLISHED CONTENT")
    print("=" * 60)
    print()

    # Load metadata
    with open(METADATA_FILE, 'r') as f:
        data = json.load(f)

    posts = [p for p in data['posts'] if p['type'] in ['words', 'projects']]

    if not posts:
        print("No posts found to regenerate")
        return

    print(f"Found {len(posts)} posts to regenerate:")
    for post in posts:
        print(f"  - {post['title']}")
    print()
    print("Regenerating posts...")
    print("-" * 60)

    for post in posts:
        title = post['title']
        print(f"\nRegenerating: {title}")

        try:
            result = subprocess.run(
                ['python3', 'publish.py', title],
                input='yes\n',  # Auto-approve
                text=True,
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0:
                print(f"✓ Success: {title}")
            else:
                print(f"✗ Failed: {title}")
                print(f"  Error: {result.stderr[:200]}")
        except Exception as e:
            print(f"✗ Error: {title} - {e}")

    print()
    print("-" * 60)
    print("Regenerating homepage and archive...")

    # Regenerate homepage
    subprocess.run(['python3', 'generate_homepage.py'], check=True)

    # Regenerate archive
    subprocess.run(['python3', 'generate_archive.py'], check=True)

    print()
    print("=" * 60)
    print("✓ ALL CONTENT REGENERATED")
    print("=" * 60)

if __name__ == '__main__':
    main()
