# ADR-0004: LLM tool loop, SYSTEM_PROTOCOL and context strategy

- **Status:** Proposed
- **Plan sections:** §4, §9, §10

## Context

These are the problems today:

- `GMLoop.step` sends only the latest user message, so there is no memory of the conversation.
- The only tool is `apply_state_update`, and its result, placed in `response.metadata`, is ignored.
- State is also scraped from prose with a greedy `\{.*\}` regex.
- `SYSTEM_PROTOCOL` is partial and WoD-specific.
- The default Ollama model (`llama2:7b`) has no tool calling.

## Decision

1. **Provider-neutral interface:** `generate(messages, tools) -> LLMResponse(text, tool_calls,
   finish_reason, usage)`. Providers only translate formats. **`TurnService` runs the tool loop**
   (max 6 rounds / 12 calls), validating each call with its JSON Schema and the authority matrix.
2. **Tool set** (§9.1): `roll_dice`, `request_player_roll`, `get_character_sheet`,
   `update_character_sheet`, `create_npc`, `start_scene`, `end_scene`, `set_turn_order`, `next_turn`,
   `adjust_tracker`, `record_fact`, `recall_memory`, `lookup_rules`, `whisper`,
   a narrowed `apply_state_update`, and `request_save`. All state changes happen through tools.
3. **Fallback for non-tool models:** a JSON-schema-constrained *adjudicate* call, then server
   execution, then a *narrate* call. As a last resort, text parsing accepts only a final fenced
   `storyteller-actions` block (or a legacy `json` fence) via `json.JSONDecoder.raw_decode`.
4. **`SYSTEM_PROTOCOL`** is a layered template in this order: identity, hard rules, output protocol,
   ruleset digest, setting + safety, mode, turn procedure, style. The static prefix comes first so it
   can be cached, and the budgeted dynamic context follows.
5. **Context** is assembled by `ContextBuilder` from layers with fractional token budgets:
   - protocol, ruleset, setting
   - campaign arc, session summary
   - scene card with sheet digests + spotlight debt
   - retrieved memory/rules
   - verbatim recent chat
   - input

   Budgets are driven by an `LLMProfile` (context window, capabilities).
6. **Hierarchical summaries** (rolling → scene → session → campaign) and **memory facts** are
   stored as events, generated after commit, and retrieved with SQLite FTS5. Embeddings are optional
   later behind the same interface.

**Models (owner decision, plan §9.6).** The target machine is a laptop with an 8 GB RTX 4070, and
the project must cost nothing. The default is therefore a local 7–8B tool-capable model on Ollama,
chosen by a benchmark, with `num_ctx` set explicitly (8k default). Models are switchable per role
in settings. Free cloud endpoints (OpenAI-compatible) are optional and opt-in.

## Consequences

- ✅ The model sees continuity. State changes are validated and logged. Resume rebuilds the same prompt.
- ✅ Works (more slowly) with small local models, and better with tool-capable ones.
- ⚠️ More LLM calls per turn (tool rounds, summaries): mitigated by caps, batching and caching.
- ⚠️ Golden prompt tests must be updated deliberately when the protocol changes.

## Alternatives considered

- **Send the full transcript every turn:** simple, but overflows quickly and is costly.
- **Agent frameworks (LangChain, LlamaIndex, etc.):** heavy dependencies with little benefit for a
  bounded, domain-specific loop. They also make deterministic testing harder.
- **Vector DB (ChromaDB) from day one** (older design doc): deferred. Keyword/FTS plus structured
  "present entity" retrieval covers early needs.
