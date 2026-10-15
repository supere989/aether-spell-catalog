# CoA ability logic catalog — initial extraction

> **Repository contents:** this repository tracks source, tests, the Combat Lab UI and hand-written docs only. The catalog, captures, evidence files, generated listings and extracted client assets named below are produced by the scripts here from a local CoA client and world database, and are not committed (see `.gitignore`).

Created in the side conversation on 2026-10-14. This directory is independent of the game checkout. No server code, game data, active test, or production configuration was changed.

## Contents

- `catalog.sqlite`: searchable corpus and separate evidence layers.
- `abilities.jsonl`: 8,370 detailed spell records suitable for programmatic review and planner input preparation.
- `sql-capture.json`: read-only SQL evidence for the declared class-spell set and its rank chains.
- `summary.json`: exact counts, integrity results, missing references, and provenance warnings.
- `query.py`: read-only lookup; no dependencies beyond Python.
- `build_catalog.py`: extraction using the existing CoA DBC parser. Refuses to overwrite its output.

The index covers all 209,544 records in the selected Spell.dbc. The detailed cohort spans all 21 CoA classes (12–32): declared acquisitions across levels, advancement/talent candidates, SQL ranks, and recursively referenced spell effects. It is not a claim that every indexed spell is player-learnable or executable. Advancement candidates retain their prerequisite, level, class-type, tab, and essence-cost fields; those conditions have not been fully evaluated.

## What each detailed entry contains

- Raw resource type, flat/percentage/per-level cost and ongoing drain.
- Cast-time, duration, range, global-cooldown and cooldown references/values.
- Equipment, stance, aura, target, reagent and attribute restrictions.
- Three effect slots with decoded effect/aura labels, amounts, scaling fields and linked spells.
- Name and authored description, retaining formulas rather than inventing evaluated damage.
- Explicit character/rotation inputs needed to determine sustainability.
- Separate database evidence, static code mentions, and scenario-definition links.

Reference tables resolve timing/range/duration IDs and retain charges, custom attributes, specialization and advancement metadata. Unknown custom layout bytes and C++ semantics are not inferred. Effect coefficients and base points are raw values: do not directly treat them as final damage or effective AP/SP scaling.

## Use

From the host:

```sh
python3 /home/raymondj/projects/aether-spell-catalog/query.py --class-id 12 --limit 20
python3 /home/raymondj/projects/aether-spell-catalog/query.py --search 'Fire Blast'
python3 /home/raymondj/projects/aether-spell-catalog/query.py --id 801576
```

From the existing devbox, the directory is `/work/aether-spell-catalog`.

Useful SQLite tables: `spell_index`, `abilities`, `acquisitions`, `reference_records`, `spell_links`, `sql_rows`, `source_mentions`, `scenario_links`, `provenance`. Detailed JSON is in `abilities.logic_json`; this can be read using SQLite JSON functions or exported JSONL.

## Evidence and limits

DBC source: `/tmp/coa-restart-validation/data/dbc` inside `coa-resume`. Per-table hashes and schema provenance are retained. Spell.dbc differs from its extraction manifest; its current hash is recorded, but its original archive attribution is stale.

SQL source: local disposable qualification world `coa_test_b4e6cfd8d4ce_world`, captured using sequential SELECTs. This is neither a transactionally consistent snapshot nor a live Ascension deployment audit. Initial SQL capture covers the declared class-spell IDs and resolved ranks, not every talent/trigger added during expansion. The per-ability SQL coverage flag distinguishes this. Captured tables include spell_bonus_data, spell_proc, spell_ranks, spell_script_names, spell_dbc and spell_learn_spell. Empty results remain empty; DBC and SQL rows are kept separate rather than applying guessed merge precedence.

The MySQL client did not support `--no-login-paths`; extraction used the existing capture function with that flag removed and `MYSQL_TEST_LOGIN_FILE=/dev/null`, plus its temporary private defaults file. No credentials were saved in this package.

Static source mentions mean a numeric ID occurs at a location, not that the code runs for that spell. Scenario links identify authored tests, not passed tests. Runtime behavior has not been verified by this catalog.

