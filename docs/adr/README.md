# Architecture Decision Records

Short records of the key decisions behind [`../STORYTELLER_PLAN.md`](../STORYTELLER_PLAN.md).
Format: Context → Decision → Consequences → Alternatives considered. The owner accepted
ADRs 0001–0006 for task T0.1.

| ADR | Title | Status |
|---|---|---|
| [0001](./0001-persistence-sqlite-event-log.md) | Persistence: SQLite + append-only event log with snapshots | Accepted |
| [0002](./0002-server-authoritative-dice.md) | Server-authoritative, deterministic dice | Accepted |
| [0003](./0003-ruleset-and-setting-pack-format.md) | Ruleset and setting pack format | Accepted |
| [0004](./0004-llm-tool-loop-and-context-strategy.md) | LLM tool loop, SYSTEM_PROTOCOL and context strategy | Accepted |
| [0005](./0005-multiplayer-transport-sse.md) | Multiplayer transport: POST for input, SSE for broadcast | Accepted |
| [0006](./0006-frontend-web-framework.md) | Frontend: React + TypeScript + Vite single-page app | Accepted |
