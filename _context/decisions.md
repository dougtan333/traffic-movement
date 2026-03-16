# decisions.md — Traffic Movement
> Architecture and product decisions log. Every significant choice is recorded here with its rationale. Once logged, decisions are not revisited without a new entry explaining why.

---

## How to use this file

When a decision is made — in conversation, in planning, or mid-build — add an entry here immediately. Include what was decided, why, and what was ruled out. This stops Claude (and future collaborators) from re-opening settled questions or suggesting approaches already considered and rejected.

---

## Confirmed decisions

### DEC-001 — Data layer: DuckDB
**Decision:** DuckDB is the default and preferred data layer for all querying and processing.
**Rationale:** Performant for analytical queries on local or file-based datasets, well-suited to the kinds of aggregations and historical comparisons this project requires. Avoids the overhead of a server-based database for a data-exploration product.
**Ruled out:** Server-based databases (Postgres, MySQL) — unnecessary infrastructure for this use case at this stage.
**Status:** Confirmed ✅

---

### DEC-002 — Frontend: React JSX
**Decision:** Frontend is built in React JSX.
**Rationale:** Component-based architecture aligns with the modular build requirement. Strong ecosystem for data visualisation libraries.
**Status:** Confirmed ✅

---

### DEC-003 — Architecture: Modular, single-responsibility
**Decision:** All code is modular. Every file has one responsibility. 150 line soft limit per file.
**Rationale:** Makes the codebase maintainable, testable, and extensible as data sources and features grow. Also supports future contributors and Claude sessions picking up work cleanly.
**Status:** Confirmed ✅

---

### DEC-004 — Documentation: Inline JSDoc + README per module + RUNTIME.md
**Decision:** Three-layer documentation — inline JSDoc comments, a README per module, and a project-level RUNTIME.md for operational process.
**Rationale:** Inline comments serve developers during build. Module READMEs serve anyone navigating the codebase. RUNTIME.md serves anyone running or maintaining the live application.
**Status:** Confirmed ✅

---

### DEC-005 — Geographic scope: Australian cities first
**Decision:** Initial scope is Australian cities. Architecture must support expansion without structural changes.
**Rationale:** Scopes the data problem to manageable size while keeping growth path open. Australian government open data is reasonably accessible.
**Status:** Confirmed ✅

---

### DEC-006 — Data accuracy: Source-verified only
**Decision:** No data values are presented without being verified back to the original source. Derived or approximated values are flagged explicitly.
**Rationale:** Core to the product's credibility. Users — including researchers and planners — are trusting the data. Errors erode that trust permanently.
**Status:** Confirmed ✅

---

### DEC-007 — V1 data sources: NSW + VIC only
**Decision:** V1 uses real data from two cities only — Sydney (NSW) and Melbourne (VIC). Queensland, Western Australia, and South Australia are excluded from V1.
**Rationale:** NSW and VIC are the only Australian states providing publicly accessible hourly or sub-hourly traffic count data. QLD, WA, and SA only publish annual average daily traffic (AADT) — no hourly granularity, which doesn't support time-series charting. Starting with real data from the outset rather than synthetic data.
**Ruled out:** Synthetic/sample data approach — user preference to work with real datasets from the start. All five cities at launch — data quality insufficient for QLD/WA/SA.
**Data sources confirmed:** TfNSW hourly permanent counts (SRC-001), VIC SCATS signal volumes (SRC-002), VIC Bluetooth travel time (SRC-007). See `data.md` for full details.
**Status:** Confirmed ✅

---

### DEC-008 — Unified DuckDB schema: four tables
**Decision:** All traffic data normalised into four DuckDB tables: `stations` (unified site reference), `hourly_counts` (core fact table — one row per station per hour), `speed_observations` (VIC Bluetooth speed/travel time), `calendar` (date dimension with holidays and events).
**Rationale:** NSW and VIC use different source systems and granularities (NSW hourly, VIC 15-min). A unified schema allows cross-city queries and charting from a single data model. VIC 15-min data is aggregated to hourly to match NSW. Speed data is separate because only VIC provides it in V1.
**Ruled out:** Keeping raw source schemas — would require city-specific query logic in every chart component, violating the modular architecture principle.
**Status:** Confirmed ✅

