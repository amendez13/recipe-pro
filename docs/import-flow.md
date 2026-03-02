# Recipe Import Flow

This diagram documents the current end-to-end implementation for recipe import, from URL input through preview generation and final recipe creation.

```mermaid
flowchart TD
    A["User enters recipe URL"] --> B["POST /api/recipes/import-preview"]
    B --> C["Auth, health check, load existing ingredient names"]
    C --> D{"URL valid"}
    D -- "No" --> E["HTTP 400 invalid URL"]
    D -- "Yes" --> F["Deterministic extract from URL"]

    F --> G{"Structured recipe found"}
    G -- "Yes" --> H["Post process ingredients"]
    H --> I["Add warnings and ai_status"]
    I --> J["Return preview JSON"]

    G -- "No" --> K["Extract recipe focused text from page"]
    K --> L{"Text extracted"}

    L -- "Yes" --> M["Build prompt with page text"]
    M --> N["Claude call without web fetch"]
    N --> O{"Text based Claude success"}
    O -- "Yes" --> P["Use Claude text result"]
    O -- "No" --> Q{"AI runtime ready"}
    Q -- "No" --> R["HTTP 502 with actionable error"]
    Q -- "Yes" --> S["Claude call with web fetch"]
    S --> T["Use Claude web result"]

    L -- "No" --> U["Claude URL call with web fetch"]
    U --> V{"Claude URL success"}
    V -- "No" --> W["Propagate error"]
    V -- "Yes" --> X["Use Claude URL result"]

    P --> Y["Post process ingredients"]
    T --> Y
    X --> Y
    Y --> Z{"Any valid ingredients"}
    Z -- "No" --> AA["HTTP 422 no valid ingredients"]
    Z -- "Yes" --> AB["Add warnings and ai_status"]
    AB --> J

    J --> AC["Frontend shows preview and enables confirm"]
    AC --> AD["User confirms import"]
    AD --> AE["POST /api/recipes"]
    AE --> AF["Recipe stored in DB and shown in UI"]
```

Notes:
- Deterministic extraction includes JSON-LD and HTML/microdata fallbacks.
- The text-first AI fallback is attempted before WebFetch AI when URL parsing fails.
- Ingredient post-processing runs for both deterministic and AI paths.
