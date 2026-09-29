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
   Masquerade meter) + a `vtm-revised` ruleset, running on generic `trackers.py` / `turn_order.py`.
6. Existing genre templates become the `freeform` ruleset, so current sheets migrate losslessly.
7. User-imported packs are **data-only**. Python hooks load only from bundled/trusted directories.
8. **Packs are normally created from the owner's rulebook PDFs** via the import wizard (plan §8.6):
   - LLM extraction per section, with confidence and page citations
   - a few pop-up verification questions
   - validation (test rolls, a sample character)
   - saving to local `data/packs/` with provenance

   World of Darkness (VtM Revised) is the primary system and the importer's reference. Imported
   packs are data-only and local, and are never committed.
9. **Several rulesets per campaign (cross-genre, plan §8.7).** A campaign has a primary ruleset
   plus `extra_rulesets`, and each character's sheet names its own ruleset. Rulesets sharing a
   `family` (VtM and *Demon: The Fallen*: `storyteller-classic`) compare results directly. Other
   families meet through each pack's `outcome_ladder`. The free D&D SRD 5.2 (CC BY 4.0) is the
   importer's non-WoD proof of concept.

## Consequences

- ✅ New systems/settings need no code in the common case. Sheet UIs can be generated from the schema.
- ✅ Prompt digests keep system knowledge compact and budgeted.
- ⚠️ Exotic mechanics need a `custom` hook (trusted code) or a new interpreter kind.
- ⚠️ Licensing: bundled packs contain only self-written structure. PDF-derived packs stay local.
- ⚠️ Extraction quality depends on the PDF and the LLM, so human verification (pop-ups) is required.
- New dependency: `jsonschema` (PyYAML is already present).

## Alternatives considered

- **Pure Python plugins per system:** maximum flexibility, but unsafe to import from users and
  harder for non-programmers to author.
- **One combined "game pack":** simpler, but prevents mixing (e.g. PbtA + a cyberpunk setting).
- **Pydantic-only sheet models per ruleset:** requires code per system; JSON Schema is portable and
  drives the frontend forms.
