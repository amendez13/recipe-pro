# Recipe Pro - Project Specification

## Overview

Recipe Pro is a FastAPI web application for managing recipes with a focus on usability while cooking. The app provides convenient recipe entry, clear presentation during cooking, and smart features for shopping list generation and ingredient-based recipe discovery.

The app runs with two-user authentication and strict per-user data isolation (each user has their own SQLite database).

## Core Functionality

### Recipe Management
- **Add recipes** with title, ordered cooking steps, and ingredients
- **Store recipes** in SQLite database
- **Present recipes** in a fast, convenient format optimized for use while cooking
  - Large, readable text
  - Clearly separated step-by-step instructions
  - Focus mode to show one step at a time with next/back controls
  - Ingredients displayed when needed (collapsible or always visible)
  - Mobile-friendly for kitchen use

### Convenient Recipe Entry
- Simple form for adding recipes
- Easy ingredient input (name + quantity + unit)
- Support for pasting recipe text and parsing
- Edit and delete existing recipes

## Features

### Shopping List Generation
- Select multiple recipes from the list
- Generate a consolidated shopping list
- Combine duplicate ingredients (e.g., 2 recipes needing onions → total quantity)
- Group by category (produce, dairy, meat, pantry, etc.) if available

### Ingredient-Based Recipe Suggestions
- Present a list of all unique ingredients across all recipes
- User selects ingredients they have available
- System suggests best-matching recipes based on:
  - Number of matching ingredients
  - Percentage of recipe ingredients matched
- Sort by best match (most ingredients matched)

## Data Model

### SQLite Database Schema

```
ingredients
├── id (PRIMARY KEY)
├── name (UNIQUE, normalized lowercase)
├── category (optional: produce, dairy, meat, pantry, spices, etc.)
└── default_available (BOOLEAN/INTEGER, default ingredient selection for finder)

recipes
├── id (PRIMARY KEY)
├── title
├── instructions (TEXT - compatibility field, derived from steps)
├── servings (optional)
├── prep_time (optional, minutes)
├── cook_time (optional, minutes)
├── created_at
└── updated_at

recipe_steps
├── id (PRIMARY KEY)
├── recipe_id (FOREIGN KEY → recipes)
├── step_order (INTEGER, starts at 1)
└── instruction (TEXT)

recipe_ingredients (junction table)
├── id (PRIMARY KEY)
├── recipe_id (FOREIGN KEY → recipes)
├── ingredient_id (FOREIGN KEY → ingredients)
├── quantity (REAL)
├── unit (TEXT: cups, tbsp, tsp, oz, g, pieces, etc.)
└── notes (optional: "diced", "room temperature", etc.)
```

### Multi-user Isolation
- The system is configured for exactly 2 users.
- Each user has a dedicated SQLite database file (`db_path`) and only accesses their own data.
- All recipe APIs require authenticated session cookies.

### Key Constraints
- Ingredients are **unique references** - same ingredient used across multiple recipes points to same record
- Ingredient names are normalized (lowercase, trimmed) for deduplication
- Recipe-ingredient relationship is many-to-many via junction table
- Recipe steps are persisted in order and rendered as discrete steps

## API Endpoints

### Recipes
- `GET /api/recipes` - List all recipes (with optional search)
- `POST /api/recipes` - Create recipe with ingredients
- `GET /api/recipes/{id}` - Get recipe detail with ingredients
- `PUT /api/recipes/{id}` - Update recipe
- `DELETE /api/recipes/{id}` - Delete recipe

### Ingredients
- `GET /api/ingredients` - List all unique ingredients
- `GET /api/ingredients/{id}/recipes` - Get recipes using this ingredient
- `POST /api/ingredients/{id}/default` - Set ingredient `default_available`
- `POST /api/ingredients/{id}` - Compatibility route for setting `default_available`
- `PATCH /api/ingredients/{id}` - Compatibility route for setting `default_available`

### Shopping List
- `POST /api/shopping-list` - Generate shopping list from recipe IDs
  - Body: `{ "recipe_ids": [1, 2, 3] }`
  - Returns consolidated, grouped ingredient list

### Recipe Suggestions
- `POST /api/suggestions` - Get recipe suggestions from ingredient IDs
  - Body: `{ "ingredient_ids": [1, 2, 3, 4] }`
  - Returns recipes sorted by match percentage

### Stats
- `GET /api/stats` - Recipe count, ingredient count, etc.

### Authentication
- `POST /api/auth/login` - Username/password login, sets auth cookie
- `POST /api/auth/logout` - Clears auth cookie
- `GET /api/auth/me` - Returns current authenticated user

## UI Views

### Home / Recipe List
- Grid or list of recipe cards
- Search/filter functionality
- Compact list on mobile with clickable title to open recipe

### Recipe Detail (Cooking Mode)
- Large, clear typography
- Step-by-step instructions with numbered, separated steps
- Focus mode panel below ingredients with next/back navigation
- Ingredients panel (sticky or collapsible)
- Timer integration (future)

### Add/Edit Recipe
- Title input
- Step-by-step entry (add/remove step rows)
- Ingredient entry with autocomplete from existing ingredients
- Dynamic add/remove ingredient rows

### Shopping List
- Independent recipe selector inside Shopping List view (no dependency on Recipe List)
- Search box with real-time filtered clickable results
- Selected recipes shown as removable filter chips (max 10 selected)
- Keyboard support (arrow navigation + Enter to add)
- Generate button
- Display consolidated list grouped by category
- Checkboxes for marking items as purchased

### Recipe Finder (by ingredients)
- Toggle between ingredient selection panel and suggestions panel
- Dynamic suggestions update when ingredient selection changes (debounced)
- Default-selected ingredients loaded from `ingredients.default_available`
- Dedicated button to open Ingredient Defaults management view
- Results sorted by match quality
- Show match percentage and missing ingredients

### Ingredient Defaults
- Dedicated view for managing default ingredient availability
- Search/filter all ingredients
- Toggle each ingredient as default available (persisted in DB)

## Tech Stack

- **Backend**: FastAPI + SQLite
- **Frontend**: Vanilla JS + CSS (SPA pattern)
- **Deployment**: Ansible + systemd (Tailscale/public host binding supported)

## Non-Goals (v1)

- Image upload for recipes
- Meal planning calendar
- Nutritional information
- Recipe import from URLs
