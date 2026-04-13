"""
Shared HTML templates for blog generators
"""
from pylib.config import (
    STYLESHEET_PATH, SITE_NAME, SITE_TAGLINE,
    SITE_LOGO_PATH, NAV_ITEMS
)


NO_CRT_STYLE = """    <style>
        /* Override CRT effects for this post */
        main p > img,
        main figure img {
            filter: none !important;
            border-radius: 0 !important;
            position: relative;
            z-index: 10000;
            background: white;
        }
        main p:has(> img:only-child)::after,
        main p:has(> img:only-child)::before {
            content: none !important;
        }
    </style>"""


def html_head(title, extra_scripts=None, meta_description=None, no_crt=False):
    """
    Generate HTML head section

    Args:
        title: Page title
        extra_scripts: Optional list of additional script tags to include
        meta_description: Optional meta description for SEO
        no_crt: If True, inject styles to disable CRT image effects
    """
    parts = [
        '<!DOCTYPE html>',
        '<!-- GENERATED FILE - DO NOT EDIT MANUALLY -->',
        '<html lang="en">',
        '<head>',
        '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'    <title>{title}</title>',
    ]

    # Add meta description if provided
    if meta_description:
        parts.append(f'    <meta name="description" content="{meta_description}">')

    parts.append(f'    <link rel="stylesheet" href="{STYLESHEET_PATH}">')
    parts.append('    <link rel="icon" type="image/png" href="/favicon.png">')

    # Add no-CRT override styles if requested
    if no_crt:
        parts.append(NO_CRT_STYLE)

    # Add Umami analytics tracking
    parts.append('    <script defer src="https://cloud.umami.is/script.js" data-website-id="6e0b4ebe-2b6a-4583-9ceb-8316259c5600"></script>')

    # Add extra scripts if provided
    if extra_scripts:
        for script in extra_scripts:
            parts.append(f'    {script}')

    parts.extend([
        '</head>',
        '<body>',
        '    <div class="crt-overlay"></div>',
        '',
    ])

    return '\n'.join(parts)


def site_header():
    """Generate site header"""
    return f'''    <!-- HEADER -->
    <header class="site-header">
        <div class="identity">
            <div class="logo-container">
                <a href="/" class="logo">{SITE_NAME}</a>
                <img class="ninja-icon" src="{SITE_LOGO_PATH}" alt="Ninja">
            </div>
            <p class="tagline">{SITE_TAGLINE}</p>
        </div>
    </header>
'''


def site_nav(active_page=''):
    """
    Generate site navigation

    Args:
        active_page: Which page is active ('home', 'words', 'projects', 'about')
    """
    parts = ['    <!-- NAVIGATION -->', '    <nav class="site-nav">']

    for page, info in NAV_ITEMS.items():
        active_class = ' active' if page == active_page else ''
        parts.append(f'        <a href="{info["url"]}" class="{info["class"]}{active_class}">{info["label"]}</a>')

    parts.append('    </nav>')
    parts.append('')

    return '\n'.join(parts)


def site_footer():
    """Generate site footer"""
    return '''    <!-- FOOTER -->
    <footer class="site-footer">
        <p>Code created with AI — Words are my own</p>
    </footer>
</body>
</html>'''
