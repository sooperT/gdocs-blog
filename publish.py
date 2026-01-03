#!/usr/bin/env python3
"""
Publish a Google Doc as a blog post

Usage:
    python3 publish.py "My first blog post"

Requirements:
    - Google OAuth credentials in client_secret_*.json
    - Document must be in "Lab/Blog posts" folder in Google Drive
"""

import os
import sys
import subprocess
import re
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Google API scopes
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/documents.readonly'
]

# Blog folder path in Google Drive
BLOG_FOLDER_PATH = "09 Lab/Taken"

# Output file (will be determined based on content type and slug)
OUTPUT_FILE = "index.html"  # Default for backwards compatibility


def authenticate():
    """Authenticate with Google APIs and return credentials"""
    creds = None

    # Load existing token if available
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # Refresh or create new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing credentials...")
            creds.refresh(Request())
        else:
            print("Starting OAuth flow...")
            # Find credentials file
            cred_file = None
            for f in os.listdir('.'):
                if f.startswith('client_secret_') and f.endswith('.json'):
                    cred_file = f
                    break

            if not cred_file:
                raise FileNotFoundError(
                    "No client_secret_*.json file found. "
                    "Please download OAuth credentials from Google Cloud Console."
                )

            flow = InstalledAppFlow.from_client_secrets_file(cred_file, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for next time
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


def parse_uk_date(date_str):
    """
    Parse UK format dates: d-mm-yyyy or dd-mm-yyyy
    Returns ISO format: yyyy-mm-dd
    """
    # Try to parse UK date format (day-month-year)
    patterns = [
        r'(\d{1,2})-(\d{2})-(\d{4})',  # d-mm-yyyy or dd-mm-yyyy
        r'(\d{4})-(\d{2})-(\d{2})'      # yyyy-mm-dd (already ISO)
    ]

    for pattern in patterns:
        match = re.match(pattern, date_str.strip())
        if match:
            parts = match.groups()
            if len(parts[0]) == 4:  # Already ISO format
                return date_str.strip()
            else:  # UK format - convert to ISO
                day, month, year = parts
                return f"{year}-{month}-{day.zfill(2)}"

    raise ValueError(f"Could not parse date: {date_str}")


def parse_frontmatter(document):
    """
    Parse frontmatter from document content
    Format:
        url: my-slug
        date: 12-11-2025
        meta-desc: Description here
        tags: tag1, tag2
        —---------------- (separator)

    Returns: (metadata dict, content without frontmatter)
    """
    content = document.get('body', {}).get('content', [])
    metadata = {}
    frontmatter_lines = []
    content_start_index = 0
    in_frontmatter = True

    # Extract text from document
    for idx, element in enumerate(content):
        if 'paragraph' in element:
            paragraph = element['paragraph']
            text = ''
            for elem in paragraph.get('elements', []):
                if 'textRun' in elem:
                    text += elem['textRun'].get('content', '')

            text = text.strip()

            # Check for frontmatter separator (em-dash or regular dash line)
            if text and (text.startswith('—') or text.startswith('---')):
                content_start_index = idx + 1
                in_frontmatter = False
                break

            # Parse frontmatter key: value pairs
            if text and ':' in text:
                key, value = text.split(':', 1)
                metadata[key.strip()] = value.strip()

    return metadata, content_start_index


def detect_content_type(drive_service, document_id):
    """
    Detect content type (words/projects/pages) from folder location
    Returns: 'words', 'projects', or 'pages'
    """
    # Get file metadata including parents
    file = drive_service.files().get(
        fileId=document_id,
        fields='parents'
    ).execute()

    parent_id = file.get('parents', [])[0] if file.get('parents') else None

    if not parent_id:
        return 'words'  # Default

    # Get parent folder name
    parent = drive_service.files().get(
        fileId=parent_id,
        fields='name'
    ).execute()

    folder_name = parent.get('name', '').lower()

    if folder_name in ['words', 'projects', 'pages']:
        return folder_name

    return 'words'  # Default


def find_folder_by_path(drive_service, folder_path):
    """
    Find a folder by its path (e.g., 'Lab/Blog posts')
    Returns the folder ID
    """
    print(f"Finding folder: '{folder_path}'...")

    parts = [p.strip() for p in folder_path.split('/')]
    current_parent = 'root'

    for part in parts:
        query = f"name='{part}' and mimeType='application/vnd.google-apps.folder' and '{current_parent}' in parents and trashed=false"

        results = drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()

        items = results.get('files', [])

        if not items:
            raise FileNotFoundError(f"Folder '{part}' not found in path '{folder_path}'")

        current_parent = items[0]['id']

    print(f"✓ Found folder")
    return current_parent


def find_document(drive_service, doc_name, folder_id):
    """Search for a document by name within a specific folder"""
    print(f"Searching for document: '{doc_name}'...")

    query = f"name='{doc_name}' and mimeType='application/vnd.google-apps.document' and '{folder_id}' in parents and trashed=false"

    results = drive_service.files().list(
        q=query,
        spaces='drive',
        fields='files(id, name, modifiedTime)'
    ).execute()

    items = results.get('files', [])

    if not items:
        raise FileNotFoundError(f"Document '{doc_name}' not found in folder")

    doc = items[0]
    print(f"✓ Found document (modified: {doc.get('modifiedTime')})")
    return doc['id']


def read_document(docs_service, document_id):
    """Read a Google Doc and return its content"""
    print("Reading document...")
    document = docs_service.documents().get(documentId=document_id).execute()
    print(f"✓ Loaded: {document.get('title')}")
    return document


def convert_to_html(document, metadata, content_start_index=0, content_type='words'):
    """
    Convert Google Docs document to HTML

    Style mapping:
    - TITLE → <h1>
    - HEADING_1 → <h2>
    - HEADING_2 → <h3>
    - HEADING_3 → <h4>
    - SUBTITLE → <h2>
    - NORMAL_TEXT → <p>
    """

    STYLE_MAP = {
        'TITLE': 'h1',
        'HEADING_1': 'h2',
        'HEADING_2': 'h3',
        'HEADING_3': 'h4',
        'SUBTITLE': 'h2',
        'NORMAL_TEXT': 'p'
    }

    html_parts = []
    title = document.get('title', 'Untitled')
    meta_desc = metadata.get('meta-desc', '')

    # Determine CSS path based on content type
    css_path = 'styles.css' if content_type == 'pages' else '../../styles.css'

    # HTML head
    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<html lang="en">')
    html_parts.append('<head>')
    html_parts.append('    <meta charset="UTF-8">')
    html_parts.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    html_parts.append(f'    <title>{title} - taken</title>')
    if meta_desc:
        html_parts.append(f'    <meta name="description" content="{meta_desc}">')
    html_parts.append(f'    <link rel="stylesheet" href="{css_path}">')
    html_parts.append('</head>')
    html_parts.append('<body>')
    html_parts.append('    <div class="crt-overlay"></div>')
    html_parts.append('')
    html_parts.append('    <!-- HEADER -->')
    html_parts.append('    <header class="site-header">')
    html_parts.append('        <div class="identity">')
    html_parts.append('            <h1 class="logo"><span class="logo-t">T</span><span class="logo-aken">aken</span></h1>')
    html_parts.append('            <div class="ninja-icon">🥷</div>')
    html_parts.append('            <p class="tagline">Words on product, systems thinking and life.</p>')
    html_parts.append('        </div>')
    html_parts.append('    </header>')
    html_parts.append('')
    html_parts.append('    <!-- NAVIGATION -->')
    html_parts.append('    <nav class="site-nav">')
    html_parts.append('        <a href="/" class="nav-red">Home</a>')
    html_parts.append('        <a href="/words/" class="nav-green">Words</a>')
    html_parts.append('        <a href="/projects/" class="nav-yellow">Projects</a>')
    html_parts.append('        <a href="/about/" class="nav-blue">About</a>')
    html_parts.append('    </nav>')
    html_parts.append('')
    html_parts.append('    <!-- MAIN CONTENT -->')
    html_parts.append('    <main>')

    # Process document content (skip frontmatter)
    # We'll inject metadata after the first h1
    content = document.get('body', {}).get('content', [])
    inline_objects = document.get('inlineObjects', {})

    metadata_injected = False

    for idx, element in enumerate(content):
        # Skip frontmatter
        if idx < content_start_index:
            continue
        if 'paragraph' in element:
            paragraph = element['paragraph']

            # Get paragraph style
            style = paragraph.get('paragraphStyle', {})
            named_style = style.get('namedStyleType', 'NORMAL_TEXT')

            # Get HTML tag for this style
            tag = STYLE_MAP.get(named_style, 'p')

            # Process text content with inline formatting
            html_content = ""
            if 'elements' in paragraph:
                for elem in paragraph['elements']:
                    # Handle inline images
                    if 'inlineObjectElement' in elem:
                        object_id = elem['inlineObjectElement']['inlineObjectId']
                        if object_id in inline_objects:
                            inline_obj = inline_objects[object_id]
                            image_props = inline_obj.get('inlineObjectProperties', {})
                            embedded_obj = image_props.get('embeddedObject', {})

                            # Get image URL
                            image_url = embedded_obj.get('imageProperties', {}).get('contentUri', '')

                            if image_url:
                                # Get alt text if available
                                alt_text = embedded_obj.get('title', 'Image')
                                html_content += f'<img src="{image_url}" alt="{alt_text}">'

                    elif 'textRun' in elem:
                        text_run = elem['textRun']
                        text = text_run.get('content', '')

                        # Check for inline formatting
                        text_style = text_run.get('textStyle', {})

                        # Build formatted text
                        formatted_text = text

                        # Handle links
                        if 'link' in text_style:
                            url = text_style['link'].get('url', '')
                            formatted_text = f'<a href="{url}">{formatted_text}</a>'

                        # Handle bold
                        if text_style.get('bold'):
                            formatted_text = f'<strong>{formatted_text}</strong>'

                        # Handle italic
                        if text_style.get('italic'):
                            formatted_text = f'<em>{formatted_text}</em>'

                        html_content += formatted_text

            # Only add paragraph if it has content
            if html_content.strip():
                html_parts.append(f'    <{tag}>{html_content.rstrip()}</{tag}>')

                # Inject metadata after first h1 (title)
                if not metadata_injected and tag == 'h1' and content_type in ['words', 'projects']:
                    if metadata.get('date') or metadata.get('tags'):
                        meta_parts = []
                        if metadata.get('date'):
                            meta_parts.append(f'Published on: {metadata["date"]}.')
                        if metadata.get('tags'):
                            tags = [tag.strip() for tag in metadata['tags'].split(',')]
                            tag_list = ', '.join(tags)
                            meta_parts.append(f'Filed under: {tag_list}')

                        if meta_parts:
                            html_parts.append(f'    <p class="post-meta">{" ".join(meta_parts)}</p>')
                        metadata_injected = True

    # Close HTML
    html_parts.append('    </main>')
    html_parts.append('')
    html_parts.append('    <!-- FOOTER -->')
    html_parts.append('    <footer class="site-footer">')
    html_parts.append('        <p>Code created with AI — Words are my own</p>')
    html_parts.append('    </footer>')
    html_parts.append('</body>')
    html_parts.append('</html>')

    return '\n'.join(html_parts)


def git_commit_and_push(filename, doc_title, include_archive=False):
    """Commit and push changes to GitHub"""
    print("\nCommitting to git...")

    try:
        # Add the post file
        subprocess.run(['git', 'add', filename], check=True)

        # Also add archive if regenerated
        if include_archive:
            subprocess.run(['git', 'add', 'words/index.html'], check=True)

        # Create commit message
        commit_msg = f"""Publish: {doc_title}

Updated blog post from Google Docs.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"""

        # Commit
        subprocess.run(['git', 'commit', '-m', commit_msg], check=True)

        # Push
        subprocess.run(['git', 'push'], check=True)

        print("✓ Committed and pushed to GitHub")

    except subprocess.CalledProcessError as e:
        print(f"⚠ Git operation failed: {e}")
        print("You may need to commit and push manually")


def main():
    """Main publishing workflow"""
    if len(sys.argv) < 2:
        print("Usage: python3 publish.py \"Document Name\"")
        print("\nExample:")
        print("  python3 publish.py \"My first blog post\"")
        sys.exit(1)

    doc_name = sys.argv[1]

    print("="*60)
    print("PUBLISHING BLOG POST")
    print("="*60)
    print(f"Document: {doc_name}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    try:
        # Authenticate
        creds = authenticate()

        # Build API services
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)

        # Find blog folder
        blog_folder_id = find_folder_by_path(drive_service, BLOG_FOLDER_PATH)

        # Search all subfolders for the document
        print(f"Searching for document in all content folders...")
        doc_id = None
        content_type = 'words'  # default

        for folder_name in ['words', 'projects', 'pages']:
            try:
                # Find subfolder
                query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{blog_folder_id}' in parents and trashed=false"
                results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
                items = results.get('files', [])

                if items:
                    subfolder_id = items[0]['id']
                    # Try to find document in this folder
                    doc_id = find_document(drive_service, doc_name, subfolder_id)
                    content_type = folder_name
                    print(f"✓ Found in /{folder_name}/ folder")
                    break
            except FileNotFoundError:
                continue

        if not doc_id:
            raise FileNotFoundError(f"Document '{doc_name}' not found in any content folder (words/projects/pages)")

        # Read document
        document = read_document(docs_service, doc_id)

        # Parse frontmatter
        print("Parsing frontmatter...")
        metadata, content_start_index = parse_frontmatter(document)
        print(f"✓ Metadata: {metadata}")

        # Parse and normalize date
        if 'date' in metadata:
            metadata['date'] = parse_uk_date(metadata['date'])
            print(f"✓ Date normalized: {metadata['date']}")

        # Get URL slug from metadata
        url_slug = metadata.get('url', doc_name.lower().replace(' ', '-'))

        # Convert to HTML
        print("Converting to HTML...")
        html = convert_to_html(document, metadata, content_start_index, content_type)
        print("✓ Conversion complete")

        # Save to preview file
        preview_file = "preview.html"
        print(f"\nSaving preview to {preview_file}...")
        with open(preview_file, 'w', encoding='utf-8') as f:
            f.write(html)
        print("✓ Preview saved")

        # Open in browser for review
        print("\nOpening preview in browser...")
        subprocess.run(['open', preview_file])

        # Ask for approval
        print("\n" + "="*60)
        print("REVIEW THE PREVIEW IN YOUR BROWSER")
        print("="*60)
        response = input("\nDoes the preview look good? Publish to blog? (yes/no): ").strip().lower()

        if response not in ['yes', 'y']:
            print("\n✗ Publishing cancelled")
            print(f"Preview saved in {preview_file} for your review")
            sys.exit(0)

        # User approved - determine output path
        if content_type == 'pages':
            # Pages go directly in their folder (e.g., /about/index.html)
            output_dir = url_slug
            output_file = os.path.join(output_dir, 'index.html')
        else:
            # Words/projects go in /{type}/{slug}/index.html
            output_dir = os.path.join(content_type, url_slug)
            output_file = os.path.join(output_dir, 'index.html')

        # Create directory if needed
        print(f"\n✓ Approved! Publishing to /{output_file}...")
        os.makedirs(output_dir, exist_ok=True)

        # Save file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        print("✓ File saved")

        # Clean up preview file
        if os.path.exists(preview_file):
            os.remove(preview_file)

        # Regenerate archive if this is a words post
        archive_updated = False
        if content_type == 'words':
            print("\nRegenerating archive page...")
            try:
                subprocess.run(['python3', 'generate_archive.py'], check=True, capture_output=True)
                print("✓ Archive updated")
                archive_updated = True
            except subprocess.CalledProcessError as e:
                print(f"⚠ Warning: Archive generation failed: {e}")

        # Git commit and push (include archive in same commit if updated)
        git_commit_and_push(output_file, document.get('title'), include_archive=archive_updated)

        print("\n" + "="*60)
        print("✓ SUCCESS! Blog post published")
        print("="*60)
        print(f"Your blog should update automatically via Netlify")

    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