---

### DEC-009 — V1 build priority: time-series traffic charting first
**Decision:** First working build focuses on time-series traffic charting (vehicle speed and counts over time), followed by dashboard with metric cards, then historical comparison, then mobility trends.
**Rationale:** Time-series charting is the most data-rich use case and exercises the full pipeline (ingest → DuckDB → API → chart). Gets a working end-to-end system fastest.
**Status:** Confirmed ✅

---

### DEC-010 — Chart library: Recharts
**Decision:** Recharts for V1 chart rendering.
**Rationale:** Already available in the React ecosystem, well-suited to line charts, bar charts, and area charts needed for time-series traffic data. Can reassess for heatmaps or more complex viz later (D3, Plotly as options).
**Status:** Confirmed ✅

---

### DEC-011 — V1 deployment: local dev only
**Decision:** V1 is local development only. No cloud deployment for first build.
**Rationale:** Focus on getting the data pipeline and charting working correctly before introducing deployment complexity. Hosting decision (OPEN-004) deferred to post-V1.
**Status:** Confirmed ✅

---

### DEC-012 — Sydney reliable network filter
**Decision:** Year-on-year and cross-period comparisons for Sydney must use the "reliable network" — a curated set of 26 stations with consistent data coverage from 2019 to 2025 (≥200 weekdays reported per year, plausible volume change between -20% and +25%).
**Rationale:** NSW sensor network is degrading — only 63 of 295 permanent stations reported data in 2026, down from 200+ in 2010–2018. Comparing raw station averages across years produces misleading results (e.g. Military Road Mosman showed a -59% drop that was sensor failure, not a traffic decline). The 26-station reliable set was identified by requiring ≥200 weekday reporting days in both 2019 and 2025, with avg volume ≥400/hr, and change within a plausible range.
**Ruled out:** Using all 295 stations for historical comparisons — produces inaccurate results due to sensor dropout. Using only the most recent year's active stations — loses the ability to compare against pre-COVID baseline.
**Station IDs:** NSW_56841, NSW_58870, NSW_57051, NSW_15828001, NSW_15370001, NSW_57104, NSW_57096, NSW_15648001, NSW_57368, NSW_15154104, NSW_99990010, NSW_15334016, NSW_15252028, NSW_15286008, NSW_15334001, NSW_57140, NSW_15286003, NSW_15828005, NSW_15286009, NSW_15286011, NSW_57268, NSW_57440, NSW_57439, NSW_15252035, NSW_99990003, NSW_15286013
**Status:** Confirmed ✅

---

### DEC-013 — VIC SCATS aggregation: site-level hourly
**Decision:** VIC SCATS 15-minute detector-level data is aggregated to site-level hourly totals during ingestion. Individual detector readings are not stored.
**Rationale:** 61% of raw SCATS rows are zero-volume (inactive detectors). Storing per-detector data would add noise and bloat. Summing across detectors per site gives the total intersection throughput, which is the meaningful metric for traffic monitoring. Aggregating to hourly matches the NSW schema for cross-city queries.
**Status:** Confirmed ✅

---

### DEC-014 — VIC coordinate system: EPSG:3111 (VicGrid94)
**Decision:** VIC Traffic Lights reference coordinates are in EPSG:3111 (VicGrid94), not MGA Zone 55. Reprojection to WGS84 (EPSG:4326) is handled in `ingest_vic_stations.py` using pyproj.
**Rationale:** Confirmed by reprojection testing — MGA55 produced coordinates in Antarctica; VicGrid94 correctly placed all samples in Victorian locations.
**Status:** Confirmed ✅

