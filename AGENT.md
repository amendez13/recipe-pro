# Recipe Pro - Project Specification

## Overview

Recipe Pro is a FastAPI web application for managing recipes with a focus on usability while cooking. The app provides convenient recipe entry, clear presentation during cooking, and smart features for shopping list generation and ingredient-based recipe discovery.

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
└── category (optional: produce, dairy, meat, pantry, spices, etc.)

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

## UI Views

### Home / Recipe List
- Grid or list of recipe cards
- Search/filter functionality
- Quick select for shopping list generation

### Recipe Detail (Cooking Mode)
- Large, clear typography
- Step-by-step instructions (optionally one step at a time)
- Ingredients panel (sticky or collapsible)
- Timer integration (future)

### Add/Edit Recipe
- Title input
- Step-by-step entry (add/remove step rows)
- Ingredient entry with autocomplete from existing ingredients
- Dynamic add/remove ingredient rows

### Shopping List
- Multi-select recipes
- Generate button
- Display consolidated list grouped by category
- Checkboxes for marking items as purchased

### Recipe Finder (by ingredients)
- Checkbox list of all ingredients
- "Find Recipes" button
- Results sorted by match quality
- Show match percentage and missing ingredients

## Tech Stack

- **Backend**: FastAPI + SQLite
- **Frontend**: Vanilla JS + CSS (SPA pattern)
- **Deployment**: Ansible + systemd (Tailscale-only access)

## Non-Goals (v1)

- User authentication (single-user app)
- Image upload for recipes
- Meal planning calendar
- Nutritional information
- Recipe import from URLs