Six unresolved spell references are retained in `summary.json`. They must be investigated rather than silently discarded or replaced.

## Next organization pass

1. Expand SQL evidence to the entire detailed cohort and reconcile loader/correction precedence.
2. Interpret linked C++ mechanics into reviewed predicates, state transitions, damage/resource formulas, and proc probabilities.
3. Connect advancement candidates to validated learnability and specialization constraints.
4. Parameterize regeneration, haste, GCD floors, resource caps and gear from character state.
5. Feed reviewed records into a bounded rotation planner; compare predicted resource/damage traces with native execution.

Sustainability is a sequence property: after each time interval apply regeneration and resource gains, enforce the resource cap, then require enough resource for the next effective cost. Damage optimization must also account for cooldowns, cast/GCD occupancy, buff windows, target lifetime, movement, tank threat and crowd control.

## Player-selected rune modifications

See `BUILD-MODIFIERS.md` for the build-aware catalog contract and `rune-candidates.jsonl` for unverified name-search candidates. Baseline spells remain unchanged. Selection mapping and modifier semantics still require verification.

## Execution-based descriptions of unresolved entries

`RUNE-DESCRIPTIONS.md` contains a provisional description for each of the 443 previously unresolved entries. `runes-described.jsonl` retains effect slots, target enums, raw amounts, modifier operations, native dispatch/definition locations, linked execution IDs and literal source leads. `rune-execution-evidence.json` preserves the source DBC records and source hashes. Reproduce inside coa-resume with `python3 -B /work/aether-spell-catalog/describe_unresolved_runes.py`.

Standard effects are described from native dispatch and effect/aura enums. Dummy/script effects are explicitly unresolved beyond those primitives; source ID mentions may be unrelated numeric collisions. Spellfire Runes 801512 also includes a manually inspected source-hook explanation. This is not a full semantic interpretation of every script. Aura-removal references are not traversed as executed effects. Two missing linked spell definitions remain recorded. Final amounts, masks, selection eligibility, correction precedence and live behavior require further verification. Original authored descriptions and baseline data were not replaced. See `rune-description-verification.json` for coverage and integrity checks.

## Generated description database layer

All 443 execution interpretations are stored in `generated_spell_descriptions`, keyed to `spell_index.id`. Original descriptions are preserved. Status, scope candidates, full JSON evidence and source hash accompany each interpretation; runtime verification and planner eligibility remain false. `query.py --id ID` exposes this as `generated_interpretation`. The transactional, repeatable importer is `import_generated_descriptions.py`; a pre-import SQLite backup is retained under `backups/`. Validation is in `description-import-verification.json`. This updates only the independent catalog, not the realm database.

## Live evidence-table deployment

2026-10-14: At operator request, imported 443 provisional rune/spell execution descriptions to VM193 Ascension acore_world.aether_generated_spell_description. Full text/evidence readback verified; live Spell.dbc hash matched. Original spell tables untouched; no restart; no Aether/planner integration enabled. Receipt: /home/raymondj/projects/aether-spell-catalog/live-description-deployment.json. Remote release and data-preserving rollback: /home/coa/wow-coa/releases/rune-descriptions-2dae08d5ec79/.

## Preliminary combat evaluator

`planner/evaluate.py` implements offline bounded action search for DPS, effective HPS and a PvP capability vector. It models resources, regeneration, cast/GCD/cooldown timing, periodic refreshes and reviewed numeric build modifiers. See `planner/README.md` for run commands and explicit limits. Four synthetic profile results are retained; these are not live measurements. No automatic interpretation of unverified catalog descriptions or runtime deployment is enabled.

## Local Combat Lab

Open http://127.0.0.1:8797/ for 5/10/15/25/40-player scenario construction and replay. See `webui/README.md` for startup, controls, verification and synthetic-model limitations.

Combat Lab v0.2 supersedes synthetic kits with source-backed baseline mechanics, editable character stats and explicit coverage/exclusion reporting. Maximum encounter duration: 1,200 seconds. See `webui/README.md` for remaining native-engine parity limitations.
