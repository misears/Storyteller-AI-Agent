# Storyteller AI: Section-by-Section Delivery Checklist

**Status:** Planning checklist; unchecked items are not claims about implementation status. Phase 1 is complete only after the Phase 1 exit gate below is verified and signed off. Phase 3 completion is the **end of alpha**, not a production release.

## How to use this checklist

- Work in milestone order: M0 -> M1/M2 -> M3 -> M4 -> M5 -> M6/M7/M9 -> M8 -> M10 -> M11 -> M12 -> M13. Parallel work is fine where dependencies permit. Keep the app runnable and the existing tests green at each milestone.
- The section headings follow the seven sections of the [original system design](../White%20Wolf%20Storyteller%20AI%20%E2%80%94%20Complete%20System%20Design%20Document.txt). Task IDs refer to [the architecture plan](STORYTELLER_PLAN.md#16-milestones--issue-sized-tasks); the [setup task](../SETUP_STORYTELLER_TASK.md) describes the existing skeleton, not the target architecture.
- Where the documents differ, follow the later architecture plan and its ADRs: local FastAPI + SQLite event log, React web UI, Ollama-first model selection, ruleset/setting packs, network after local sign-off, and Discord last. The original PostgreSQL/ChromaDB/Celery/Redis/Docker stack is not a Phase 1 prerequisite. Add infrastructure only if measured needs justify it later.
- Keep runtime PDFs, imported packs, databases, credentials, and copyrighted rule text out of source control and release bundles. A bundled WoD pack contains original mechanics structure, not copied book text. Consult the architecture plan's security and licensing constraints before implementing import/export.
- The architecture plan lists two different tasks as `T5.7`: model switching and the turns API. This checklist calls them `T5.7 (models)` and `T5.7 (turns)` until the source plan is corrected.

## Section 1: Purpose, architecture, and delivery boundaries

### Phase 1: Single computer (M0, M11)

- [ ] **T0.1:** Confirm the remaining owner decisions and accept/amend ADRs 0001-0006. Keep the core ruleset-neutral and the server authoritative for state, dice, visibility, and permissions.
- [ ] **T0.2:** Verify the already-recorded removal of duplicate `*-BlackDragon*` files; do not repeat cleanup without checking the worktree.
- [ ] **T0.3:** Back up existing PDFs and runtime DB outside the repository; untrack runtime data, ignore future files, and ensure an empty data directory boots. Coordinate the owner-run history purge and other clones' re-clone before declaring this complete. Never delete the only copy of a sourcebook.
- [ ] **T0.4, T0.5:** Add Python pytest/ruff CI; restrict default binding to loopback and configure CORS appropriately.
- [ ] Define component boundaries: thin routers and UI, adapter-neutral `TurnService`, provider-neutral LLM client, deterministic rules/reducers, event store, and SSE broadcaster. Avoid embedding mechanics in a route or Discord handler.
- [ ] **T11.1, T11.2, T11.3, T11.4:** Add request limits and leak checks, benchmark long-campaign resume and turn overhead, package a desktop build with packs/migrations/built UI, and write player/operator/pack-author guides.

**Section gate:** A fresh local install starts on `127.0.0.1` without Node at runtime or an external database; secrets and runtime content are absent from tracked files. The Phase 1 sign-off gate appears below.

## Section 2: FastAPI skeleton, services, and user interface

### Phase 1: Backend foundation (M1, M5)

- [ ] **T1.1:** Add SQLAlchemy 2, Alembic, SQLite WAL/foreign keys, startup migrations, and portable data paths; ensure migrations are packaged in the desktop build.
- [ ] **T1.5, T1.6:** Add `CampaignService`, campaign create/read and paged chat endpoints; keep existing `/sessions` and `/gm/step` calls working as temporary facades.
- [ ] **T5.1, T5.2, T5.3:** Normalize OpenAI/Anthropic/Ollama tool calls in the LLM client; centralize schema validation, authority checks, handlers, idempotency, and audit events in a bounded tool registry.
- [ ] **T5.5, T5.7 (turns):** Implement the per-campaign locked turn service and `/campaigns/{id}/turns`; persist player input, resolve tools, validate narration, commit outcomes, then broadcast. Maintain the legacy play page until replacement.
- [ ] **T5.7 (models), T5.8:** Add role-specific model profiles, model list/test/switch controls, safe key handling, a non-tool-model fallback, and an 8 GB VRAM local-model benchmark before choosing a default.

### Phase 1: React delivery (M10)

- [ ] **T10.0:** Scaffold React + TypeScript + Vite, generated API types, lint/component tests, development proxy, and a build served by FastAPI. Keep old HTML pages available during migration.
- [ ] **T10.1, T10.2:** Build lobby/player selection, campaign create/resume, and session-zero wizard.
- [ ] **T10.3:** Build play view with live SSE chat/dice/turn order, two-step player/character selection, GM-only view, roll action, and X-card control.
- [ ] **T10.4, T10.5, T10.6:** Build schema-driven character sheets and history, saves/timelines/export/import, PDF library/import wizard, and settings/model switcher.
- [ ] **T10.7:** Remove legacy pages and compatibility routes only when their React replacements pass equivalent API and end-to-end checks.

**Section gate:** A local user can create, play, pause, resume, and inspect a campaign through the built UI; two local windows receive the right committed events.

## Section 3: Data schema, characters, and durable history

### Phase 1 (M1, M4, M6)

- [ ] **T1.2:** Define validated Pydantic models for campaigns, accounts/players/memberships, PCs/NPCs and sheet versions, sessions/scenes, messages, dice, events, saves, and version-pinned packs. Test serialization and schema export.
- [ ] **T1.3, T1.4:** Implement append-only events, unit of work, per-campaign locking, reducers, and rebuildable projections. Crash injection must leave intake and already-committed rolls visible but no partial turn resolution.
- [ ] **T4.1, T4.2:** Add schema-validated sheet creation/JSON Patch, optimistic version checks, history, and revert-as-a-new-version.
- [ ] **T4.3, T4.4, T4.5:** Migrate legacy JSON sheets to `freeform` without losing exports; support NPC tiers/defaults, derived stats, and ruleset-driven character creation.
- [ ] **T6.1, T6.2:** Snapshot at defined intervals and scene/session ends; verify checksums and resume in a fresh process with identical state, logs, prompt, and next die roll.
- [ ] **T6.3, T6.4, T6.5:** Load older saves as a **new branch**, preserve the original branch, upcast old event/snapshot versions, and safely export/import campaigns without embedding PDFs or secrets.

**Section gate:** An export imported into a fresh database resumes equivalently; a prior save forks without overwriting the old timeline; invalid/concurrent sheet edits return useful errors.

## Section 4: Prompt pack, agent behavior, and campaign generation

### Phase 1 (M5, M7, M9)

- [ ] **T5.4:** Replace the setup document's placeholder `SYSTEM_PROTOCOL` with layered solo/group/assistant instructions, ruleset and setting digests, safety rules, and golden prompt tests. Assistant mode stays functional but is not expanded beyond the plan.
- [ ] **T5.5, T5.6:** Make tools the only route to mechanical changes; parse only explicitly fenced fallback state data, validate allowed paths, support models without tools, and correct fabricated dice claims before publishing narration.
- [ ] **T7.1, T7.2, T7.3, T7.4:** Build token-budgeted context, rolling scene/session/campaign summaries, visibility-aware facts and retrieval, and per-turn usage tracking. Test 400 turns over three sessions without gaps or secret leakage.
- [ ] **T9.1, T9.2:** Generate a sectioned campaign bible with schema validation/repair; let the host review, edit, and regenerate sections as recorded events.
- [ ] **T9.3, T9.4, T9.5:** Guide each player through valid character creation, seed NPCs and opening hooks, begin play, advance world clocks at session boundaries, and show a recap at the next session.
- [ ] Preserve grounded lore: search only the campaign-selected PDFs, cite pages for short rules references, and distinguish retrieved canon from invented scene details.

**Section gate:** A scripted GM turn uses logged tools for rolls and changes; solo, group, and assistant outputs obey their mode and authority rules across a long resumed campaign.

## Section 5: PDF ingestion, rulesets, and setting packs

### Phase 1 (M3, M10)

- [ ] **T3.1, T3.2, T3.3:** Define data-only, versioned pack manifests, schema validation, safe formulas, and `freeform`/`pbta-generic` test packs. Never run imported Python code.
- [ ] **T3.4, T3.5, T3.6, T3.7:** Bundle original `vtm-revised` mechanics structure and `wod-city-nights` setting data; move faction/city/secrecy behavior to generic trackers; scope `lookup_rules` and citations to selected PDFs; expose pack/schema/theme endpoints.
- [ ] **T3.8:** Reuse the existing PDF extraction/OCR and document store. Add page-tagged chunks, classification, resumable per-section structured extraction, confidence scores, and source citations. Use self-authored PDF fixtures in CI.
- [ ] **T3.9, T3.10:** Build a wizard with up to ten targeted questions, editable/skip-as-unverified fields, sample character/formula/test-roll validation, and local versioned pack saving; invalid drafts cannot become active packs.
- [ ] **T3.11, T3.12:** Support supplement extend/diff/version pinning; prove a second, mechanically different system with the freely licensed D&D SRD 5.2 and required attribution in any committed excerpt.
- [ ] **T3.13, T3.14:** Add a self-written `demon-the-fallen` structure, later enriched from the owner's PDF; support multiple rulesets in one campaign, per-character mechanics, same-family opposed rolls and a confirmed cross-family outcome mapping.
- [ ] **T10.6:** Make upload, progress, citations, corrections, and pack selection usable from the web UI.

**Section gate:** The owner can select PDFs, answer a small number of questions, inspect citations, save a valid playable pack, and extend it without silently changing existing campaigns. PDFs remain local and unbundled.

## Section 6: State engine, dice, multiplayer, and safety

### Phase 1: Local shared-table play (M2, M8, M9)

- [ ] **T2.1, T2.2, T2.3:** Implement bounded dice-expression parsing, seeded counter-based RNG and proof verification, plus ruleset-configurable sum/pool/band/roll-under interpreters; preserve the old dice API through a shim during migration.
- [ ] **T2.4:** Persist each roll as an event and chat-linked dice record. Never accept a client-provided result; hide secret rolls until authorized to reveal them.
- [ ] **T3.7, T9.5:** Drive tension/doom, factions, scene clocks, NPC memory, and world ticks through generic trackers and events rather than WoD-only hard-coded state.
- [ ] **T8.1:** Model accounts, players, memberships, character ownership, and host/player authority now; Phase 1 uses a local pick/add player selector, not password login. Allow several characters per player.
- [ ] **T8.2:** Broadcast committed events over SSE with per-view visibility and `Last-Event-ID` replay; test separate local player and GM windows.
- [ ] **T8.3, T8.4, T8.5:** Add freeform/round-robin/initiative policies, up to ten players, spotlight balancing, join/leave and absent-PC policies, and mode switching; test concurrent submissions without lost or duplicate actions.
- [ ] Implement lines/veils and an X-card pause in the shared play flow; test that hidden notes and private events do not appear in player-facing APIs or streams.

**Section gate:** Ten local players can take concurrent turns deterministically, while visibility and authority tests cover every role; an eleventh join is refused.

## Phase 1 exit gate: local release (M11)

- [ ] Python tests and ruff pass, pack fixtures validate, and targeted migration, replay, tool-loop, PDF-import, and multi-window UI tests pass. Run optional real-model smoke on the owner's machine; keep CI deterministic with a scripted provider.
- [ ] **T11.2:** Measure a 1,000-turn resume under 1 second and non-LLM turn overhead under 100 ms (benchmarks are recorded even if CI treats them as non-blocking).
- [ ] **T11.3:** Smoke-test the desktop package, including migrations, content packs, and React assets, on a machine without Node at runtime.
- [ ] **T11.5:** Play one complete scripted session and one real multi-session campaign on a single computer; verify saves, branch load, sheets, PDF lookup/import, model switching, safety controls, and a second window.
- [ ] Record owner acceptance that Phase 1 **works as desired**. Only then mark Phase 1 **complete** and open Phase 2 work.

## Phase 2: Network play (M12)

- [ ] **T12.1:** Add opt-in LAN binding, explicit interface choice, startup warning, and CORS allow-list; default local mode remains loopback-only.
- [ ] **T12.2:** Require password-backed account sessions in network mode, throttled login/reset, join codes, and scoped hashed API/service tokens. Keep local identity behavior unchanged.
- [ ] **T12.3:** Bind each remote browser to its own player and characters; keep host privileges separate. Re-run the full authority/visibility matrix against authenticated actors.
- [ ] **T12.4, T12.5:** Rate-limit turns/dice per token, cap SSE connections, track reconnect/presence and absent-player policy; load-test ten clients and interruptions.
- [ ] **T12.6 (optional):** Document TLS/reverse proxy hosting and a database upgrade only if multi-process deployment is actually needed.

**Phase 2 exit:** Ten devices can join, play, reconnect, and see only authorized information; no unauthenticated network request can mutate a campaign. Keep the local single-computer mode working.

## Section 7 / Phase 3: Discord bot (M13)

- [ ] **T13.1, T13.2:** Start a separate outbound bot process with scoped server credentials; support ping and explicit channel-to-campaign binding. Keep all game logic in the existing API/services.
- [ ] **T13.3:** Link Discord identities to accounts and campaign players/characters; unlinked users receive private setup guidance and cannot act as someone else.
- [ ] **T13.4:** Translate `/act` or permitted channel messages into turn API calls and committed SSE narration into Discord posts; handle message limits and streaming edits without duplicating turns.
- [ ] **T13.5:** Add roll, sheet, save, recap, and turn commands backed by the same API/event log as the web UI.
- [ ] **T13.6:** Route whispers and GM-only data only to authorized private destinations; test that public channels never receive secret events or long rulebook passages.
- [ ] **T13.7:** Persist the last delivered event sequence and recover from bot restarts/reconnects with no duplicate or missing public posts. Test against a fake Discord gateway plus a live smoke test in a private test server.

**End-of-alpha gate:** Complete Phase 1 and Phase 2 gates still pass; a linked Discord group can run and resume a campaign through the bot and web UI against one shared event history, including rolls, saves, visibility, and restart recovery. Document remaining beta/production gaps separately rather than treating alpha completion as general availability.
