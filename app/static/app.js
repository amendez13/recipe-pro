// Idea Canvas - Frontend Application

const API = {
    async getIdeas(category = '', limit = 100, offset = 0) {
        const params = new URLSearchParams({ limit, offset });
        if (category) params.set('category', category);
        const res = await fetch(`/api/ideas?${params}`);
        return res.json();
    },

    async createIdea(data) {
        const res = await fetch('/api/ideas', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return res.json();
    },

    async updateIdea(id, data) {
        const res = await fetch(`/api/ideas/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return res.json();
    },

    async deleteIdea(id) {
        const res = await fetch(`/api/ideas/${id}`, { method: 'DELETE' });
        return res.json();
    },

    async getCategories() {
        const res = await fetch('/api/categories');
        return res.json();
    },

    async search(query, limit = 50) {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&limit=${limit}`);
        return res.json();
    },

    async getStats() {
        const res = await fetch('/api/stats');
        return res.json();
    },
};

// State
let currentIdeas = [];
let currentCategory = '';
let searchTimeout = null;

// DOM Elements
const ideasGrid = document.getElementById('ideas-grid');
const newIdeaBtn = document.getElementById('new-idea-btn');
const modalOverlay = document.getElementById('modal-overlay');
const modalTitle = document.getElementById('modal-title');
const modalClose = document.getElementById('modal-close');
const cancelBtn = document.getElementById('cancel-btn');
const ideaForm = document.getElementById('idea-form');
const searchInput = document.getElementById('search-input');
const categoryFilter = document.getElementById('category-filter');
const categoryList = document.getElementById('category-list');
const totalCount = document.getElementById('total-count');
const themeToggle = document.getElementById('theme-toggle');

// Theme
function initTheme() {
    const saved = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = saved || (prefersDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
    updateThemeIcon();
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    updateThemeIcon();
}

function updateThemeIcon() {
    const theme = document.documentElement.getAttribute('data-theme');
    const icon = document.querySelector('.theme-icon');
    icon.textContent = theme === 'dark' ? '☀' : '☾';
}

// Modal
function openModal(title = 'New Idea', idea = null) {
    modalTitle.textContent = title;
    document.getElementById('idea-id').value = idea?.id || '';
    document.getElementById('idea-title').value = idea?.title || '';
    document.getElementById('idea-content').value = idea?.content || '';
    document.getElementById('idea-category').value = idea?.category || 'general';
    document.getElementById('idea-tags').value = idea?.tags?.join(', ') || '';
    modalOverlay.classList.add('active');
    document.getElementById('idea-title').focus();
}

function closeModal() {
    modalOverlay.classList.remove('active');
    ideaForm.reset();
}

// Render
function formatDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
    });
}

function renderIdea(idea) {
    const card = document.createElement('div');
    card.className = 'idea-card';

    const tagsHtml = idea.tags?.length
        ? `<div class="tags">${idea.tags.map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}</div>`
        : '';

    card.innerHTML = `
        <h3>${escapeHtml(idea.title)}</h3>
        <p class="content-preview">${escapeHtml(idea.content || '')}</p>
        <div class="meta">
            <span class="category">${escapeHtml(idea.category)}</span>
            <span class="date">${formatDate(idea.created_at)}</span>
        </div>
        ${tagsHtml}
        <div class="card-actions">
            <button class="secondary-btn edit-btn" data-id="${idea.id}">Edit</button>
            <button class="danger-btn delete-btn" data-id="${idea.id}">Delete</button>
        </div>
    `;

    card.querySelector('.edit-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        openModal('Edit Idea', idea);
    });

    card.querySelector('.delete-btn').addEventListener('click', async (e) => {
        e.stopPropagation();
        if (confirm('Delete this idea?')) {
            await API.deleteIdea(idea.id);
            loadIdeas();
        }
    });

    return card;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderIdeas(ideas) {
    ideasGrid.innerHTML = '';

    if (ideas.length === 0) {
        ideasGrid.innerHTML = `
            <div class="empty-state">
                <h2>No ideas yet</h2>
                <p>Click "+ New Idea" to capture your first idea!</p>
            </div>
        `;
        return;
    }

    ideas.forEach(idea => {
        ideasGrid.appendChild(renderIdea(idea));
    });
}

async function loadIdeas() {
    try {
        const data = await API.getIdeas(currentCategory);
        currentIdeas = data.ideas;
        renderIdeas(currentIdeas);
        totalCount.textContent = `${data.total} idea${data.total !== 1 ? 's' : ''}`;
    } catch (err) {
        console.error('Failed to load ideas:', err);
    }
}

async function loadCategories() {
    try {
        const categories = await API.getCategories();
        categoryFilter.innerHTML = '<option value="">All Categories</option>';
        categoryList.innerHTML = '';

        categories.forEach(cat => {
            const option = document.createElement('option');
            option.value = cat;
            option.textContent = cat;
            categoryFilter.appendChild(option);

            const listOption = document.createElement('option');
            listOption.value = cat;
            categoryList.appendChild(listOption);
        });
    } catch (err) {
        console.error('Failed to load categories:', err);
    }
}

async function handleSearch(query) {
    if (!query.trim()) {
        loadIdeas();
        return;
    }

    try {
        const data = await API.search(query);
        currentIdeas = data.ideas;
        renderIdeas(currentIdeas);
        totalCount.textContent = `${data.count} result${data.count !== 1 ? 's' : ''} for "${query}"`;
    } catch (err) {
        console.error('Search failed:', err);
    }
}

// Event Listeners
newIdeaBtn.addEventListener('click', () => openModal());
modalClose.addEventListener('click', closeModal);
cancelBtn.addEventListener('click', closeModal);
themeToggle.addEventListener('click', toggleTheme);

modalOverlay.addEventListener('click', (e) => {
    if (e.target === modalOverlay) closeModal();
});

ideaForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const id = document.getElementById('idea-id').value;
    const tagsValue = document.getElementById('idea-tags').value;
    const tags = tagsValue ? tagsValue.split(',').map(t => t.trim()).filter(Boolean) : [];

    const data = {
        title: document.getElementById('idea-title').value,
        content: document.getElementById('idea-content').value,
        category: document.getElementById('idea-category').value || 'general',
        tags,
    };

    try {
        if (id) {
            await API.updateIdea(id, data);
        } else {
            await API.createIdea(data);
        }
        closeModal();
        loadIdeas();
        loadCategories();
    } catch (err) {
        console.error('Save failed:', err);
        alert('Failed to save idea');
    }
});

categoryFilter.addEventListener('change', (e) => {
    currentCategory = e.target.value;
    searchInput.value = '';
    loadIdeas();
});

searchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        handleSearch(e.target.value);
    }, 300);
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modalOverlay.classList.contains('active')) {
        closeModal();
    }
    if (e.key === 'n' && e.ctrlKey) {
        e.preventDefault();
        openModal();
    }
});

// Init
initTheme();
loadIdeas();
loadCategories();
