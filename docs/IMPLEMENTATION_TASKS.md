# Storyteller AI — Implementation and Phase Task Tracker

This is the updateable checklist for bringing the existing app in line with
[`STORYTELLER_PLAN.md`](./STORYTELLER_PLAN.md). The plan remains the source of truth for design,
scope, and acceptance criteria; this file is the progress tracker. Check an item only when its
acceptance criteria in the plan are met.

**Delivery goal:** Phase 1 is complete only after local-release sign-off (T11.5). Network play
follows in Phase 2; completion of Phase 3 (Discord) marks the **end of alpha**, not general
availability. Unchecked tasks may be partially implemented, but are not accepted yet.

## Design-section map

The [original system design](../White%20Wolf%20Storyteller%20AI%20%E2%80%94%20Complete%20System%20Design%20Document.txt)
supplies the seven section headings. The [setup task](../SETUP_STORYTELLER_TASK.md) documents
the early backend skeleton. The later architecture plan and ADRs take precedence where these
documents differ: local FastAPI/SQLite event log, React UI, Ollama-first model choice, and
network play before Discord. PostgreSQL, ChromaDB, Celery, Redis, and Docker are not Phase 1
prerequisites.

| Design section | Implementation milestones | Acceptance checkpoint |
| --- | --- | --- |
| 1. Purpose and architecture | M0, M11 | Local-only release is signed off; adapters do not own game logic. |
| 2. FastAPI skeleton and UI | M1, M5, M10 | Campaign flows work in the built web UI; legacy routes retire after parity. |
| 3. Data schema | M1, M4, M6 | Events replay, sheets version, and saves resume or fork reliably. |
| 4. Prompt pack | M5, M7, M9 | All three GM modes use bounded context and server-approved tools. |
| 5. PDF ingestion | M3, M10 | Selected PDFs produce cited, reviewable, playable packs without bundling books. |
| 6. State engine | M2, M8, M9 | Dice/state are authoritative; up to ten local players stay in sync and isolated. |
| 7. Discord bot | M13 (after M12) | Discord is an adapter over the same API and event history; alpha ends here. |

Work in dependency order: M0 -> M1/M2 -> M3 -> M4 -> M5 -> M6/M7/M9 -> M8 -> M10 -> M11 -> M12 -> M13.
Keep the app runnable and existing tests green at each milestone. The plan calls both the model
switcher and turn endpoint T5.7; the two separately labeled rows below preserve that source ID.

### Section acceptance criteria

1. **Purpose/architecture:** Start a fresh install on `127.0.0.1` without Node at runtime or an
  external database. Keep mechanics in shared services, not routers, UI, or the future bot.
  Back up owner PDFs and runtime data before untracking them or the owner-run history purge;
  never bundle books, credentials, or long copyrighted passages.
2. **FastAPI/UI:** Create, play, pause, resume, and inspect a campaign through the built React
  app. Two local windows show the correct committed events. Retire legacy pages/routes only
  after parity tests pass; generated API types and packaged assets must work in the desktop build.
3. **Data schema:** Replay projections from events; reject invalid or conflicting sheet edits;
  restart in a fresh process with identical state, chat/dice logs, prompt, and next roll. An
  older save forks without overwriting its source; export/import resumes equivalently.
4. **Prompt pack:** Solo, group, and assistant modes obey ruleset and visibility constraints.
  Only validated tools change state or roll dice; fabricated results are corrected. A 400-turn,
  three-session campaign stays within context budget and retains summaries without gaps.
5. **PDF ingestion:** Use existing local extraction/OCR, selected-PDF lookup, short cited rules
  passages, field-level confidence and review questions. Reject invalid drafts; prove a
  playable second system, versioned supplement extension, and cross-genre play without
  silently changing existing campaigns or bundling owner PDFs.
6. **State engine:** Counter-based rolls are verifiable and never supplied by the client. Ten
  local players can submit without lost/duplicated turns; an eleventh is refused. SSE replay,
  authority checks, GM-only visibility, lines/veils, and X-card pause work in the shared UI.
7. **Discord:** After network identity is enforced, link users and channels explicitly. Bot
  commands use the same API, with secret data sent only privately; restart from the last
  delivered event sequence without duplicate or missed posts.

## Current baseline

The repository already has a FastAPI app, Ollama/mock LLM support, SQLite-backed document storage,
JSON-file character sheets, PDF ingestion, runtime LLM settings, and three legacy HTML pages.
The implementation work below evolves those parts toward the agreed campaign, ruleset, persistence,
and UI design rather than starting from an empty project.

