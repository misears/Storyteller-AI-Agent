# ADR-0005: Multiplayer transport — POST for input, SSE for broadcast

- **Status:** Accepted
- **Plan sections:** §11, §13.7

## Context

1..N players, in one room or remote, must see the same narration, dice and sheet changes in near
real time, with per-player visibility (whispers, secret rolls). Today the frontend calls
`POST /gm/step` and renders the synchronous response. Only the submitting player sees it.

Owner decision (Q1): run on a **single computer** first (Phase 1), then extend to **network play**
(Phase 2) and a **Discord bot** (Phase 3).

## Decision

1. Player input stays on plain **`POST /campaigns/{id}/turns`**, with idempotency via
   `client_msg_id`. It returns `202` + `turn_id` (or waits with `?wait=true`).
2. All committed events are pushed via **Server-Sent Events** at `GET /campaigns/{id}/stream`, using a
   `StreamingResponse`. The SSE `id` is the event seq, so clients resume with `Last-Event-ID`.
3. The stream reads committed events after the subscriber's cursor, filters each event by
   **visibility** (public / GM-only / specific players), and sends heartbeats every 15 s. The
   current local implementation polls the SQLite event log while the connection remains open;
   an in-process broadcaster can replace polling if subscriber counts make it necessary.
4. The same stream serves every phase:
   - **Phase 1:** multiple windows on one machine, e.g. a player view and a GM view.
   - **Phase 2:** each player's device.
   - **Phase 3:** the Discord bot adapter, which consumes it like any client and posts to Discord.
5. Narration tokens stream as transient `message.delta` events. Only the final text is part of the
   permanent log, as a persisted `message.posted` event, which clients receive as the SSE type
   `message.final`.

## Consequences

- ✅ No new dependency. Works through proxies. Trivial reconnect/resume thanks to event seqs.
- ✅ The same event log serves both history (`GET /chat`) and live updates.
- ⚠️ One-way channel; typing indicators and presence need a small `POST` or a later WebSocket.
- ⚠️ Persistent streams poll the local SQLite event log. If subscriber counts grow, replace the
   polling loop with an in-process broadcaster; hosted scale-out would add Redis pub/sub or Postgres
   `LISTEN/NOTIFY`.

## Alternatives considered

- **WebSockets:** bidirectional, but more state handling and reconnect logic. It can be added later
  on top of the same `Broadcaster`.
- **Polling `GET /chat?after_seq`:** simplest, and kept as a fallback for clients without SSE.
- **Discord bot as the primary transport:** rejected as the *primary* transport. It is planned as a
  Phase 3 adapter (M13) over this same API + SSE, so `TurnService` stays transport-agnostic.
