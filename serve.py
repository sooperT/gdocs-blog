#!/usr/bin/env python3
"""
Local preview server for blog development

Runs a simple HTTP server to preview the blog locally before deploying.
This helps conserve Netlify build credits by allowing local iteration.

Usage:
    python3 serve.py

The server will start at http://localhost:8000
Press Ctrl+C to stop the server.
"""

import http.server
import socketserver
import webbrowser
import os

PORT = 8000

class Handler(http.server.SimpleHTTPRequestHandler):
    """Custom handler to suppress log messages for a cleaner output"""

    def log_message(self, format, *args):
        # Only log errors, suppress normal requests
        if args[1][0] not in ('2', '3'):
            super().log_message(format, *args)


def main():
    # Change to script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 60)
    print("BLOG PREVIEW SERVER")
    print("=" * 60)
    print(f"\nStarting server at http://localhost:{PORT}")
    print("\nAvailable pages:")
    print(f"  - Homepage:     http://localhost:{PORT}/")
    print(f"  - Words:        http://localhost:{PORT}/words/")
    print(f"  - Projects:     http://localhost:{PORT}/projects/")
    print(f"  - About:        http://localhost:{PORT}/about/")
    print(f"  - Playground:   http://localhost:{PORT}/playground.html")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60)
    print()

    # Open browser automatically
    webbrowser.open(f'http://localhost:{PORT}')

    # Start server
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n" + "=" * 60)
            print("Server stopped")
            print("=" * 60)


if __name__ == '__main__':
    main()
