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
BLOG_FOLDER_PATH = "Lab/Blog posts"

# Output file
OUTPUT_FILE = "index.html"


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


def convert_to_html(document):
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

    # HTML head
    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<html lang="en">')
    html_parts.append('<head>')
    html_parts.append('    <meta charset="UTF-8">')
    html_parts.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    html_parts.append(f'    <title>{title}</title>')
    html_parts.append('    <link rel="stylesheet" href="styles.css">')
    html_parts.append('</head>')
    html_parts.append('<body>')
    html_parts.append('    <div class="crt-overlay"></div>')
    html_parts.append('    <main>')

    # Process document content
    content = document.get('body', {}).get('content', [])

    for element in content:
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
                    if 'textRun' in elem:
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

    # Close HTML
    html_parts.append('    </main>')
    html_parts.append('</body>')
    html_parts.append('</html>')

    return '\n'.join(html_parts)


def git_commit_and_push(filename, doc_title):
    """Commit and push changes to GitHub"""
    print("\nCommitting to git...")

    try:
        # Add the file
        subprocess.run(['git', 'add', filename], check=True)

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

        # Find document
        doc_id = find_document(drive_service, doc_name, blog_folder_id)

        # Read document
        document = read_document(docs_service, doc_id)

        # Convert to HTML
        print("Converting to HTML...")
        html = convert_to_html(document)
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

        # User approved - save to actual file
        print(f"\n✓ Approved! Publishing to {OUTPUT_FILE}...")
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(html)
        print("✓ File saved")

        # Clean up preview file
        if os.path.exists(preview_file):
            os.remove(preview_file)

        # Git commit and push
        git_commit_and_push(OUTPUT_FILE, document.get('title'))

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
