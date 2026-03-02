const root = document.getElementById('app-root');
const state = {
    route: 'list',
    recipes: [],
    shoppingChecks: new Set(),
    shoppingRecipeIds: new Set(),
    ingredients: [],
    editRecipeId: null,
    detailRecipeId: null,
    focusMode: false,
    focusStepIndex: 0,
    authUser: null,
    authReady: false,
    collapsedRecipeCategories: {},
};

const SHOPPING_SELECTION_STORAGE_KEY_PREFIX = 'shopping_recipe_ids::';
const SHOPPING_CHECKS_STORAGE_KEY_PREFIX = 'shopping_checks::';
const INGREDIENT_LANGUAGE_STORAGE_KEY_PREFIX = 'ingredient_language::';

function getIngredientLanguageStorageKey() {
    const username = state.authUser?.username;
    if (!username) {
        return null;
    }
    return `${INGREDIENT_LANGUAGE_STORAGE_KEY_PREFIX}${username}`;
}

function loadIngredientLanguagePreference() {
    const key = getIngredientLanguageStorageKey();
    if (!key) {
        return 'en';
    }
    try {
        const saved = String(window.localStorage.getItem(key) || '').toLowerCase();
        return saved === 'es' ? 'es' : 'en';
    } catch (_) {
        return 'en';
    }
}

function saveIngredientLanguagePreference(language) {
    const key = getIngredientLanguageStorageKey();
    if (!key) {
        return;
    }
    try {
        window.localStorage.setItem(key, language === 'es' ? 'es' : 'en');
    } catch (_) {
        // Ignore storage failures.
    }
}

function getIngredientDisplayName(ingredient, language = 'en') {
    const fallback = String(ingredient?.name || '').trim();
    const english = String(ingredient?.name_en || fallback).trim();
    const spanish = String(ingredient?.name_es || english || fallback).trim();
    return language === 'es' ? (spanish || english || fallback) : (english || spanish || fallback);
}

function formatQuantityUnit(quantity, unit) {
    const numericQuantity = Number(quantity);
    if (Number.isNaN(numericQuantity) || numericQuantity <= 0) {
        return '';
    }
    const normalizedUnit = String(unit || '').trim().toLowerCase();
    if (!normalizedUnit || normalizedUnit === 'nonunit') {
        return `${numericQuantity}`;
    }
    return `${numericQuantity} ${unit}`;
}

function getShoppingSelectionStorageKey() {
    const username = state.authUser?.username;
    if (!username) {
        return null;
    }
    return `${SHOPPING_SELECTION_STORAGE_KEY_PREFIX}${username}`;
}

function loadShoppingSelectionFromStorage() {
    const key = getShoppingSelectionStorageKey();
    if (!key) {
        return new Set();
    }
    try {
        const raw = window.localStorage.getItem(key);
        if (!raw) {
            return new Set();
        }
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) {
            return new Set();
        }
        const ids = parsed
            .map((value) => Number(value))
            .filter((value) => Number.isInteger(value) && value > 0)
            .slice(0, 10);
        return new Set(ids);
    } catch (_) {
        return new Set();
    }
}

function saveShoppingSelectionToStorage() {
    const key = getShoppingSelectionStorageKey();
    if (!key) {
        return;
    }
    try {
        window.localStorage.setItem(key, JSON.stringify(Array.from(state.shoppingRecipeIds)));
    } catch (_) {
        // Ignore storage failures (private mode, quota, etc).
    }
}

function clearShoppingSelectionFromStorage() {
    const key = getShoppingSelectionStorageKey();
    if (!key) {
        return;
    }
    try {
        window.localStorage.removeItem(key);
    } catch (_) {
        // Ignore storage failures.
    }
}

function getShoppingChecksStorageKey() {
    const username = state.authUser?.username;
    if (!username) {
        return null;
    }
    return `${SHOPPING_CHECKS_STORAGE_KEY_PREFIX}${username}`;
}

function loadShoppingChecksFromStorage() {
    const key = getShoppingChecksStorageKey();
    if (!key) {
        return new Set();
    }
    try {
        const raw = window.localStorage.getItem(key);
        if (!raw) {
            return new Set();
        }
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) {
            return new Set();
        }
        const ids = parsed
            .map((value) => String(value || '').trim())
            .filter(Boolean);
        return new Set(ids);
    } catch (_) {
        return new Set();
    }
}

function saveShoppingChecksToStorage() {
    const key = getShoppingChecksStorageKey();
    if (!key) {
        return;
    }
    try {
        window.localStorage.setItem(key, JSON.stringify(Array.from(state.shoppingChecks)));
    } catch (_) {
        // Ignore storage failures (private mode, quota, etc).
    }
}

function clearShoppingChecksFromStorage() {
    const key = getShoppingChecksStorageKey();
    if (!key) {
        return;
    }
    try {
        window.localStorage.removeItem(key);
    } catch (_) {
        // Ignore storage failures.
    }
}