---

### DEC-015 — Fuel crisis baseline: February 2026 weekday average
**Decision:** For tracking the impact of the March 2026 fuel crisis on traffic, the baseline is February 2026 weekday average per station. Comparisons are also made against the same week from the prior year.
**Rationale:** Feb 2026 is the most recent full month before the crisis onset (~3 March). It had no public holidays that would distort the average (Australia Day is 26 Jan). Using per-station averages normalises for any network changes.
**Status:** Confirmed ✅

---

### DEC-016 — Victoria-only focus for new data sources
**Decision:** All new data sources from this point forward are Victorian only. NSW data already ingested (SCATS counts, 26-station reliable network) is retained, but no new NSW datasets will be added.
**Rationale:** VIC open data is consistently more comprehensive, better documented, and more granular than NSW equivalents. NSW traffic sensor network is degrading (only 26 reliable stations from 295). VIC provides PT patronage, vehicle registrations, cycling data, Bluetooth speed, and TIRTL — NSW has no comparable open datasets for most of these. Focusing on one state deeply produces a better product than covering two states thinly.
**Ruled out:** Continuing to add NSW data sources — quality gap too large, effort better spent on VIC depth.
**Status:** Confirmed ✅

---

## Open decisions

### OPEN-001 — Authentication approach
**Question:** What auth solution to use for the extended access tier?
**Options to assess at build time:** Supabase Auth, Auth0, Clerk, NextAuth, custom JWT
**Dependencies:** Depends on hosting choice and whether a backend is introduced
**Trigger:** Assess when extended access tier scope is defined
**Status:** Open ⬜

---

### OPEN-002 — Payment integration
**Question:** What payment provider and model for extended access?
**Options:** Stripe (most likely), Paddle, Lemon Squeezy
**Dependencies:** Depends on what extended access actually includes (features TBD)
**Trigger:** Assess when monetisation scope is defined
**Note:** Payment module must be fully isolated from day one regardless of when it's built
**Status:** Open ⬜

---

### OPEN-004 — Hosting and deployment
**Question:** Where does this application run?
**Options:** Vercel, Netlify, Fly.io, AWS, self-hosted
**Dependencies:** DuckDB file access patterns, data size, expected traffic
**Trigger:** Post-V1, once local dev version is working
**Status:** Open ⬜

---

### OPEN-005 — Historical data storage
**Question:** How is historical data stored and versioned?
**Considerations:** File-based (Parquet via DuckDB), database snapshots, API with date parameters
**Dependencies:** Partially resolved — raw CSV files kept as extracted directories in project root, DuckDB database is the queryable store. Remaining question is whether to convert to Parquet for long-term archive efficiency.
**Trigger:** When database exceeds ~10 GB or when deployment strategy is decided
**Status:** Partially resolved — working approach in place, optimisation deferred

---

### OPEN-006 — TIRTL dataset viability
**Question:** Does the newly released VIC TIRTL dataset provide historical speed + count data in a usable format?
**Impact:** If yes, it could replace or supplement the Bluetooth polling approach for VIC speed data. Would give us historical speed data without needing to build a polling script.
**Trigger:** Download and inspect the dataset when it becomes available
**Current status:** Announced 9 March 2026 on VIC portal, but no download link found as of 15 March 2026.
**Status:** Open ⬜

---

## Decision log format

When adding a new entry, use this format:

```
### DEC-XXX — Short title
**Decision:** What was decided
**Rationale:** Why
**Ruled out:** What alternatives were considered and rejected
**Status:** Confirmed ✅
```

For open decisions:
```
### OPEN-XXX — Short title
**Question:** What needs to be decided
**Options:** Known candidates
**Dependencies:** What this depends on
**Trigger:** What event or milestone prompts this decision
**Status:** Open ⬜
```

---

*See also: `context.md` (project background), `conventions.md` (code standards), `stage.md` (current phase)*
