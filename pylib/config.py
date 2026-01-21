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
HOMEPAGE_TITLE = 'Tom Stenson | Senior Product Manager | Systems Thinking | Copenhagen'
HOMEPAGE_META_DESC = "I'm Tom Stenson, a Senior Product Manager in Copenhagen. Writing about product management, growth, AI, and systems thinking."
ARCHIVE_TITLE = 'Words - taken'

# Styles
STYLESHEET_PATH = '/lib/styles/styles.css'
TAG_FILTER_SCRIPT = '<script src="/tag-filter.js" defer></script>'
