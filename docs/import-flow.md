# Recipe Import Flow

This diagram documents the current end-to-end implementation for recipe import, from URL input through preview generation and final recipe creation.

```mermaid
flowchart TD
    A[User pastes recipe URL in Import Assistant] --> B[Frontend calls POST /api/recipes/import-preview with url]
    B --> C[Backend: auth + runtime health check + load existing ingredient names]
    C --> D{URL valid http/https + netloc?}
    D -- No --> E[400 Invalid URL]
    D -- Yes --> F[Try deterministic extraction: _extract_recipe_from_url]

    F --> G{Structured recipe found?}
    G -- Yes --> H[Post-process ingredients: split compounds, normalize qty/unit, bilingual fill, DB-name matching]
    H --> I[Attach warnings + ai_status]
    I --> J[Return preview JSON]

    G -- No --> K[Extract recipe-focused text: _extract_recipe_text_from_url]
    K --> L{Text extracted?}

    L -- Yes --> M[Build PAGE TEXT prompt]
    M --> N[Claude import call with allow_web_fetch=false]
    N --> O{Claude text call success?}
    O -- Yes --> P[Use Claude result]
    O -- No --> Q[If AI not ready and status in 422/502/504 -> 502 actionable error]
    O -- No --> R[Last resort Claude call with allow_web_fetch=true]
    R --> S[Use Claude web-fetch result]

    L -- No --> T[Claude URL call with allow_web_fetch=true]
    T --> U{Claude URL call success?}
    U -- No --> V[Propagate error or 502 if AI runtime not ready]
    U -- Yes --> W[Use Claude URL result]

    P --> X[Post-process ingredients]
    S --> X
    W --> X
    X --> Y{Any valid ingredients after post-process?}
    Y -- No --> Z[422 Imported recipe has no valid ingredients]
    Y -- Yes --> AA[Attach warnings + ai_status]
    AA --> J

    J --> AB[Frontend renders preview + enables Confirm and Add Recipe]
    AB --> AC[User confirms import]
    AC --> AD[Frontend maps preview -> POST /api/recipes]
    AD --> AE[Backend creates recipe in DB]
    AE --> AF[Recipe created and shown in UI]
```

Notes:
- Deterministic extraction includes JSON-LD and HTML/microdata fallbacks.
- The text-first AI fallback is attempted before WebFetch AI when URL parsing fails.
- Ingredient post-processing runs for both deterministic and AI paths.
