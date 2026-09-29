# ADR-0003: Ruleset and setting pack format

- **Status:** Proposed
- **Plan sections:** §8, §5.5

## Context

The current engines hard-code World of Darkness concepts (Camarilla/Anarchs/Sabbat, Masquerade,
`clan`, 10-sided pools with 8+ successes). The agent must run any system (D&D 5e SRD, WoD,
PbtA, …) and any setting theme, and validate PC/NPC sheets against the active system.

## Decision

1. Split content into two independent, versioned pack types:
   - **Ruleset pack** (`content/rulesets/<id>/`):
     - `ruleset.yaml`: dice mechanic, attributes/skills/resources, derived formulas, checks,
       turn rules, chargen steps, NPC tiers, prompt digest, licence
     - `sheet.schema.json`: JSON Schema 2020-12
     - optional `migrations/`
     - optional `hooks.py` (trusted packs only)
   - **Setting pack** (`content/settings/<id>/setting.yaml`):
     - compatible rulesets, tone, default lines/veils
     - trackers (clocks/meters), factions, locations, NPC archetypes, name/hook tables, glossary
     - lore document ids, prompt digest
2. Manifests are validated by Pydantic models. Sheets are validated with the `jsonschema` library.
3. Formulas use an **AST-allow-listed evaluator**, never `eval`.
4. A campaign **pins** `ruleset_id@version` and `setting_id@version`. Upgrades are explicit migrations.
5. Today's WoD engines become **data**: a `wod-city-nights` setting pack (factions, districts,
   Masquerade meter) + a `wod-v20-pool` ruleset, running on generic `trackers.py` / `turn_order.py`.
6. Existing genre templates become the `freeform` ruleset, so current sheets migrate losslessly.
7. User-imported packs are **data-only**. Python hooks load only from bundled/trusted directories.

## Consequences

- ✅ New systems/settings need no code in the common case. Sheet UIs can be generated from the schema.
- ✅ Prompt digests keep system knowledge compact and budgeted.
- ⚠️ Exotic mechanics need a `custom` hook (trusted code) or a new interpreter kind.
- ⚠️ Licensing: packs must contain only permitted text (SRD CC-BY-4.0, or self-written summaries).
- New dependency: `jsonschema` (PyYAML is already present).

## Alternatives considered

- **Pure Python plugins per system:** maximum flexibility, but unsafe to import from users and
  harder for non-programmers to author.
- **One combined "game pack":** simpler, but prevents mixing (e.g. PbtA + a cyberpunk setting).
- **Pydantic-only sheet models per ruleset:** requires code per system; JSON Schema is portable and
  drives the frontend forms.