const api = {
    async request(url, options = {}, meta = {}) {
        const response = await fetch(url, options);
        if (!response.ok) {
            let detail = 'Request failed';
            try {
                const body = await response.json();
                detail = body.detail || JSON.stringify(body);
            } catch (_) {
                detail = response.statusText;
            }
            if (response.status === 401 && !meta.suppressAuthRedirect) {
                state.authUser = null;
                state.route = 'login';
                state.authReady = true;
                renderHeaderAuth();
                render();
            }
            throw new Error(detail);
        }
        return response.json();
    },
    getRecipes(search = '') {
        const qs = search ? `?search=${encodeURIComponent(search)}` : '';
        return this.request(`/api/recipes${qs}`);
    },
    getRecipe(id) {
        return this.request(`/api/recipes/${id}`);
    },
    createRecipe(payload) {
        return this.request('/api/recipes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
    },
    updateRecipe(id, payload) {
        return this.request(`/api/recipes/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
    },
    deleteRecipe(id) {
        return this.request(`/api/recipes/${id}`, { method: 'DELETE' });
    },
    getIngredients() {
        return this.request('/api/ingredients');
    },
    getRecipesByIngredient(id) {
        return this.request(`/api/ingredients/${id}/recipes`);
    },
    updateIngredientPreference(id, payload) {
        return fetch(`/api/ingredients/${id}/default`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        }).then(async (response) => {
            if (response.ok) {
                return response.json();
            }
            // Backward compatibility for deployments still on PATCH endpoint.
            if (response.status === 404 || response.status === 405) {
                // First fallback: POST on base ingredient endpoint.
                const postFallback = await fetch(`/api/ingredients/${id}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                if (postFallback.ok) {
                    return postFallback.json();
                }
                // Second fallback: PATCH on base ingredient endpoint.
                if (postFallback.status === 404 || postFallback.status === 405) {
                    return this.request(`/api/ingredients/${id}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload),
                    });
                }
                let fallbackDetail = 'Request failed';
                try {
                    const fallbackBody = await postFallback.json();
                    fallbackDetail = fallbackBody.detail || JSON.stringify(fallbackBody);
                } catch (_) {
                    fallbackDetail = postFallback.statusText;
                }
                throw new Error(fallbackDetail);
            }
            let detail = 'Request failed';
            try {
                const body = await response.json();
                detail = body.detail || JSON.stringify(body);
            } catch (_) {
                detail = response.statusText;
            }
            throw new Error(detail);
        });
    },
    deleteIngredient(id) {
        return this.request(`/api/ingredients/${id}`, { method: 'DELETE' });
    },
    updateIngredientNames(id, payload) {
        return this.request(`/api/ingredients/${id}/names`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
    },
    getIngredientMergePreview(payload) {
        return this.request('/api/ingredients/merge-preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
    },
    mergeIngredients(payload) {
        return this.request('/api/ingredients/merge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
    },
    undoIngredientMerge(mergeEventId) {
        return this.request(`/api/ingredients/merge/${mergeEventId}/undo`, {
            method: 'POST',
        });
    },
    getIngredientMergeHistory() {
        return this.request('/api/ingredients/merge-history');
    },
    getShoppingList(recipe_ids) {
        return this.request('/api/shopping-list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ recipe_ids }),
        });
    },
    getSuggestions(ingredient_ids) {
        return this.request('/api/suggestions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ingredient_ids }),
        });
    },
    getRecipeImportPreview(payload) {
        return this.request('/api/recipes/import-preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
    },
    login(payload) {
        return this.request('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        }, { suppressAuthRedirect: true });
    },
    logout() {
        return this.request('/api/auth/logout', { method: 'POST' });
    },
    me() {
        return this.request('/api/auth/me', {}, { suppressAuthRedirect: true });
    },
};

function nav(route, payload = null) {
    if (route !== 'login' && !state.authUser) {
        state.route = 'login';
        render();
        return;
    }
    state.route = route;
    if (route === 'detail' && payload) {
        state.detailRecipeId = payload.id;
    }
    if (route === 'edit' && payload) {
        state.editRecipeId = payload.id;
    }
    if (route !== 'edit') {
        state.editRecipeId = null;
    }
    if (route !== 'detail') {
        state.detailRecipeId = null;
    }
    render();
}

document.querySelectorAll('[data-route]').forEach((button) => {
    button.addEventListener('click', () => nav(button.dataset.route));
});

const authUsernameEl = document.getElementById('auth-username');
const logoutBtnEl = document.getElementById('logout-btn');
const navActionsEl = document.querySelector('.nav-actions');

function renderHeaderAuth() {
    if (state.authUser) {
        authUsernameEl.textContent = state.authUser.username;
        authUsernameEl.classList.remove('hidden');
        logoutBtnEl.classList.remove('hidden');
        navActionsEl.classList.remove('hidden');
    } else {
        authUsernameEl.textContent = '';
        authUsernameEl.classList.add('hidden');
        logoutBtnEl.classList.add('hidden');
        navActionsEl.classList.add('hidden');
    }
}

logoutBtnEl.addEventListener('click', async () => {
    try {
        await api.logout();
    } catch (_) {
        // Even if logout call fails, drop local auth state.
    }
    state.authUser = null;
    state.route = 'login';
    renderHeaderAuth();
    render();
});

function setMessage(el, text, isError = false) {
    el.textContent = text;
    el.className = `message ${isError ? 'error' : ''}`;
}

function getRecipeCategoryLabel(recipe) {
    const value = String(recipe?.category || '').trim();
    return value || 'Uncategorized';
}

function getRecipeCategoryKey(label) {
    return label.trim().toLowerCase();
}

function groupRecipesByCategory(recipes) {
    const grouped = new Map();
    recipes.forEach((recipe) => {
        const label = getRecipeCategoryLabel(recipe);
        const key = getRecipeCategoryKey(label);
        if (!grouped.has(key)) {
            grouped.set(key, { key, label, recipes: [] });
        }
        grouped.get(key).recipes.push(recipe);
    });
    return Array.from(grouped.values()).sort((left, right) => left.label.localeCompare(right.label));
}

function recipeCard(recipe) {
    const article = document.createElement('article');
    article.className = 'card recipe-card';
    article.innerHTML = `
        <label class="row gap align-center compact-row">
            <button type="button" class="title-link" data-open-recipe="${recipe.id}">${escapeHtml(recipe.title)}</button>
        </label>
        <p class="muted compact-meta">Servings: ${recipe.servings ?? '-'} | Prep: ${recipe.prep_time ?? '-'} | Cook: ${recipe.cook_time ?? '-'}</p>
        <div class="row gap recipe-actions">
            <button class="edit-compact" data-edit-recipe="${recipe.id}">Edit</button>
        </div>
    `;
    return article;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text ?? '');
    return div.innerHTML;
}

async function renderLoginView() {
    root.innerHTML = '';
    const node = document.getElementById('login-view-template').content.cloneNode(true);
    root.appendChild(node);

    const form = document.getElementById('login-form');
    const messageEl = document.getElementById('login-message');
    const usernameEl = document.getElementById('login-username');
    const passwordEl = document.getElementById('login-password');
    const rememberEl = document.getElementById('login-remember');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        setMessage(messageEl, 'Signing in...');
        try {
            const session = await api.login({
                username: usernameEl.value.trim(),
                password: passwordEl.value,
                remember: rememberEl.checked,
            });
            state.authUser = { username: session.username };
            renderHeaderAuth();
            nav('list');
        } catch (err) {
            setMessage(messageEl, err.message || 'Login failed', true);
        }
    });
}

async function renderListView() {
    root.innerHTML = '';
    const node = document.getElementById('list-view-template').content.cloneNode(true);
    root.appendChild(node);

    const listEl = document.getElementById('recipe-list');
    const searchEl = document.getElementById('recipe-search');
    const messageEl = document.getElementById('recipe-list-message');

    async function load(search = '') {
        try {
            const recipes = await api.getRecipes(search);
            state.recipes = recipes;
            listEl.innerHTML = '';
            if (!recipes.length) {
                setMessage(messageEl, 'No recipes found.');
                return;
            }
            setMessage(messageEl, `Loaded ${recipes.length} recipe(s).`);
            const groups = groupRecipesByCategory(recipes);
            groups.forEach((group) => {
                const wrapper = document.createElement('section');
                wrapper.className = 'category-group card';
                const isOpen = !state.collapsedRecipeCategories[group.key];
                wrapper.innerHTML = `
                    <details class="category-details" data-category-key="${escapeHtml(group.key)}" ${isOpen ? 'open' : ''}>
                        <summary class="category-summary">
                            <span class="category-summary-title">${escapeHtml(group.label)}</span>
                            <span class="category-summary-count">${group.recipes.length} recipe(s)</span>
                        </summary>
                        <div class="grid category-recipes"></div>
                    </details>
                `;
                const recipesEl = wrapper.querySelector('.category-recipes');
                group.recipes.forEach((recipe) => recipesEl.appendChild(recipeCard(recipe)));
                listEl.appendChild(wrapper);
            });

            listEl.querySelectorAll('[data-open-recipe]').forEach((button) => {
                button.addEventListener('click', () => nav('detail', { id: Number(button.dataset.openRecipe) }));
            });
            listEl.querySelectorAll('[data-edit-recipe]').forEach((button) => {
                button.addEventListener('click', () => nav('edit', { id: Number(button.dataset.editRecipe) }));
            });
            listEl.querySelectorAll('.category-details').forEach((detailsEl) => {
                detailsEl.addEventListener('toggle', () => {
                    const key = detailsEl.dataset.categoryKey || '';
                    if (!key) {
                        return;
                    }
                    state.collapsedRecipeCategories[key] = !detailsEl.open;
                });
            });
        } catch (err) {
            setMessage(messageEl, `Failed to load recipes: ${err.message}`, true);
        }
    }

    searchEl.addEventListener('input', () => load(searchEl.value.trim()));
    document.getElementById('refresh-recipes').addEventListener('click', () => load(searchEl.value.trim()));

    await load();
}

function splitInstructions(instructions) {
    return String(instructions || '')
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean);
}

function getRecipeSteps(recipe) {
    if (Array.isArray(recipe.steps) && recipe.steps.length > 0) {
        return recipe.steps.map((step) => String(step).trim()).filter(Boolean);
    }
    return splitInstructions(recipe.instructions);
}

async function renderDetailView(recipeId) {
    root.innerHTML = '';
    const node = document.getElementById('detail-view-template').content.cloneNode(true);
    root.appendChild(node);

    const metaEl = document.getElementById('detail-meta');
    const titleEl = document.getElementById('detail-title');
    const ingredientsEl = document.getElementById('detail-ingredients');
    const stepsEl = document.getElementById('detail-steps');
    const sourceUrlEl = document.getElementById('detail-source-url');
    const focusPanelEl = document.getElementById('focus-mode-panel');
    const focusCounterEl = document.getElementById('focus-step-counter');
    const focusTextEl = document.getElementById('focus-step-text');
    const langEnBtn = document.getElementById('ingredient-lang-en');
    const langEsBtn = document.getElementById('ingredient-lang-es');

    try {
        const recipe = await api.getRecipe(recipeId);
        const steps = getRecipeSteps(recipe);
        let ingredientLanguage = loadIngredientLanguagePreference();
        state.focusStepIndex = 0;
        titleEl.textContent = recipe.title;
        const categoryLabel = getRecipeCategoryLabel(recipe);
        metaEl.textContent = `Category: ${categoryLabel} | Servings: ${recipe.servings ?? '-'} | Prep: ${recipe.prep_time ?? '-'} min | Cook: ${recipe.cook_time ?? '-'} min`;

        function renderIngredientLanguageToggle() {
            langEnBtn.classList.toggle('active', ingredientLanguage === 'en');
            langEsBtn.classList.toggle('active', ingredientLanguage === 'es');
        }

        function renderIngredientsList() {
            ingredientsEl.innerHTML = '';
            recipe.ingredients.forEach((item) => {
                const li = document.createElement('li');
                const ingredientData = item.ingredient || {};
                const name = getIngredientDisplayName(ingredientData, ingredientLanguage) || `Ingredient #${item.ingredient_id}`;
                const qtyUnit = formatQuantityUnit(item.quantity, item.unit);
                const prefix = qtyUnit ? `${qtyUnit} ` : '';
                li.textContent = `${prefix}${name}${item.notes ? ` (${item.notes})` : ''}`;
                ingredientsEl.appendChild(li);
            });
        }
        renderIngredientLanguageToggle();
        renderIngredientsList();

        langEnBtn.addEventListener('click', () => {
            ingredientLanguage = 'en';
            saveIngredientLanguagePreference(ingredientLanguage);
            renderIngredientLanguageToggle();
            renderIngredientsList();
        });
        langEsBtn.addEventListener('click', () => {
            ingredientLanguage = 'es';
            saveIngredientLanguagePreference(ingredientLanguage);
            renderIngredientLanguageToggle();
            renderIngredientsList();
        });

        stepsEl.innerHTML = '';
        steps.forEach((step, index) => {
            const li = document.createElement('li');
            li.innerHTML = `<strong>Step ${index + 1}</strong><p>${escapeHtml(step)}</p>`;
            stepsEl.appendChild(li);
        });

        if (recipe.url) {
            sourceUrlEl.innerHTML = `Source: <a href="${escapeHtml(recipe.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(recipe.url)}</a>`;
            sourceUrlEl.classList.remove('hidden');
        } else {
            sourceUrlEl.textContent = '';
            sourceUrlEl.classList.add('hidden');
        }

        function renderFocusStep() {
            if (!steps.length) {
                focusCounterEl.textContent = 'No steps available';
                focusTextEl.textContent = '';
                document.getElementById('focus-prev').disabled = true;
                document.getElementById('focus-next').disabled = true;
                return;
            }
            if (state.focusStepIndex < 0) {
                state.focusStepIndex = 0;
            }
            if (state.focusStepIndex >= steps.length) {
                state.focusStepIndex = steps.length - 1;
            }
            const index = state.focusStepIndex;
            focusCounterEl.textContent = `Step ${index + 1} of ${steps.length}`;
            focusTextEl.textContent = steps[index];
            document.getElementById('focus-prev').disabled = index === 0;
            document.getElementById('focus-next').disabled = index === steps.length - 1;
        }

        function renderFocusVisibility() {
            if (state.focusMode) {
                focusPanelEl.classList.remove('hidden');
            } else {
                focusPanelEl.classList.add('hidden');
            }
        }

        renderFocusStep();
        renderFocusVisibility();

        document.getElementById('toggle-focus-mode').addEventListener('click', () => {
            state.focusMode = !state.focusMode;
            renderFocusVisibility();
        });
        function goPrevStep() {
            state.focusStepIndex -= 1;
            renderFocusStep();
        }

        function goNextStep() {
            state.focusStepIndex += 1;
            renderFocusStep();
        }

        document.getElementById('focus-prev').addEventListener('click', goPrevStep);
        document.getElementById('focus-next').addEventListener('click', goNextStep);

        let touchStartX = 0;
        let touchStartY = 0;
        focusPanelEl.addEventListener('touchstart', (event) => {
            const touch = event.changedTouches[0];
            touchStartX = touch.clientX;
            touchStartY = touch.clientY;
        }, { passive: true });
        focusPanelEl.addEventListener('touchend', (event) => {
            const touch = event.changedTouches[0];
            const dx = touch.clientX - touchStartX;
            const dy = touch.clientY - touchStartY;
            const isHorizontalSwipe = Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy);
            if (!isHorizontalSwipe) {
                return;
            }
            if (dx < 0) {
                goNextStep();
            } else {
                goPrevStep();
            }
        }, { passive: true });

        document.getElementById('edit-recipe').addEventListener('click', () => nav('edit', { id: recipe.id }));
        document.getElementById('delete-recipe').addEventListener('click', async () => {
            if (!confirm(`Delete ${recipe.title}?`)) {
                return;
            }
            await api.deleteRecipe(recipe.id);
            nav('list');
        });
        document.getElementById('back-to-list').addEventListener('click', () => nav('list'));
    } catch (err) {
        setMessage(metaEl, `Unable to load recipe: ${err.message}`, true);
    }
}

