"""
Configuration constants for blog generators
"""

# Paths
METADATA_FILE = 'posts-metadata.json'
WORDS_DIR = 'words'
WORDS_ARCHIVE_FILE = 'words/index.html'

# Google Drive paths
GDRIVE_BLOG_FOLDER = 'Lab/Blog posts'

# Content types
CONTENT_TYPE_WORDS = 'words'
CONTENT_TYPE_PROJECTS = 'projects'
CONTENT_TYPE_PAGES = 'pages'

# Site metadata
SITE_NAME = 'Taken'
SITE_TAGLINE = 'Words on product, systems thinking and AI.'
SITE_LOGO_PATH = '/lib/img/ninja-trans.png'

# Navigation
NAV_ITEMS = {
    'home': {'url': '/', 'class': 'nav-red', 'label': 'Home'},
    'words': {'url': '/words/', 'class': 'nav-green', 'label': 'Words'},
    'projects': {'url': '/projects/', 'class': 'nav-yellow', 'label': 'Projects'},
    'about': {'url': '/about/', 'class': 'nav-blue', 'label': 'About'},
}

# SEO
HOMEPAGE_TITLE = 'Tom Stenson | Fractional Product Manager | Copenhagen'
HOMEPAGE_META_DESC = "Product manager, fixer & builder in Copenhagen. Fractional & interim product work. Writing about product, systems thinking and AI."
ARCHIVE_TITLE = 'Product Strategy & GenAI Articles | Tom Stenson | Copenhagen'
ARCHIVE_META_DESC = 'Writing on Product strategy, GenAI, & systems thinking. Musings on future impact.'

# Styles
STYLESHEET_PATH = '/lib/styles/styles.css'
TAG_FILTER_SCRIPT = '<script src="/tag-filter.js" defer></script>'
