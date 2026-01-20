/**
 * Tag Filtering Module
 *
 * Provides client-side tag filtering for blog archive pages
 * - Fetches posts-metadata.json
 * - Filters by URL query parameters (?tag=ai,product)
 * - Renders filtered post listing
 * - Handles clickable tags
 */

class TagFilter {
    constructor() {
        this.allPosts = [];
        this.activeTags = [];
        this.init();
    }

    async init() {
        // Parse URL parameters
        this.parseURLParams();

        // Fetch metadata
        await this.fetchMetadata();

        // Render posts (filtered if tags are active)
        this.renderPosts();

        // Render filter UI if filters are active
        if (this.activeTags.length > 0) {
            this.renderFilterUI();
        }

        // Setup tag click handlers
        this.setupTagClickHandlers();
    }

    parseURLParams() {
        const params = new URLSearchParams(window.location.search);
        const tagParam = params.get('tag');

        if (tagParam) {
            this.activeTags = tagParam.split(',').map(t => t.trim()).filter(t => t);
        }
    }

    async fetchMetadata() {
        try {
            const response = await fetch('/posts-metadata.json');
            const data = await response.json();
            this.allPosts = data.posts || [];
        } catch (error) {
            console.error('Failed to load posts metadata:', error);
            // Graceful fallback: page will show static HTML posts
        }
    }

    filterPosts() {
        if (this.activeTags.length === 0) {
            return this.allPosts;
        }

        // AND logic: post must have ALL active tags
        return this.allPosts.filter(post => {
            return this.activeTags.every(tag =>
                post.tags && post.tags.includes(tag)
            );
        });
    }

    renderPosts() {
        const filteredPosts = this.filterPosts();
        const container = document.querySelector('.post-listing');

        if (!container) return;

        // Clear existing posts
        container.innerHTML = '';

        if (filteredPosts.length === 0) {
            container.innerHTML = '<p class="no-results">No posts found with the selected tags.</p>';
            return;
        }

        // Render filtered posts
        filteredPosts.forEach(post => {
            if (post.type !== 'words') return; // Only show words on words archive

            const article = document.createElement('article');
            article.className = 'post-preview';

            // Format date from YYYY-MM-DD to DD/MM/YYYY
            let formattedDate = '';
            if (post.date) {
                const [year, month, day] = post.date.split('-');
                formattedDate = `${day}/${month}/${year}`;
            }

            // Build tags HTML
            let tagsHTML = '';
            if (post.tags && post.tags.length > 0) {
                const tagList = post.tags.map(tag =>
                    `<a href="?tag=${encodeURIComponent(tag)}" class="tag-link" data-tag="${tag}">${tag}</a>`
                ).join(', ');
                tagsHTML = `Filed under: ${tagList}`;
            }

            // Split excerpt into paragraphs and render each as separate <p> tag
            let excerptHTML = '';
            if (post.excerpt) {
                const paragraphs = post.excerpt.split('\n\n');
                excerptHTML = paragraphs.map(p => `<p class="post-excerpt">${p}</p>`).join('\n                ');
            }

            article.innerHTML = `
                <h3><a href="${post.url}">${post.title}</a></h3>
                <p class="post-meta">
                    ${formattedDate ? `Published on: ${formattedDate}. ` : ''}
                    ${tagsHTML}
                </p>
                ${excerptHTML}
            `;

            container.appendChild(article);
        });
    }

    renderFilterUI() {
        const main = document.querySelector('main');
        if (!main) return;

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
        // Remove existing filter UI
        const existingFilterUI = document.querySelector('.filter-ui');
        if (existingFilterUI) {
            existingFilterUI.remove();
        }

        // Re-render
        this.renderPosts();

        if (this.activeTags.length > 0) {
            this.renderFilterUI();
        }
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new TagFilter());
} else {
    new TagFilter();
}