function ingredientRow(initial = {}) {
    const initialUnit = (initial.unit || '').trim();
    const displayUnit = initialUnit === 'nonunit' ? '' : initialUnit;
    const row = document.createElement('div');
    row.className = 'row gap responsive ingredient-row';
    row.innerHTML = `
        <input class="i-name" placeholder="name" value="${escapeHtml(initial.name || '')}" required>
        <input class="i-qty" type="number" min="0" step="0.01" placeholder="qty (optional)" value="${initial.quantity ?? ''}">
        <input class="i-unit" placeholder="unit (optional)" value="${escapeHtml(displayUnit)}">
        <input class="i-category" placeholder="category" value="${escapeHtml(initial.category || '')}">
        <input class="i-notes" placeholder="notes" value="${escapeHtml(initial.notes || '')}">
        <button type="button" class="danger remove-row">Remove</button>
    `;
    row.querySelector('.remove-row').addEventListener('click', () => row.remove());
    return row;
}

function stepRow(initialStep = '') {
    const row = document.createElement('div');
    row.className = 'row gap align-center step-row';
    row.innerHTML = `
        <textarea class="s-text" rows="2" placeholder="Describe this step..." required>${escapeHtml(initialStep)}</textarea>
        <button type="button" class="danger remove-step">Remove</button>
    `;
    row.querySelector('.remove-step').addEventListener('click', () => row.remove());
    return row;
}

