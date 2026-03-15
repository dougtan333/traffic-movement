# context.md — Traffic Movement
> Project background and domain knowledge. Load this at the start of every session on this project.

---

## What this project is

**Traffic Movement** is a public-facing web application that tracks and visualises traffic and people movement trends across Australian cities. It takes publicly available movement data, enriches it with historical context, and presents it in a way that is visually engaging and genuinely useful to a broad audience — from curious individuals to researchers and urban planners.

The core insight is that movement data tells a story. In normal times it reflects the rhythm of city life. In times of significant change — COVID lockdowns, major events, infrastructure shifts — patterns change dramatically. Overlaying current data against historical baselines is central to the product's value.

---

## Who it's for

- **General public** — curious about their city, want to explore trends without needing expertise
- **Researchers and analysts** — need reliable data, historical depth, and potentially raw access
- **Urban planners and government** — interested in long-term trends and anomaly detection

The UI must serve all three. Non-technical users get guided, visual, intuitive exploration. Power users get depth, comparisons, and (eventually) data access.

---

## Geographic scope

- **Australia-first** — major cities are the initial focus
- City selection driven by data availability
- User selects their city or region of interest
- Architecture must support expanding to additional cities without structural changes

---

## Data

- Sources to be detailed in `data.md` as they are confirmed and integrated
- All data must be verified back to original source before use — no derived or assumed values
- Historical overlays are a core feature — data pipeline must retain and expose historical records, not just current state
- DuckDB is the data layer for all querying and processing

---

## Core product principles

Every build of this product must have:

- **Accurate data** — sourced, verified, traceable. No approximations presented as fact.
- **Great visual design** — clean, considered, not a dashboard. Feels like a product, not a tool.
- **Intuitive UX** — a new user should understand what they're looking at within seconds.
- **Useful commentary** — contextual help notes and annotations that guide users through what the data means, especially during anomalous periods (e.g. COVID, major events).
- **Onboarding support** — new users get enough context to orient themselves without needing documentation.

---

## Authentication

- Auth approach assessed at build time based on user tier requirements
- Free tier: public access, no login required
- Extended access tier: requires authentication — solution TBD
- Architecture must treat auth as a modular layer, not baked into core data or UI logic

---

## Monetisation

- Extended access model planned — exact features TBD
- Likely direction: deeper historical data, more cities, raw data export, or custom comparisons
- Payment integration deferred — architecture must accommodate it without requiring structural changes when it arrives
- Keep payment logic fully isolated as a module from day one

---

## Technical context

- **Frontend:** JSX (React)
- **Data layer:** DuckDB
- **Architecture:** Modular, fully documented. Every component and query is a discrete, documented unit.
- **Deployment:** Web-fronted, URL-based

---

## What this project is not

- Not a real-time traffic navigation tool (that's Google Maps)
- Not a raw data repository — data is curated and presented with context
- Not city-infrastructure tooling — the audience is people, not systems

---

*See also: `data.md` (sources), `stage.md` (current phase), `decisions.md` (architecture choices), `conventions.md` (code standards)*
