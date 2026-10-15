#!/usr/bin/env python3
"""Tell Bing (and the other IndexNow engines) which takenbyninjas.com pages changed.

Copilot answers from Bing's index, so an agent page Bing has not recrawled is
an agent page Copilot answers from stale. One POST carries every URL, with no
daily quota, unlike the Request-indexing button in Webmaster Tools.

Usage:
    python3 scripts/indexnow.py --changed            # pages changed by HEAD (default: HEAD~1..HEAD)
    python3 scripts/indexnow.py --changed origin/main@{1}..origin/main
    python3 scripts/indexnow.py --all                # every URL in both sitemaps
    python3 scripts/indexnow.py /for-agents/ /words/kitten-pm/
    add --dry-run to list without pinging

Every URL is fetched first and must return 200 without a noindex, so a ping
never points Bing at a page that is not live yet: run this AFTER the Netlify
deploy has landed, not right after git push. Exit 1 if any URL was skipped or
the ping was refused.

Key: fc3c395c151aeaf226a0299dd43dce31.txt at the site root (served by Netlify).
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from pylib.config import SITE_URL  # noqa: E402

HOST = SITE_URL.replace('https://', '')
KEY = 'fc3c395c151aeaf226a0299dd43dce31'
ENDPOINT = 'https://api.indexnow.org/indexnow'
SITEMAPS = ('sitemap.xml', 'sitemap-agent.xml')
NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
UA = 'takenbyninjas-indexnow/1 (+https://takenbyninjas.com/)'


def sitemap_urls():
    urls = []
    for sm in SITEMAPS:
        tree = ET.parse(os.path.join(ROOT, sm))
        urls += [u.find('s:loc', NS).text for u in tree.findall('.//s:url', NS)]
    return urls


def path_to_url(path):
    """Repo path -> site URL, or None for files that are not pages."""
    if path.endswith('/index.html'):
        d = path[:-len('index.html')]
        return SITE_URL + '/' + d if d else SITE_URL + '/'
    if path in ('llms.txt', 'for-agents/start.md'):
        return f'{SITE_URL}/{path}'
    return None


def changed_urls(rev_range):
    out = subprocess.run(['git', 'diff', '--name-only', rev_range], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split()
    listed = set(sitemap_urls())
    urls = []
    for p in out:
        u = path_to_url(p)
        if u and u in listed and u not in urls:   # sitemap membership keeps unlisted/noindex pages out
            urls.append(u)
    return urls


def live(url):
    """(ok, reason): 200, HTML or text, and no noindex in header or meta."""
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            if 'noindex' in r.headers.get('X-Robots-Tag', ''):
                return False, 'X-Robots-Tag noindex'
            body = r.read(200000).decode('utf-8', 'replace')
    except Exception as e:  # noqa: BLE001
        return False, str(e)
    if re.search(r'<meta name="robots" content="[^"]*noindex', body):
        return False, 'meta noindex'
    return True, 'ok'


def ping(urls):
    payload = json.dumps({'host': HOST, 'key': KEY, 'urlList': urls}).encode()
    req = urllib.request.Request(ENDPOINT, data=payload, method='POST',
                                 headers={'Content-Type': 'application/json; charset=utf-8', 'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')


def main(argv):
    dry = '--dry-run' in argv
    argv = [a for a in argv if a != '--dry-run']
    if not argv or argv[0] == '--changed':
        rev = argv[1] if len(argv) > 1 else 'HEAD~1..HEAD'
        urls = changed_urls(rev)
        print(f'Pages changed in {rev}: {len(urls)}')
    elif argv[0] == '--all':
        urls = sitemap_urls()
        print(f'Every sitemap URL: {len(urls)}')
    else:
        urls = [a if a.startswith('http') else SITE_URL + a for a in argv]
    if not urls:
        print('Nothing to ping.')
        return 0

    keep, skipped = [], 0
    for u in urls:
        ok, why = live(u)
        print(f"  {'✓' if ok else '✗'} {u}{'' if ok else '  (' + why + ')'}")
        if ok:
            keep.append(u)
        else:
            skipped += 1
    if dry:
        print(f'Dry run: would ping {len(keep)} URL(s).')
        return 1 if skipped else 0
    if not keep:
        print('No live URLs to ping.')
        return 1
    status, body = ping(keep)
    accepted = status in (200, 202)
    print(f"{'✓' if accepted else '✗'} IndexNow {status} for {len(keep)} URL(s){(': ' + body.strip()) if body.strip() else ''}")
    return 0 if accepted and not skipped else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