function collectFormPayload() {
    const ingredients = [];
    document.querySelectorAll('.ingredient-row').forEach((row) => {
        const name = row.querySelector('.i-name').value.trim();
        const quantityRaw = row.querySelector('.i-qty').value.trim();
        const quantity = quantityRaw === '' ? 0 : Number(quantityRaw);
        const unit = row.querySelector('.i-unit').value.trim() || 'nonunit';
        if (!name || Number.isNaN(quantity)) {
            return;
        }
        ingredients.push({
            name,
            name_en: name,
            name_es: name,
            quantity,
            unit,
            category: row.querySelector('.i-category').value.trim() || null,
            notes: row.querySelector('.i-notes').value.trim() || null,
        });
    });

    const steps = [];
    document.querySelectorAll('.step-row').forEach((row) => {
        const instruction = row.querySelector('.s-text').value.trim();
        if (instruction) {
            steps.push(instruction);
        }
    });

    return {
        title: document.getElementById('f-title').value.trim(),
        category: document.getElementById('f-category').value.trim() || null,
        url: document.getElementById('f-url').value.trim() || null,
        instructions: steps.join('\n'),
        steps,
        servings: Number(document.getElementById('f-servings').value) || null,
        prep_time: Number(document.getElementById('f-prep').value) || null,
        cook_time: Number(document.getElementById('f-cook').value) || null,
        ingredients,
    };
}

async function renderFormView(recipeId = null) {
    root.innerHTML = '';
    const node = document.getElementById('form-view-template').content.cloneNode(true);
    root.appendChild(node);

    const form = document.getElementById('recipe-form');
    const rowsEl = document.getElementById('ingredient-rows');
    const stepRowsEl = document.getElementById('step-rows');
    const messageEl = document.getElementById('form-message');
    const titleEl = document.getElementById('form-title');
    const importSectionEl = document.getElementById('import-assistant');
    const importUrlEl = document.getElementById('import-url');
    const importTextFileEl = document.getElementById('import-text-file');
    const importTextEl = document.getElementById('import-text');
    const importMessageEl = document.getElementById('import-message');
    const importPreviewEl = document.getElementById('import-preview');
    const importConfirmBtn = document.getElementById('import-confirm-btn');
    let importPayload = null;

    document.getElementById('add-ingredient-row').addEventListener('click', () => {
        rowsEl.appendChild(ingredientRow());
    });
    document.getElementById('add-step-row').addEventListener('click', () => {
        stepRowsEl.appendChild(stepRow());
    });
    document.getElementById('cancel-form').addEventListener('click', () => nav('list'));
    async function previewImport(previewPayload, sourceLabel) {
        setMessage(importMessageEl, 'Importing recipe preview...');
        try {
            importPayload = await api.getRecipeImportPreview(previewPayload);
            importPreviewEl.classList.remove('hidden');
            importConfirmBtn.classList.remove('hidden');
            const warnings = Array.isArray(importPayload.warnings) ? importPayload.warnings : [];
            const warningsHtml = warnings.length
                ? `<div class="message error"><strong>Import warnings:</strong><br>${warnings.map((item) => escapeHtml(item)).join('<br>')}</div>`
                : '';
            importPreviewEl.innerHTML = `
                <h4>${escapeHtml(importPayload.title)}</h4>
                <p class="muted">Servings: ${importPayload.servings ?? '-'} | Prep: ${importPayload.prep_time ?? '-'} | Cook: ${importPayload.cook_time ?? '-'}</p>
                <p><strong>Steps:</strong> ${importPayload.steps.length}</p>
                <p><strong>Ingredients:</strong> ${importPayload.ingredients.length}</p>
                <p class="muted">Source: ${escapeHtml(importPayload.source_url || sourceLabel)}</p>
                ${warningsHtml}
            `;
            setMessage(importMessageEl, 'Preview ready. Confirm to add this recipe.');
        } catch (err) {
            importPayload = null;
            importPreviewEl.classList.add('hidden');
            importConfirmBtn.classList.add('hidden');
            setMessage(importMessageEl, `Import failed: ${err.message}`, true);
        }
    }

    document.getElementById('import-preview-url-btn').addEventListener('click', async () => {
        const url = importUrlEl.value.trim();
        if (!url) {
            setMessage(importMessageEl, 'Provide a URL first.', true);
            return;
        }
        await previewImport({ url }, url);
    });

    document.getElementById('import-preview-file-btn').addEventListener('click', async () => {
        const file = importTextFileEl.files?.[0];
        if (!file) {
            setMessage(importMessageEl, 'Choose a text file first.', true);
            return;
        }
        let content = '';
        try {
            content = (await file.text()).trim();
        } catch (_) {
            setMessage(importMessageEl, 'Unable to read selected file.', true);
            return;
        }
        if (!content) {
            setMessage(importMessageEl, 'Selected file is empty.', true);
            return;
        }
        await previewImport({ text: content }, `File: ${file.name}`);
    });

    document.getElementById('import-preview-text-btn').addEventListener('click', async () => {
        const text = importTextEl.value.trim();
        if (!text) {
            setMessage(importMessageEl, 'Paste recipe text first.', true);
            return;
        }
        await previewImport({ text }, 'Pasted text');
    });
    importConfirmBtn.addEventListener('click', async () => {
        if (!importPayload) {
            setMessage(importMessageEl, 'No preview available to confirm.', true);
            return;
        }
        try {
            const importCreatePayload = {
                title: importPayload.title,
                category: importPayload.category || null,
                url: importPayload.source_url || null,
                instructions: (importPayload.steps || []).join('\n'),
                steps: importPayload.steps || [],
                servings: importPayload.servings ?? null,
                prep_time: importPayload.prep_time ?? null,
                cook_time: importPayload.cook_time ?? null,
                ingredients: importPayload.ingredients || [],
            };
            const created = await api.createRecipe(importCreatePayload);
            setMessage(importMessageEl, `Imported and created ${created.title}.`);
            importPayload = null;
            setTimeout(() => nav('list'), 300);
        } catch (err) {
            setMessage(importMessageEl, `Failed to save imported recipe: ${err.message}`, true);
        }
    });

    if (recipeId) {
        titleEl.textContent = 'Edit Recipe';
        importSectionEl.classList.add('hidden');
        try {
            const recipe = await api.getRecipe(recipeId);
            const steps = getRecipeSteps(recipe);
            document.getElementById('f-title').value = recipe.title;
            document.getElementById('f-category').value = recipe.category || '';
            document.getElementById('f-url').value = recipe.url || '';
            document.getElementById('f-servings').value = recipe.servings ?? '';
            document.getElementById('f-prep').value = recipe.prep_time ?? '';
            document.getElementById('f-cook').value = recipe.cook_time ?? '';
            steps.forEach((step) => stepRowsEl.appendChild(stepRow(step)));
            if (recipe.ingredients.length) {
                recipe.ingredients.forEach((item) => rowsEl.appendChild(ingredientRow({
                    name: item.ingredient?.name_en || item.ingredient?.name || '',
                    quantity: item.quantity,
                    unit: item.unit,
                    category: item.ingredient?.category || '',
                    notes: item.notes || '',
                })));
            }
        } catch (err) {
            setMessage(messageEl, `Failed to load recipe: ${err.message}`, true);
        }
    }

    if (!rowsEl.children.length) {
        rowsEl.appendChild(ingredientRow());
    }
    if (!stepRowsEl.children.length) {
        stepRowsEl.appendChild(stepRow());
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const payload = collectFormPayload();
        if (!payload.title || payload.steps.length === 0) {
            setMessage(messageEl, 'Title and at least one step are required.', true);
            return;
        }

        try {
            if (recipeId) {
                const updated = await api.updateRecipe(recipeId, payload);
                setMessage(messageEl, `Updated ${updated.title}.`);
            } else {
                const created = await api.createRecipe(payload);
                setMessage(messageEl, `Created ${created.title}.`);
            }
            setTimeout(() => nav('list'), 300);
        } catch (err) {
            setMessage(messageEl, `Save failed: ${err.message}`, true);
        }
    });
}