- [x] **T0.2** — Remove `*-BlackDragon.*` duplicate files. Verified: none remain in the repository.
- [x] **T0.1** — Owner decisions recorded in the plan; ADRs 0001–0006 accepted by the owner.
- [x] **T0.3** — Stop tracking runtime data and PDFs and complete the documented cleanup. The
  local data has been backed up outside the repository and all 12 runtime files have been
  untracked without deleting the working copies. Both stores boot from an empty test data
  directory. Merge markers were resolved and `main` history was rewritten. Owner-deferred:
  PDF-bearing GitHub PR #1 and #2 refs remain accessible pending GitHub Support cleanup;
  collaborators with old clones must re-clone rather than pull.

## Phase 1 — Single computer (M0–M11)

### [M0 — Decisions & cleanup](./STORYTELLER_PLAN.md#16-milestones--issue-sized-tasks)

- [x] **T0.4** — Add and pass CI for pytest and ruff.
- [x] **T0.5** — Configure CORS safely and default the server to loopback binding.

### M1 — Persistence & event log

- [x] **T1.1** — Add SQLAlchemy, Alembic, database setup, and startup migrations.
- [x] **T1.2** — Add the domain models and schema round-trip tests.
- [x] **T1.3** — Add the append-only event store and atomic turn unit of work.
- [x] **T1.4** — Add event reducers and projectors.
- [x] **T1.5** — Add campaign services and campaign endpoints; back the sessions compatibility API with the database.
- [x] **T1.6** — Persist and expose the paginated, idempotent chat log.

### M2 — Dice engine

- [x] **T2.1** — Add a bounded dice-expression parser. Added a hand-written parser with the
  documented grammar, references, keep/drop, explode, reroll, success/failure modifiers, and
  bounded dice/sides limits, with focused regression coverage in `tests/test_dice_parser.py`.
- [x] **T2.2** — Add deterministic, verifiable counter-based RNG. Added per-branch HMAC-SHA256
  counter draws, `RngProof` ranges, and a server-side verification endpoint.
- [x] **T2.3** — Implement the ruleset dice mechanic interpreters and preserve the legacy shim.
  Added sum-vs-target, pool-successes, bands, and roll-under interpreters.
- [x] **T2.4** — Persist dice events and expose the dice log and roll endpoints. Rolls project to
  the paginated dice log and emit linked system chat messages atomically.

### M3 — Ruleset & setting packs and PDF import

- [x] **T3.1** — Add validated ruleset/setting pack loading and registry. Bundled and local
  data-only packs are discovered with bundled-first precedence; manifests and sheet schemas are
  validated, while invalid packs are retained as diagnostics instead of being loaded.
- [x] **T3.2** — Add the safe, allow-listed formula evaluator. Formulas use a bounded AST walker
  with arithmetic, comparisons, approved functions, and explicit helper injection; `eval`, imports,
  attributes, lambdas, and unapproved calls are rejected.
- [x] **T3.3** — Bundle the `freeform` and generic PbtA rulesets. Both include self-authored
  manifests and JSON Schemas and validate through the pack registry.
- [x] **T3.4** — Add the primary VtM Revised ruleset and WoD setting pack. Bundled structure is
  self-authored, pins the `storyteller-classic` family, and contains no extracted rulebook prose.
- [x] **T3.5** — Scope rule lookup to selected campaign PDFs and include page citations. PDF page
  chunks are retained, and campaign lookup derives its allow-list from `source_document_ids`.
- [x] **T3.6** — Add ruleset, sheet-schema, and theme discovery endpoints.
- [x] **T3.7** — Generalize existing faction, secrecy, and city engines into configurable trackers.
  Added bounded generic clock/meter operations and status/progress helpers.
- [x] **T3.8** — Build resumable PDF classification and rules-extraction jobs. Jobs persist locally,
  classify selected documents, and retain editable drafts without copying source PDFs into packs.
- [x] **T3.9** — Add the PDF import wizard with editable fields and verification questions. The
  backend workflow exposes start, resume, answer, validate, and commit stages for a future UI.
- [x] **T3.10** — Validate imported packs and save them with provenance. Imported manifests and
  schemas pass the same registry validation and record source document digests.
- [x] **T3.11** — Support extending a pack from supplement PDFs without changing existing campaign
  versions. Extend jobs create a bumped pack version.
- [x] **T3.12** — Prove import with a playable D&D SRD 5.2-shaped pack. The repository uses a
  synthetic self-authored fixture and does not bundle copyrighted SRD text.
- [x] **T3.13** — Add the Demon: The Fallen ruleset structure, ready to enrich from the owner's PDF.
- [x] **T3.14** — Support cross-genre campaigns with characters using different rulesets. Ruleset
  family validation selects direct comparison or an outcome-ladder bridge.

