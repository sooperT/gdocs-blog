"""
Shared HTML templates for blog generators
"""
from pylib.config import (
    STYLESHEET_PATH, SITE_NAME, SITE_TAGLINE,
    SITE_LOGO_PATH, NAV_ITEMS
)


def html_head(title, extra_scripts=None, meta_description=None):
    """
    Generate HTML head section

    Args:
        title: Page title
        extra_scripts: Optional list of additional script tags to include
        meta_description: Optional meta description for SEO
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
                <h2 class="logo">{SITE_NAME}</h2>
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