async function renderShoppingView() {
    root.innerHTML = '';
    const node = document.getElementById('shopping-view-template').content.cloneNode(true);
    root.appendChild(node);

    const categoriesEl = document.getElementById('shopping-categories');
    const messageEl = document.getElementById('shopping-message');
    const searchEl = document.getElementById('shopping-recipe-search');
    const resultsEl = document.getElementById('shopping-recipe-results');
    const selectedEl = document.getElementById('shopping-selected-recipes');
    const selectionMetaEl = document.getElementById('shopping-selection-meta');
    const langEnBtn = document.getElementById('shopping-lang-en');
    const langEsBtn = document.getElementById('shopping-lang-es');

    let availableRecipes = [];
    let currentSearchResults = [];
    let highlightedSearchIndex = -1;
    let ingredientLanguage = loadIngredientLanguagePreference();
    let latestShoppingData = null;
    state.shoppingRecipeIds = loadShoppingSelectionFromStorage();
    state.shoppingChecks = loadShoppingChecksFromStorage();

    function renderIngredientLanguageToggle() {
        langEnBtn.classList.toggle('active', ingredientLanguage === 'en');
        langEsBtn.classList.toggle('active', ingredientLanguage === 'es');
    }

    langEnBtn.addEventListener('click', () => {
        ingredientLanguage = 'en';
        saveIngredientLanguagePreference(ingredientLanguage);
        renderIngredientLanguageToggle();
        if (latestShoppingData) {
            renderShoppingCategories(latestShoppingData);
        }
    });
    langEsBtn.addEventListener('click', () => {
        ingredientLanguage = 'es';
        saveIngredientLanguagePreference(ingredientLanguage);
        renderIngredientLanguageToggle();
        if (latestShoppingData) {
            renderShoppingCategories(latestShoppingData);
        }
    });

    function renderSelectionMeta() {
        const count = state.shoppingRecipeIds.size;
        const atLimit = count >= 10;
        selectionMetaEl.textContent = atLimit
            ? `${count}/10 recipes selected (max reached)`
            : `${count}/10 recipes selected`;
        selectionMetaEl.classList.toggle('limit-hit', atLimit);
        selectedEl.classList.toggle('limit-hit', atLimit);
    }

    function getFilteredRecipes(searchTerm = '') {
        const terms = searchTerm
            .trim()
            .toLowerCase()
            .split(/\s+/)
            .filter(Boolean);
        const unselected = availableRecipes.filter((recipe) => !state.shoppingRecipeIds.has(recipe.id));
        if (!terms.length) {
            return unselected.slice(0, 40);
        }
        return unselected
            .filter((recipe) => terms.every((term) => recipe.title.toLowerCase().includes(term)))
            .slice(0, 40);
    }

    function renderSelectedFilters() {
        const selectedRecipes = availableRecipes.filter((recipe) => state.shoppingRecipeIds.has(recipe.id));
        selectedEl.innerHTML = '';
        if (!selectedRecipes.length) {
            selectedEl.innerHTML = '<p class="muted">No selected recipes yet.</p>';
            return;
        }
        selectedRecipes.forEach((recipe) => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'selected-filter-chip';
            chip.dataset.removeShoppingRecipeId = String(recipe.id);
            chip.innerHTML = `${escapeHtml(recipe.title)} <span aria-hidden="true">×</span>`;
            selectedEl.appendChild(chip);
        });
        selectedEl.querySelectorAll('[data-remove-shopping-recipe-id]').forEach((button) => {
            button.addEventListener('click', () => {
                state.shoppingRecipeIds.delete(Number(button.dataset.removeShoppingRecipeId));
                saveShoppingSelectionToStorage();
                renderSelectionMeta();
                renderSelectedFilters();
                renderSearchResults(searchEl.value);
            });
        });
    }

    function renderSearchResults(searchTerm = '') {
        const filtered = getFilteredRecipes(searchTerm);
        currentSearchResults = filtered;
        resultsEl.innerHTML = '';
        if (!filtered.length) {
            highlightedSearchIndex = -1;
        } else if (highlightedSearchIndex >= filtered.length) {
            highlightedSearchIndex = filtered.length - 1;
        }
        if (!filtered.length) {
            resultsEl.innerHTML = '<p class="muted">No matching recipes available.</p>';
            return;
        }
        filtered.forEach((recipe) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'recipe-search-item';
            item.dataset.shoppingPickRecipeId = String(recipe.id);
            item.textContent = recipe.title;
            if (currentSearchResults[highlightedSearchIndex]?.id === recipe.id) {
                item.classList.add('active-search-item');
            }
            resultsEl.appendChild(item);
        });
        resultsEl.querySelectorAll('[data-shopping-pick-recipe-id]').forEach((button) => {
            button.addEventListener('click', () => {
                const recipeId = Number(button.dataset.shoppingPickRecipeId);
                if (state.shoppingRecipeIds.size >= 10) {
                    setMessage(messageEl, 'You can select up to 10 recipes.', true);
                    return;
                }
                state.shoppingRecipeIds.add(recipeId);
                saveShoppingSelectionToStorage();
                searchEl.value = '';
                highlightedSearchIndex = -1;
                renderSelectionMeta();
                renderSelectedFilters();
                renderSearchResults('');
            });
        });
    }

    function renderShoppingCategories(data) {
        categoriesEl.innerHTML = '';
        const categories = Object.keys(data.by_category || {});
        if (!categories.length) {
            setMessage(messageEl, 'No shopping items for selected recipes.');
            return;
        }
        const visibleIds = new Set();
        categories.forEach((category) => {
            const section = document.createElement('section');
            section.className = 'card';
            section.innerHTML = `<h3>${escapeHtml(category)}</h3>`;
            const list = document.createElement('ul');
            data.by_category[category].forEach((item) => {
                const id = `${item.ingredient_id}-${item.unit}`;
                visibleIds.add(id);
                const qtyUnit = formatQuantityUnit(item.total_quantity, item.unit);
                const prefix = qtyUnit ? `${escapeHtml(qtyUnit)} ` : '';
                const displayName = getIngredientDisplayName(item, ingredientLanguage);
                const li = document.createElement('li');
                li.innerHTML = `
                    <label class="shopping-item-label">
                        <input type="checkbox" data-shopping-id="${id}" ${state.shoppingChecks.has(id) ? 'checked' : ''}>
                        <span class="shopping-item-text">${prefix}${escapeHtml(displayName)} (${escapeHtml(item.recipes.join(', '))})</span>
                    </label>
                `;
                list.appendChild(li);
            });
            section.appendChild(list);
            categoriesEl.appendChild(section);
        });
        state.shoppingChecks = new Set(
            Array.from(state.shoppingChecks).filter((id) => visibleIds.has(id))
        );
        saveShoppingChecksToStorage();

        categoriesEl.querySelectorAll('[data-shopping-id]').forEach((input) => {
            input.addEventListener('change', () => {
                const id = input.dataset.shoppingId;
                if (input.checked) {
                    state.shoppingChecks.add(id);
                } else {
                    state.shoppingChecks.delete(id);
                }
                saveShoppingChecksToStorage();
            });
        });
    }

    async function loadList() {
        const recipe_ids = Array.from(state.shoppingRecipeIds);
        if (!recipe_ids.length) {
            categoriesEl.innerHTML = '';
            latestShoppingData = null;
            setMessage(messageEl, 'Select recipes above to generate a shopping list.', true);
            return;
        }

        try {
            const data = await api.getShoppingList(recipe_ids);
            latestShoppingData = data;
            setMessage(messageEl, `Generated ${data.items.length} item(s) from ${recipe_ids.length} recipe(s).`);
            renderShoppingCategories(data);
        } catch (err) {
            setMessage(messageEl, `Shopping list failed: ${err.message}`, true);
        }
    }

    document.getElementById('generate-shopping-list').addEventListener('click', loadList);
    document.getElementById('clear-shopping-recipes').addEventListener('click', () => {
        state.shoppingRecipeIds.clear();
        latestShoppingData = null;
        clearShoppingSelectionFromStorage();
        renderSelectionMeta();
        renderSelectedFilters();
        renderSearchResults(searchEl.value);
        categoriesEl.innerHTML = '';
        setMessage(messageEl, 'Recipe selection cleared.');
    });
    document.getElementById('clear-shopping').addEventListener('click', () => {
        state.shoppingChecks.clear();
        clearShoppingChecksFromStorage();
        loadList();
    });

    searchEl.addEventListener('input', () => {
        highlightedSearchIndex = -1;
        renderSearchResults(searchEl.value);
    });
    searchEl.addEventListener('keydown', (event) => {
        if (!currentSearchResults.length) {
            return;
        }
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            highlightedSearchIndex = Math.min(highlightedSearchIndex + 1, currentSearchResults.length - 1);
            renderSearchResults(searchEl.value);
            return;
        }
        if (event.key === 'ArrowUp') {
            event.preventDefault();
            highlightedSearchIndex = Math.max(highlightedSearchIndex - 1, 0);
            renderSearchResults(searchEl.value);
            return;
        }
        if (event.key === 'Escape') {
            searchEl.value = '';
            highlightedSearchIndex = -1;
            renderSearchResults('');
            return;
        }
        if (event.key === 'Enter') {
            event.preventDefault();
            const highlighted =
                highlightedSearchIndex >= 0
                    ? currentSearchResults[highlightedSearchIndex]
                    : currentSearchResults[0];
            if (!highlighted) {
                return;
            }
            if (state.shoppingRecipeIds.size >= 10) {
                setMessage(messageEl, 'You can select up to 10 recipes.', true);
                return;
            }
            state.shoppingRecipeIds.add(highlighted.id);
            saveShoppingSelectionToStorage();
            searchEl.value = '';
            highlightedSearchIndex = -1;
            renderSelectionMeta();
            renderSelectedFilters();
            renderSearchResults('');
        }
    });

    try {
        availableRecipes = await api.getRecipes();
        renderIngredientLanguageToggle();
        const validRecipeIds = new Set(availableRecipes.map((recipe) => recipe.id));
        state.shoppingRecipeIds = new Set(
            Array.from(state.shoppingRecipeIds).filter((recipeId) => validRecipeIds.has(recipeId)).slice(0, 10)
        );
        saveShoppingSelectionToStorage();
        renderSelectionMeta();
        renderSelectedFilters();
        renderSearchResults();
    } catch (err) {
        setMessage(messageEl, `Failed to load recipes: ${err.message}`, true);
    }

    await loadList();
}

