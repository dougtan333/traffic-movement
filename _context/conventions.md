# conventions.md — Traffic Movement
> Code standards, documentation rules, and naming conventions for this project. Every contributor and every Claude session follows these without exception.

---

## Architecture

### Modular by default
- Every file has a single, clear responsibility. If a file is doing two things, it gets split.
- Maximum **150 lines per file** — if you're approaching this, stop and consider splitting before continuing.
- No logic in entry points. `index.jsx` and `main.jsx` wire things together, they don't contain business logic.
- Data logic and UI logic are never mixed in the same file.

### Folder structure
```
traffic-movement/
  _context/              ← Claude context files (non-code)
  src/
    components/          ← React UI components, one per file
      ComponentName/
        index.jsx
        ComponentName.jsx
        ComponentName.css
        README.md
    modules/             ← Business logic, data processing, utilities
      moduleName/
        index.js
        moduleName.js
        README.md
    queries/             ← DuckDB queries, one concern per file
      queryName.js
      README.md
    hooks/               ← Custom React hooks
    context/             ← React context providers
    constants/           ← App-wide constants and config
  public/
  README.md              ← Project-level README
  RUNTIME.md             ← Runtime process documentation
```

---

## Documentation rules

Documentation is written **as the code is built**, never retrofitted.

### 1. Inline comments
Every function, query, and component gets an inline comment block. Use JSDoc format:

```javascript
/**
 * Fetches traffic volume data for a given city and date range.
 *
 * @param {string} city - City identifier (e.g. 'sydney', 'melbourne')
 * @param {string} dateFrom - Start date in ISO format (YYYY-MM-DD)
 * @param {string} dateTo - End date in ISO format (YYYY-MM-DD)
 * @returns {Array} Array of traffic volume records
 *
 * @source Australian Traffic Data API — data.gov.au
 */
```

- Non-obvious logic gets a plain comment explaining *why*, not just *what*
- Data transformations must note the source schema and output shape
- Anything that touches external data must cite the source

### 2. README per module
Every folder under `src/components/` and `src/modules/` gets a `README.md` containing:
- **What this module does** — one paragraph
- **Inputs and outputs** — what it expects, what it returns
- **Dependencies** — what it relies on internally and externally
- **Usage example** — minimal working example
- **Notes** — edge cases, known limitations, decisions made

### 3. Project-level README
`/README.md` at the root covers:
- Project overview and purpose
- Tech stack
- How to install and run locally
- Folder structure overview
- Link to RUNTIME.md for operational detail
- Link to `_context/` for Claude context files

### 4. RUNTIME.md
`/RUNTIME.md` documents the live running process:
- How data is ingested and refreshed
- Environment variables required
- Startup sequence
- Known runtime dependencies (DuckDB file paths, API keys, etc.)
- How to verify the app is working correctly
- Common runtime errors and how to resolve them

---

## Naming conventions

| Thing | Convention | Example |
|-------|-----------|---------|
| React components | PascalCase | `TrafficChart.jsx` |
| Hooks | camelCase, `use` prefix | `useTrafficData.js` |
| Modules / utilities | camelCase | `formatDateRange.js` |
| DuckDB queries | camelCase, descriptive | `getVolumeByCity.js` |
| Constants | UPPER_SNAKE_CASE | `MAX_DATE_RANGE` |
| CSS classes | kebab-case | `traffic-chart__legend` |
| Folders | kebab-case | `city-selector/` |

---

## DuckDB conventions

- One query per file under `src/queries/`
- Queries are pure functions — they receive parameters and return data, no side effects
- All queries include a comment block citing the data source and describing the return shape
- No raw SQL strings outside of `src/queries/` — all data access goes through query modules
- Query files are named for what they return, not how they work: `getCityTrends.js` not `runJoinQuery.js`

---

## React / JSX conventions

- One component per file
- Props are documented with JSDoc `@param` on the component function
- No inline styles — use CSS files or a consistent styling approach
- Components are presentational or container — never both in the same file
- Keep components under 150 lines; extract sub-components if growing beyond that

---

## Git conventions

- Commit messages: `type: short description` — e.g. `feat: add city selector component`
- Types: `feat`, `fix`, `data`, `docs`, `refactor`, `test`
- Never commit broken code to main
- Each module or feature gets its own branch

---

*See also: `context.md` (project overview), `decisions.md` (why certain choices were made)*
