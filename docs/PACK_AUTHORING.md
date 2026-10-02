# Ruleset Pack Authoring Guide

## Layout

Bundled packs live under `storyteller_ai/backend/content`; owner-created packs live under the local
data directory. A ruleset directory contains:

```text
ruleset.yaml
sheet.schema.json
```

The manifest declares an id, semantic version, license, dice mechanic, checks, turn rules, chargen
steps, NPC tiers, and a short prompt digest. `sheet.schema.json` must be a valid JSON Schema 2020-12
document. Setting packs use `setting.yaml` and declare compatible ruleset IDs.

## Validation

The registry validates manifests with Pydantic and schemas with `jsonschema`. Invalid packs remain
visible as diagnostics but are never loaded. Discovery is bundled-first, followed by local packs.

Imported packs are data-only. Do not add Python hooks or copy rulebook prose into the repository.
Selected source documents remain local and are referenced through provenance and page-cited lookup.

## Safe formulas

Derived formulas support arithmetic, comparisons, `min`, `max`, `floor`, `ceil`, and explicit helpers.
They must not use `eval`, imports, attributes, lambdas, or arbitrary calls.