async function renderFinderView() {
    root.innerHTML = '';
    const node = document.getElementById('finder-view-template').content.cloneNode(true);
    root.appendChild(node);

    const ingredientsEl = document.getElementById('finder-ingredients');
    const resultsEl = document.getElementById('finder-results');
    const messageEl = document.getElementById('finder-message');
    const toggleBtn = document.getElementById('finder-toggle-mode');
    const manageIngredientsBtn = document.getElementById('finder-manage-ingredients');
    const selectPanelEl = document.getElementById('finder-select-panel');
    const resultsPanelEl = document.getElementById('finder-results-panel');
    let suggestionsMode = false;
    let suggestionsDebounce = null;

    function renderFinderMode() {
        if (suggestionsMode) {
            selectPanelEl.classList.add('hidden');
            resultsPanelEl.classList.remove('hidden');
            toggleBtn.textContent = 'Show Ingredient List';
        } else {
            selectPanelEl.classList.remove('hidden');
            resultsPanelEl.classList.add('hidden');
            toggleBtn.textContent = 'Show Suggestions';
        }
    }

    toggleBtn.addEventListener('click', () => {
        suggestionsMode = !suggestionsMode;
        renderFinderMode();
    });
    manageIngredientsBtn.addEventListener('click', () => nav('ingredients'));

    try {
        state.ingredients = await api.getIngredients();
        if (!state.ingredients.length) {
            setMessage(messageEl, 'No ingredients available yet. Create recipes first.');
            suggestionsMode = true;
            renderFinderMode();
            return;
        }
        ingredientsEl.innerHTML = '';
        state.ingredients.forEach((ingredient) => {
            const checked = ingredient.default_available ? 'checked' : '';
            const label = document.createElement('label');
            label.className = 'chip ingredient-chip';
            label.innerHTML = `<input type="checkbox" value="${ingredient.id}" ${checked}> ${escapeHtml(ingredient.name)}`;
            ingredientsEl.appendChild(label);
        });
        ingredientsEl.querySelectorAll('input[type="checkbox"]').forEach((input) => {
            input.addEventListener('change', () => {
                clearTimeout(suggestionsDebounce);
                suggestionsDebounce = setTimeout(() => {
                    loadSuggestions();
                }, 250);
            });
        });
        loadSuggestions();
    } catch (err) {
        setMessage(messageEl, `Failed to load ingredients: ${err.message}`, true);
        return;
    }

    async function loadSuggestions() {
        const selected = Array.from(ingredientsEl.querySelectorAll('input:checked')).map((el) => Number(el.value));
        if (!selected.length) {
            resultsEl.innerHTML = '';
            setMessage(messageEl, 'Select ingredients to see matching recipes.');
            return;
        }
        try {
            const data = await api.getSuggestions(selected);
            resultsEl.innerHTML = '';
            if (!data.suggestions.length) {
                setMessage(messageEl, 'No matching recipes found.');
                return;
            }
            setMessage(messageEl, `Found ${data.suggestions.length} suggestion(s).`);
            data.suggestions.forEach((entry) => {
                const card = document.createElement('article');
                card.className = 'card';
                card.innerHTML = `
                    <h3>${escapeHtml(entry.recipe.title)}</h3>
                    <p>${entry.match_count}/${entry.total_ingredients} ingredients matched (${entry.match_percentage}%)</p>
                    <p><strong>Matched:</strong> ${escapeHtml(entry.matched_ingredients.join(', ') || 'None')}</p>
                    <p><strong>Missing:</strong> ${escapeHtml(entry.missing_ingredients.join(', ') || 'None')}</p>
                    <button data-open-recipe="${entry.recipe.id}">Open Recipe</button>
                `;
                resultsEl.appendChild(card);
            });
            resultsEl.querySelectorAll('[data-open-recipe]').forEach((button) => {
                button.addEventListener('click', () => nav('detail', { id: Number(button.dataset.openRecipe) }));
            });
        } catch (err) {
            setMessage(messageEl, `Suggestions failed: ${err.message}`, true);
        }
    }

    renderFinderMode();
}

