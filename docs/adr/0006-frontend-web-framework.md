# ADR-0006: Frontend — React + TypeScript + Vite single-page app

- **Status:** Proposed
- **Plan sections:** §3.1, §16 (M10)

## Context

Today the frontend is three hand-written HTML/JS pages (`setup.html`, `play.html`,
`character_tracker.html`) served by FastAPI's static mount. The planned UI is much larger:

- lobby with a player picker
- session-zero wizard
- a live play view over SSE
- character sheets generated from each ruleset's JSON Schema (including PDF-imported rulesets)
- save/timeline management
- the PDF import wizard
- model settings

The owner chose a **web framework** over vanilla pages (Q11). The app must still run on a single
laptop (Phase 1) and ship as a desktop build without extra installs.

## Decision

1. Use **React + TypeScript**, built with **Vite**, in `storyteller_ai/web/`.
2. Build to static files in `storyteller_ai/frontend/dist/`. These are served by the existing FastAPI
   static mount (still registered last) and bundled into the PyInstaller desktop build.
   **Node.js is a build-time tool only.**
3. Generate API types from FastAPI's OpenAPI schema (`openapi-typescript`). Use TanStack Query for
   data fetching and the browser `EventSource` for SSE.
4. Render character sheets from the ruleset JSON Schema with `@rjsf/core`, so a new or imported
   system needs no new UI code.
5. Keep the legacy pages working until the React pages reach parity (M10), then remove them together
   with the compat routes (T10.7).

## Consequences

- ✅ Schema-driven sheet forms and a mature component ecosystem. Typed API contracts catch drift.
- ✅ Same app for Phase 1 (loopback), Phase 2 (network) and as a companion to the Phase 3 Discord bot.
- ⚠️ Adds a Node.js/npm build toolchain and a supply chain to maintain. Mitigated by a lockfile and
  advisory-DB checks for every new dependency.
- ⚠️ Frontend tests need Vitest and Playwright in CI.

## Alternatives considered

- **Keep vanilla HTML/JS** (previous default): no toolchain, but schema-driven forms, SSE state and
  a multi-step wizard become hard to maintain. Rejected by the owner (Q11).
- **Svelte/SvelteKit:** smaller bundles and simpler syntax, but a smaller JSON-Schema-form ecosystem.
- **Vue + Vite:** a comparable choice. React was picked for ecosystem breadth and contributor familiarity.
- **HTMX + server templates:** little JavaScript, but a poor fit for rich client state (dice panel,
  live turn order, offline-tolerant SSE replay).
