/**
 * Tag Enhancement & Filtering Module (Progressive Enhancement)
 *
 * Works across all pages:
 * - Converts plain text tags to clickable links
 * - On archive page: adds filtering functionality
 *
 * Without JavaScript: all pages show plain text tags
 */

class TagFilter {
    constructor() {
        this.activeTags = [];
        this.isArchivePage = !!document.querySelector('.post-listing');
        this.init();
    }

    async init() {
        // Always enhance tag links on all pages
        this.enhanceTagLinks();

        // Only add filtering functionality on archive page
        if (this.isArchivePage) {
            // Parse URL parameters
            this.parseURLParams();

            // Apply filtering if tags are active
            if (this.activeTags.length > 0) {
                this.filterPosts();
                this.renderFilterUI();
            }

            // Setup click handlers for filtering
            this.setupTagClickHandlers();
        }
    }

    parseURLParams() {
        const params = new URLSearchParams(window.location.search);
        const tagParam = params.get('tag');

        if (tagParam) {
            this.activeTags = tagParam.split(',').map(t => t.trim()).filter(t => t);
        }
    }

    enhanceTagLinks() {
        // Find all post-meta paragraphs and convert plain text tags to links
        document.querySelectorAll('.post-meta').forEach(meta => {
            const text = meta.textContent;
            const match = text.match(/Filed under: (.+)/);

            if (match) {
                const tagsText = match[1];
                const tags = tagsText.split(', ').map(t => t.trim());

                // Build clickable tag links
                const tagsHTML = tags.map(tag =>
                    `<a href="/words/?tag=${encodeURIComponent(tag)}" class="tag-link" data-tag="${tag}">${tag}</a>`
                ).join(', ');

                // Replace plain text with links
                const dateMatch = text.match(/Published on: (.+?)\./);
                const date = dateMatch ? dateMatch[1] : '';

                meta.innerHTML = `${date ? `Published on: ${date}. ` : ''}Filed under: ${tagsHTML}`;
            }
        });
    }

    filterPosts() {
        // Hide/show articles based on data-tags attribute
        document.querySelectorAll('.post-preview').forEach(article => {
            const articleTags = article.dataset.tags ? article.dataset.tags.split(',') : [];

            // AND logic: article must have ALL active tags
            const matches = this.activeTags.every(tag => articleTags.includes(tag));

            article.style.display = matches ? 'block' : 'none';
        });

        // Check if any posts are visible
        const visiblePosts = Array.from(document.querySelectorAll('.post-preview'))
            .filter(article => article.style.display !== 'none');

        // Show "no results" message if no posts match
        const container = document.querySelector('.post-listing');
        if (container) {
            let noResultsMsg = container.querySelector('.no-results');

            if (visiblePosts.length === 0) {
                if (!noResultsMsg) {
                    noResultsMsg = document.createElement('p');
                    noResultsMsg.className = 'no-results';
                    noResultsMsg.textContent = 'No posts found with the selected tags.';
                    container.appendChild(noResultsMsg);
                }
            } else {
                if (noResultsMsg) {
                    noResultsMsg.remove();
                }
            }
        }
    }

    renderFilterUI() {
        const main = document.querySelector('main');
        if (!main) return;

        // Remove existing filter UI if present
        const existingFilterUI = document.querySelector('.filter-ui');
        if (existingFilterUI) {
            existingFilterUI.remove();
        }

        // Create filter UI container
        const filterUI = document.createElement('div');
        filterUI.className = 'filter-ui';
        filterUI.innerHTML = `
            <div class="filter-status">
                <span class="filter-label">Filtered by:</span>
                ${this.activeTags.map(tag => `
                    <button class="filter-tag" data-tag="${tag}">
                        ${tag} <span class="remove-tag">×</span>
                    </button>
                `).join('')}
            </div>
        `;

        // Insert after the intro paragraph
        const introParagraph = main.querySelector('p');
        if (introParagraph) {
            introParagraph.after(filterUI);
        } else {
            main.prepend(filterUI);
        }

        // Setup remove tag handlers
        filterUI.querySelectorAll('.filter-tag').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const tagToRemove = btn.dataset.tag;
                this.removeTag(tagToRemove);
            });
        });
    }

    setupTagClickHandlers() {
        // Intercept tag link clicks to add to current filter (instead of replacing)
        // Only on archive page
        document.addEventListener('click', (e) => {
            const tagLink = e.target.closest('.tag-link');
            if (!tagLink) return;

            e.preventDefault();
            const tag = tagLink.dataset.tag;
            this.addTag(tag);
        });
    }

    addTag(tag) {
        if (this.activeTags.includes(tag)) return; // Already active

        this.activeTags.push(tag);
        this.updateURL();
        this.refresh();
    }

    removeTag(tag) {
        this.activeTags = this.activeTags.filter(t => t !== tag);
        this.updateURL();
        this.refresh();
    }

    updateURL() {
        const url = new URL(window.location);

        if (this.activeTags.length > 0) {
            url.searchParams.set('tag', this.activeTags.join(','));
        } else {
            url.searchParams.delete('tag');
        }

        window.history.pushState({}, '', url);
    }

    refresh() {
        // Re-filter posts
        this.filterPosts();

        // Update filter UI
        if (this.activeTags.length > 0) {
            this.renderFilterUI();
        } else {
            const existingFilterUI = document.querySelector('.filter-ui');
            if (existingFilterUI) {
                existingFilterUI.remove();
            }
        }
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new TagFilter());
} else {
    new TagFilter();
}