async function renderIngredientsView() {
    root.innerHTML = '';
    const node = document.getElementById('ingredients-view-template').content.cloneNode(true);
    root.appendChild(node);

    const listEl = document.getElementById('ingredient-default-list');
    const messageEl = document.getElementById('ingredient-default-message');
    const searchEl = document.getElementById('ingredient-default-search');
    const mergePrimaryEl = document.getElementById('merge-primary');
    const mergeSecondaryEl = document.getElementById('merge-secondary');
    const mergePreviewBtn = document.getElementById('merge-preview-btn');
    const mergeExecuteBtn = document.getElementById('merge-execute-btn');
    const mergeConfirmCollisionEl = document.getElementById('merge-confirm-collision');
    const mergePreviewOutputEl = document.getElementById('merge-preview-output');
    const mergeHistoryListEl = document.getElementById('merge-history-list');
    let ingredients = [];
    let recipeUsageByIngredientId = new Map();
    let latestPreview = null;

    async function loadRecipeUsage() {
        const usageMap = new Map();
        const usagePromises = ingredients.map(async (ingredient) => {
            try {
                const recipes = await api.getRecipesByIngredient(ingredient.id);
                usageMap.set(
                    ingredient.id,
                    recipes.map((recipe) => recipe.title).filter(Boolean),
                );
            } catch (_) {
                usageMap.set(ingredient.id, []);
            }
        });
        await Promise.all(usagePromises);
        recipeUsageByIngredientId = usageMap;
    }

    function renderList(search = '') {
        const term = search.trim().toLowerCase();
        const filtered = ingredients.filter((ingredient) => {
            if (!term) {
                return true;
            }
            const english = String(ingredient.name_en || ingredient.name || '').toLowerCase();
            const spanish = String(ingredient.name_es || ingredient.name_en || ingredient.name || '').toLowerCase();
            const recipeTitles = recipeUsageByIngredientId.get(ingredient.id) || [];
            const recipeMatch = recipeTitles.some((title) => String(title || '').toLowerCase().includes(term));
            return english.includes(term) || spanish.includes(term) || recipeMatch;
        });
        listEl.innerHTML = '';
        if (!filtered.length) {
            listEl.innerHTML = '<tr><td colspan="6" class="muted ingredient-empty">No ingredients found.</td></tr>';
            return;
        }
        filtered.forEach((ingredient) => {
            const row = document.createElement('tr');
            const checked = ingredient.default_available ? 'checked' : '';
            const recipes = recipeUsageByIngredientId.get(ingredient.id) || [];
            const recipesLabel = recipes.length ? recipes.join(' • ') : 'Not used in any recipe';
            const englishName = ingredient.name_en || ingredient.name || '';
            const spanishName = ingredient.name_es || ingredient.name_en || ingredient.name || '';
            row.innerHTML = `
                <td class="ingredient-col-default">
                    <input type="checkbox" data-ingredient-default-id="${ingredient.id}" ${checked} aria-label="Default ${escapeHtml(englishName)}">
                </td>
                <td class="ingredient-col-name">
                    <input type="text" data-ingredient-name-en-id="${ingredient.id}" value="${escapeHtml(englishName)}" aria-label="English name">
                </td>
                <td class="ingredient-col-name">
                    <input type="text" data-ingredient-name-es-id="${ingredient.id}" value="${escapeHtml(spanishName)}" aria-label="Spanish name">
                </td>
                <td class="ingredient-col-save">
                    <button type="button" class="ingredient-save-btn" data-save-ingredient-id="${ingredient.id}">Save</button>
                </td>
                <td class="ingredient-col-delete">
                    <button type="button" class="ingredient-delete-btn" data-delete-ingredient-id="${ingredient.id}" aria-label="Delete ${escapeHtml(englishName)}">×</button>
                </td>
                <td>
                    <div class="ingredient-usage-scroll" title="${escapeHtml(recipesLabel)}">${escapeHtml(recipesLabel)}</div>
                </td>
            `;
            listEl.appendChild(row);
        });
        listEl.querySelectorAll('[data-save-ingredient-id]').forEach((button) => {
            button.addEventListener('click', async () => {
                const ingredientId = Number(button.dataset.saveIngredientId);
                const enInput = listEl.querySelector(`[data-ingredient-name-en-id="${ingredientId}"]`);
                const esInput = listEl.querySelector(`[data-ingredient-name-es-id="${ingredientId}"]`);
                const nameEn = String(enInput?.value || '').trim();
                const nameEs = String(esInput?.value || '').trim();
                if (!nameEn || !nameEs) {
                    setMessage(messageEl, 'Both English and Spanish ingredient names are required.', true);
                    return;
                }
                try {
                    const updated = await api.updateIngredientNames(ingredientId, {
                        name_en: nameEn,
                        name_es: nameEs,
                    });
                    const target = ingredients.find((item) => item.id === ingredientId);
                    if (target) {
                        target.name = updated.name;
                        target.name_en = updated.name_en;
                        target.name_es = updated.name_es;
                    }
                    setMessage(messageEl, 'Ingredient names updated.');
                    renderList(searchEl.value);
                    renderMergeSelectors();
                } catch (err) {
                    setMessage(messageEl, `Failed to update ingredient names: ${err.message}`, true);
                }
            });
        });
        listEl.querySelectorAll('[data-ingredient-default-id]').forEach((input) => {
            input.addEventListener('change', async () => {
                const ingredientId = Number(input.dataset.ingredientDefaultId);
                try {
                    const updated = await api.updateIngredientPreference(ingredientId, {
                        default_available: input.checked,
                    });
                    const target = ingredients.find((item) => item.id === ingredientId);
                    if (target) {
                        target.default_available = updated.default_available;
                    }
                    setMessage(messageEl, 'Ingredient defaults updated.');
                } catch (err) {
                    input.checked = !input.checked;
                    setMessage(messageEl, `Failed to update default ingredient: ${err.message}`, true);
                }
            });
        });
        listEl.querySelectorAll('[data-delete-ingredient-id]').forEach((button) => {
            button.addEventListener('click', async () => {
                const ingredientId = Number(button.dataset.deleteIngredientId);
                const target = ingredients.find((item) => item.id === ingredientId);
                const ingredientName = getIngredientDisplayName(target || {}, 'en') || 'this ingredient';
                const usageTitles = recipeUsageByIngredientId.get(ingredientId) || [];
                const usageCount = usageTitles.length;
                const warning = usageCount
                    ? `Delete ${ingredientName} from ${usageCount} recipe(s)? This removes it from those recipes.`
                    : `Delete ${ingredientName}?`;
                if (!confirm(warning)) {
                    return;
                }
                try {
                    const result = await api.deleteIngredient(ingredientId);
                    ingredients = ingredients.filter((item) => item.id !== ingredientId);
                    recipeUsageByIngredientId.delete(ingredientId);
                    renderList(searchEl.value);
                    renderMergeSelectors();
                    await renderMergeHistory();
                    setMessage(
                        messageEl,
                        `Deleted ${result.name}. Removed from ${result.affected_recipe_count} recipe(s).`,
                    );
                } catch (err) {
                    setMessage(messageEl, `Failed to delete ingredient: ${err.message}`, true);
                }
            });
        });
    }

    function renderMergeSelectors() {
        mergePrimaryEl.innerHTML = '';
        mergeSecondaryEl.innerHTML = '';
        const sorted = [...ingredients].sort((a, b) => {
            const left = getIngredientDisplayName(a, 'en');
            const right = getIngredientDisplayName(b, 'en');
            return left.localeCompare(right);
        });
        sorted.forEach((ingredient) => {
            const optionPrimary = document.createElement('option');
            optionPrimary.value = String(ingredient.id);
            optionPrimary.textContent = getIngredientDisplayName(ingredient, 'en');
            mergePrimaryEl.appendChild(optionPrimary);

            const optionSecondary = document.createElement('option');
            optionSecondary.value = String(ingredient.id);
            optionSecondary.textContent = getIngredientDisplayName(ingredient, 'en');
            mergeSecondaryEl.appendChild(optionSecondary);
        });
        if (sorted.length >= 2) {
            mergePrimaryEl.value = String(sorted[0].id);
            mergeSecondaryEl.value = String(sorted[1].id);
        }
    }

    async function renderMergeHistory() {
        mergeHistoryListEl.innerHTML = '';
        try {
            const history = await api.getIngredientMergeHistory();
            if (!history.length) {
                mergeHistoryListEl.innerHTML = '<p class="muted">No merge operations yet.</p>';
                return;
            }
            history.forEach((eventItem) => {
                const row = document.createElement('div');
                row.className = 'merge-history-item';
                const undone = !!eventItem.undone_at;
                row.innerHTML = `
                    <p><strong>${escapeHtml(eventItem.secondary_name_before)}</strong> → <strong>${escapeHtml(eventItem.primary_name_before)}</strong></p>
                    <p class="muted">Merged: ${escapeHtml(eventItem.merged_at)}${undone ? ` | Undone: ${escapeHtml(eventItem.undone_at)}` : ''}</p>
                    ${undone ? '' : `<button type="button" data-undo-merge-id="${eventItem.id}">Undo</button>`}
                `;
                mergeHistoryListEl.appendChild(row);
            });
            mergeHistoryListEl.querySelectorAll('[data-undo-merge-id]').forEach((button) => {
                button.addEventListener('click', async () => {
                    const mergeEventId = Number(button.dataset.undoMergeId);
                    try {
                        const result = await api.undoIngredientMerge(mergeEventId);
                        setMessage(
                            messageEl,
                            `Undo complete. Restored ${result.restored_secondary_name}.`,
                        );
                        ingredients = await api.getIngredients();
                        renderList(searchEl.value);
                        renderMergeSelectors();
                        await renderMergeHistory();
                    } catch (err) {
                        setMessage(messageEl, `Failed to undo merge: ${err.message}`, true);
                    }
                });
            });
        } catch (err) {
            mergeHistoryListEl.innerHTML = `<p class="message error">Failed to load merge history: ${escapeHtml(err.message)}</p>`;
        }
    }

    mergePreviewBtn.addEventListener('click', async () => {
        const primaryId = Number(mergePrimaryEl.value);
        const secondaryId = Number(mergeSecondaryEl.value);
        if (!primaryId || !secondaryId || primaryId === secondaryId) {
            setMessage(messageEl, 'Choose two different ingredients for merge.', true);
            return;
        }
        try {
            latestPreview = await api.getIngredientMergePreview({
                primary_id: primaryId,
                secondary_id: secondaryId,
            });
            mergePreviewOutputEl.classList.remove('hidden');
            const hasCollision = latestPreview.collision_recipe_count > 0;
            mergePreviewOutputEl.innerHTML = `
                <h4>Merge Preview</h4>
                <p><strong>Primary:</strong> ${escapeHtml(latestPreview.primary.name)}</p>
                <p><strong>Secondary:</strong> ${escapeHtml(latestPreview.secondary.name)}</p>
                <p><strong>Secondary usages:</strong> ${latestPreview.secondary_recipe_count}</p>
                <p><strong>Collisions:</strong> ${latestPreview.collision_recipe_count}</p>
                ${hasCollision ? `<p class="message error">Warning: in collision recipes, secondary will be removed.</p>` : ''}
                ${hasCollision && latestPreview.collision_recipe_titles.length ? `<p class="muted">Recipes: ${escapeHtml(latestPreview.collision_recipe_titles.join(', '))}</p>` : ''}
            `;
            setMessage(messageEl, 'Merge preview ready.');
        } catch (err) {
            latestPreview = null;
            mergePreviewOutputEl.classList.add('hidden');
            setMessage(messageEl, `Failed to preview merge: ${err.message}`, true);
        }
    });

    mergeExecuteBtn.addEventListener('click', async () => {
        const primaryId = Number(mergePrimaryEl.value);
        const secondaryId = Number(mergeSecondaryEl.value);
        if (!primaryId || !secondaryId || primaryId === secondaryId) {
            setMessage(messageEl, 'Choose two different ingredients for merge.', true);
            return;
        }
        const confirmCollisionDrop = mergeConfirmCollisionEl.checked;
        try {
            const result = await api.mergeIngredients({
                primary_id: primaryId,
                secondary_id: secondaryId,
                confirm_collision_drop: confirmCollisionDrop,
            });
            setMessage(
                messageEl,
                `Merged ${result.secondary.name} into ${result.primary.name}. Repointed ${result.repointed_rows}, removed collisions ${result.dropped_collision_rows}.`,
            );
            mergePreviewOutputEl.classList.add('hidden');
            mergeConfirmCollisionEl.checked = false;
            latestPreview = null;
            ingredients = await api.getIngredients();
            await loadRecipeUsage();
            renderList(searchEl.value);
            renderMergeSelectors();
            await renderMergeHistory();
        } catch (err) {
            setMessage(messageEl, `Merge failed: ${err.message}`, true);
        }
    });

    searchEl.addEventListener('input', () => renderList(searchEl.value));

    try {
        ingredients = await api.getIngredients();
        await loadRecipeUsage();
        renderList(searchEl.value);
        renderMergeSelectors();
        await renderMergeHistory();
    } catch (err) {
        setMessage(messageEl, `Failed to load ingredients: ${err.message}`, true);
    }
}

async function render() {
    if (!state.authReady) {
        return;
    }
    renderHeaderAuth();
    if (!state.authUser) {
        await renderLoginView();
        return;
    }
    if (state.route === 'list') {
        await renderListView();
        return;
    }
    if (state.route === 'detail') {
        if (!state.detailRecipeId) {
            nav('list');
            return;
        }
        await renderDetailView(state.detailRecipeId);
        return;
    }
    if (state.route === 'add') {
        await renderFormView(null);
        return;
    }
    if (state.route === 'edit') {
        if (!state.editRecipeId) {
            nav('list');
            return;
        }
        await renderFormView(state.editRecipeId);
        return;
    }
    if (state.route === 'shopping') {
        await renderShoppingView();
        return;
    }
    if (state.route === 'finder') {
        await renderFinderView();
        return;
    }
    if (state.route === 'ingredients') {
        await renderIngredientsView();
        return;
    }
    nav('list');
}

async function bootstrapAuth() {
    try {
        const session = await api.me();
        state.authUser = { username: session.username };
        state.route = 'list';
    } catch (_) {
        state.authUser = null;
        state.route = 'login';
    } finally {
        state.authReady = true;
    }
}

bootstrapAuth().then(render);