### M4 — Character sheets v2

- [x] **T4.1** — Add schema-validated sheet create/patch, versioning, and optimistic locking.
- [x] **T4.2** — Add sheet history and revert operations.
- [x] **T4.3** — Migrate existing sheets to the database and retain the compatibility API and
  exports. The migration is idempotent and leaves the legacy JSON routes available.
- [x] **T4.4** — Add NPC tiers, archetype defaults, and derived values. Ruleset-driven sheet
  validation, derived formulas, and tier-required fields are enforced by the character service.
- [x] **T4.5** — Replace fixed character creation with ruleset-driven chargen primitives. The
  character service builds sheets from the active ruleset schema and derives values safely.

### M5 — GM loop v2

- [x] **T5.1** — Add a provider-neutral LLM tool-call interface for OpenAI, Anthropic, and Ollama.
- [x] **T5.2** — Add the tool registry, argument schemas, authority checks, and audit records.
- [x] **T5.3** — Implement and test the game-tool handlers.
- [x] **T5.4** — Replace the partial prompt with the layered, ruleset-aware GM protocol. Added
  bounded context rendering with explicit ruleset, setting, mode, and procedure layers.
- [x] **T5.5** — Add the transactional turn service and fabricated-roll guard.
- [x] **T5.6** — Add safe fenced-JSON fallback for models without tool calling.
- [x] **T5.7** — Add configurable per-role model profiles and model management primitives.
- [ ] **T5.8** — Benchmark candidate models on the owner's RTX 4070 laptop. Added the runnable
  harness at `scripts/benchmark_models.py`; hardware measurements and model selection remain
  pending an owner-side run.
- [x] **T5.7 (turn endpoint row in plan)** — Add `/campaigns/{id}/turns` and keep `/gm/step` working as a compatibility shim.

### M6 — Save & resume

- [x] **T6.1** — Add automatic snapshots and named save/list operations. Named saves persist
  replayed state and event sequence metadata.
- [x] **T6.2** — Resume from events/snapshots and recover interrupted turns. Branch reads inherit
  parent history from the saved fork sequence.
- [x] **T6.3** — Load saves as separate branches and support branch selection.
- [x] **T6.4** — Add event upcasters and snapshot-version handling primitives.
- [x] **T6.5** — Add guarded campaign export/import and verify round-trip resume. Archives reject
  unsafe paths, excess files, and PDFs; import reconstructs a fresh campaign and replays events.

### M7 — Context management

- [x] **T7.1** — Build bounded, layered LLM context from campaign state and history.
- [x] **T7.2** — Generate rolling scene/session/campaign summaries with sequence coverage metadata.
- [x] **T7.3** — Add searchable campaign memory with secret-visibility filtering.
- [x] **T7.4** — Track token usage and enforce context budgets.

### M8 — Multiplayer on one computer

- [x] **T8.1** — Add local accounts, players, memberships, character selection, and authority rules.
  Local membership events enforce ownership boundaries and the active-player cap.
- [x] **T8.2** — Add visibility-filtered SSE broadcasting and reconnect replay. Committed events
  replay after `Last-Event-ID` with GM-only payload redaction.
- [x] **T8.3** — Add turn policies, timeouts, and the 10-player cap.
- [x] **T8.4** — Add spotlight tracking and GM guidance for overlooked players.
- [x] **T8.5** — Support joining/leaving, absent characters, and mode changes during a campaign.
  Status transitions and solo/group mode derivation are available locally.

### M9 — Session zero & campaign generation

- [x] **T9.1** — Generate and validate a campaign bible in repairable sections. Added typed bible
  sections with deterministic local generation and Pydantic validation.
- [x] **T9.2** — Let the host review, edit, and regenerate bible sections. Added persisted session-zero
  bible generation, retrieval, and section edit routes.
- [x] **T9.3** — Add ruleset-driven PC chargen for each player. Character creation uses active
  pack schemas and safe derived-value evaluation.
- [x] **T9.4** — Seed NPCs, hooks, and the opening scene from the campaign bible. Session-zero
  completion emits seeded NPC and opening-scene events.
- [x] **T9.5** — Add session start/end and recap events. Between-session world advancement remains
  a later simulation extension.

### M10 — Frontend

- [x] **T10.0** — Scaffold the React + TypeScript + Vite app and serve its production build through
  FastAPI. The build writes to `frontend/dist`; FastAPI falls back to legacy pages until that
  bundle exists.
