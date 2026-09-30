# ADR-0001: Persistence — SQLite + append-only event log with snapshots

- **Status:** Accepted
- **Plan sections:** §5, §6

## Context

Game state currently lives in memory (`services/session_manager.py`) and is lost on restart.
Character sheets are one JSON file, and nothing records chat or dice. The requirements are:

- a complete ordered **chat log**
- a **dice log**
- versioned **character sheets** for PCs and NPCs
- **save / resume at any point** with exact fidelity: scene, turn order, pending actions, context
  and RNG position

The app is local-first. It ships as a desktop build (PyInstaller) and already uses SQLite for the
document store.

## Decision

1. Use **SQLite** (WAL mode) in a new file `data/campaigns.db`, accessed through **SQLAlchemy 2.0**,
   with schema managed by **Alembic** (migrations run at startup, after a backup copy).
2. The **source of truth is an append-only `events` table** (per-campaign `seq`, `branch_id`,
   `type`, versioned JSON payload, actor, `turn_id`).
3. Chat messages, dice rolls, characters, sheets, sheet versions, scenes, summaries and memory facts
   are **projections**. They are written in the same transaction as their events and can be rebuilt
   from events.
4. `GameState` is produced by **pure reducers** over events. The same code runs live and on replay.
5. **Snapshots** (materialised state + context pointers + checksum) are taken every 100 events, at
   scene and session end, and on manual save. **Resume** = latest valid snapshot + replay of later
   events. The LLM is never re-invoked.
6. Turns are serialised by a per-campaign lock. Player input + `turn.started` are committed first.
   Each `dice.rolled` is committed immediately (see ADR-0002). All remaining effects of the turn and
   `turn.completed` are committed in **one transaction**. A started-but-not-completed turn is
   therefore detectable on resume.
7. **Loading an older save forks a new branch.** History is never destroyed.
8. Portable **export** = zip of `events.jsonl` + manifest/checksums + pinned pack copies.
   Projections are rebuilt on import.
9. Payload evolution is handled by **upcasters**. Stored events are never rewritten.

## Consequences

- ✅ Exact resume, full audit trail, free "chat log" and "dice log" views, and time travel/branching.
- ✅ Crash safety: at most the in-flight turn is lost, and it is marked `interrupted` and re-run.
- ✅ Tests can assert replay equivalence (the key M6 acceptance test).
- ⚠️ More moving parts than CRUD. Every state change needs an event type + reducer.
- ⚠️ Single-writer SQLite suits one process. Hosted multi-process deployments would need Postgres
  (same SQLAlchemy code) and DB-level locks.
- New dependencies: `SQLAlchemy`, `alembic` (checked against the advisory DB when added).

## Alternatives considered

- **JSON files per campaign** (extend today's store): simple, but no atomic multi-record
  writes, poor querying of logs, and painful concurrency.
- **Plain CRUD tables + periodic full-state dumps:** simpler, but loses the "why" of changes and
  makes exact resume and audit harder.
- **SQLModel:** convenient, but it couples API models to tables. We want them to evolve
  independently.
- **Postgres from day one** (as in the older design doc): unnecessary for a local-first app, and
  harder to bundle.
