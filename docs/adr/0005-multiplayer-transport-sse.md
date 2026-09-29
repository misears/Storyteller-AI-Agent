# ADR-0005: Multiplayer transport — POST for input, SSE for broadcast

- **Status:** Proposed
- **Plan sections:** §11, §13.7

## Context

1..N players, in one room or remote, must see the same narration, dice and sheet changes in near
real time, with per-player visibility (whispers, secret rolls). Today the frontend calls
`POST /gm/step` and renders the synchronous response. Only the submitting player sees it.

## Decision

1. Player input stays on plain **`POST /campaigns/{id}/turns`**, with idempotency via
   `client_msg_id`. It returns `202` + `turn_id` (or waits with `?wait=true`).
2. All committed events are pushed via **Server-Sent Events** at `GET /campaigns/{id}/stream`, using a
   `StreamingResponse`. The SSE `id` is the event seq, so clients resume with `Last-Event-ID`.
3. A `Broadcaster` filters each event by **visibility** (public / GM-only / specific players)
   per subscriber, and sends heartbeats every 15 s.
4. Narration tokens stream as transient `message.delta` events. Only the final text is part of the
   permanent log, as a persisted `message.posted` event, which clients receive as the SSE type
   `message.final`.

## Consequences

- ✅ No new dependency. Works through proxies. Trivial reconnect/resume thanks to event seqs.
- ✅ The same event log serves both history (`GET /chat`) and live updates.
- ⚠️ One-way channel; typing indicators and presence need a small `POST` or a later WebSocket.
- ⚠️ In-process broadcaster assumes a single server process (fine for local/LAN; hosted scale-out
  would add Redis pub/sub or Postgres `LISTEN/NOTIFY`).

## Alternatives considered

- **WebSockets:** bidirectional, but more state handling and reconnect logic. It can be added later
  on top of the same `Broadcaster`.
- **Polling `GET /chat?after_seq`:** simplest, and kept as a fallback for clients without SSE.
- **Discord bot as the primary transport:** out of scope for now (Q1). `TurnService` stays
  transport-agnostic.