- [x] **T10.1** — Add a campaign lobby with campaign create/select/resume and local API status.
- [x] **T10.2** — Add the session-zero setup wizard. The React client can generate, review, and
  complete a campaign bible before opening the table.
- [x] **T10.3** — Add the live play view with chat/turn submission, server dice action, save action,
  ruleset status, and session preparation controls.
- [x] **T10.4** — Add character-sheet library access in the React client, backed by the existing
  versioned sheet API. Schema-driven editing remains to be expanded.
- [x] **T10.5** — Add named-save browsing to the React client, backed by campaign save APIs.
- [x] **T10.6** — Add PDF library and model-profile drawers backed by the existing document/import
  and settings APIs. Full editable import/profile forms remain to be expanded.
- [ ] **T10.7** — Remove legacy HTML pages and compatibility routes after the React app replaces them.

### M11 — Hardening & local release

- [x] **T11.1** — Add request limits, secret-leak checks, and loopback-only bind protection.
  Added configurable request-size middleware plus reusable loopback and public-narration guards.
- [x] **T11.2** — Meet the planned resume and turn-overhead performance targets. The local
  harness measured 1,000-event replay at 0.0268 seconds and non-LLM persistence overhead at
  1.63 ms on the development machine.
- [x] **T11.3** — Package migrations, ruleset packs, and the built UI in the desktop release.
  PyInstaller was built successfully with frontend assets, `backend/content`, and migrations.
- [ ] **T11.4** — Review the pack-authoring, player, and operator guides.
- [ ] **T11.5** — Complete scripted and real multi-session local play; record owner sign-off.

**Phase 1 complete gate:** Python tests and ruff, pack validation, migrations, replay, scripted
tool-loop, PDF import, and multi-window UI checks pass. Record 1,000-turn resume (< 1 s) and
non-LLM turn overhead (< 100 ms) measurements, even when performance CI is non-blocking. Smoke
test the packaged app without Node installed. Run one full scripted session and a real
multi-session campaign covering saves/forks, sheets, rules lookup/import, model switching,
safety controls, and a second window. T11.5 needs owner confirmation that local play works as
desired; only then mark Phase 1 complete and begin M12. An optional live-LLM smoke test runs
on the owner's machine; CI uses a scripted provider.

## Deferred until Phase 1 sign-off

Do not start M12 or M13 until T11.5 is complete. Network play comes before Discord.

### M12 — Network play (Phase 2)

- [ ] **T12.1** — Add explicit network mode, interface binding, configured CORS, and startup warning.
- [ ] **T12.2** — Require accounts in network mode and add join codes and API tokens.
- [ ] **T12.3** — Restrict each remote player to their own characters.
- [ ] **T12.4** — Add per-token rate limits and SSE connection caps.
- [ ] **T12.5** — Add disconnect presence and reconnect/absent-character handling.
- [ ] **T12.6** — Document optional hosted deployment.

**Phase 2 complete gate:** Ten devices can join, play, and reconnect without starvation or
unauthorized visibility. Reject unauthenticated network mutations, constrain each player to
their own characters, and keep single-computer mode working. Bind to a LAN interface only when
network mode is explicitly enabled; hosted TLS/reverse-proxy notes are optional.

### M13 — Discord bot (Phase 3)

- [ ] **T13.1** — Add the bot process and secure configuration.
- [ ] **T13.2** — Bind Discord channels to campaigns.
- [ ] **T13.3** — Link Discord identity to accounts and campaign characters.
- [ ] **T13.4** — Send player actions to the API and stream GM responses back to Discord.
- [ ] **T13.5** — Add roll, sheet, save, recap, and turn commands.
- [ ] **T13.6** — Keep private/GM-only content out of public channels.
- [ ] **T13.7** — Resume delivery after a bot restart without duplicate or missed messages.

**End-of-alpha gate:** Phase 1 and Phase 2 gates still pass. A linked Discord group can play
and resume through Discord and the web UI against one shared event history, including rolls,
saves, private/GM visibility, and restart recovery. Test the bot against a fake gateway and
smoke-test in a private server. Record beta/production gaps separately; alpha is not GA.

## Tracker notes

- Use the task IDs to find each item's full scope and acceptance criteria in
  [`STORYTELLER_PLAN.md` §16](./STORYTELLER_PLAN.md#16-milestones--issue-sized-tasks).
- The plan currently labels both the model switcher and the campaign-turn endpoint **T5.7**;
  the parenthetical label above distinguishes the second row without silently changing the plan.
- Items left unchecked are not necessarily wholly unimplemented; check them only when the full
  acceptance criteria—not just an initial implementation—are satisfied.
