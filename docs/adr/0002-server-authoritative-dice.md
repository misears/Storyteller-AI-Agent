# ADR-0002: Server-authoritative, deterministic dice

- **Status:** Proposed
- **Plan sections:** §7, §9.1

## Context

LLMs readily "narrate" dice results they never rolled. `engines/dice_pool.py` uses the global
`random` module with a hard-coded WoD rule. Every roll must be logged with roller, expression,
individual dice, modifiers, result, interpretation, reason and a link to the chat. Resume must
continue the dice stream correctly.

## Decision

1. **Only the server rolls.** The dice engine is reached through the `roll_dice` tool (LLM), the
   player roll endpoint, or engine-internal rolls (initiative, chargen). Clients and the LLM never
   supply results.
2. A small hand-written **expression parser** (`NdX`, keep/drop, explode, reroll, success
   thresholds, `{refs}`) with hard limits, and **mechanic interpreters** selected by the ruleset
   (`sum_vs_target`, `pool_successes`, `bands`, `roll_under`, `custom`).
3. **Counter-based RNG** (`hmac-sha256-ctr-v1`):
   - key = HMAC(campaign secret seed, branch_id)
   - draw n = HMAC(key, counter)
   - unbiased mapping via rejection sampling

   Each `DiceRoll` stores an `RngProof` (counter range). `GameState.rng_counter` is restored on
   resume.
4. Each roll is **committed immediately** as a `dice.rolled` event plus a system chat message,
   before the narration is generated. On a retry of an interrupted turn, rolls already made
   are injected as established results, so there is no re-roll fishing.
5. The GM narration message lists the `dice_roll_ids` it relies on. A post-validator flags
   narration that mentions roll results with no matching roll.
6. Rolls may be **secret** (GM-only). They are always logged, and hidden from players per table config.

## Consequences

- ✅ Trustworthy, auditable dice. Deterministic tests. Identical continuation after resume.
- ✅ Per-branch keys mean loading an old save does not reveal future rolls (anti save-scum).
- ⚠️ A small amount of parser/interpreter code to own and test (property tests).
- ⚠️ Seed secrecy matters. It is stored server-side and only exported on explicit request.

## Alternatives considered

- **`random.Random(seed)` with pickled state:** works, but the state is opaque, Python-version
  coupled, and hard to audit per roll.
- **Third-party dice libraries** (e.g. `d20`, `dice`): good parsers, but they don't cover pools with
  botches/bands in one model, and we would still need our own RNG and interpretation layer.
  One may be reconsidered for the parser only.
- **Let the LLM roll ("pick a number"):** rejected; neither fair nor auditable.
