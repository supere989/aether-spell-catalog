# AetherCraft Combat Lab v0.2

Open **http://127.0.0.1:8797/**. Start manually if stopped:

```sh
python3 -B /home/raymondj/projects/aether-spell-catalog/webui/server.py --port 8797
```

The local process uses `server.pid` and `server.log`. It binds only to loopback and is not a boot service. No realm files, services or databases are modified by this application.

## Controls

Choose 5, 10, 15, 25 or 40 players, then edit each class and role. Duration now accepts **5–1,200 seconds (20 minutes)**. Enemy health and incoming pressure determine whether a run ends earlier in victory or a wipe. To exercise the full window, choose sufficient enemy health and survivable incoming pressure.

Each build now exposes level, AP/RAP/SP, healing power, primary stats, health, mana/base mana, weapon base damage and speed, normalization speed, initial rage/runic power, and regeneration. Defaults are scenario assumptions, not measurements of a live character. AP and stats are independent effective inputs: raising strength does not automatically recompute AP. Mana cost percentages use the separate base-mana input. Rage/runic power use native internal units (10 per displayed game point).

The **Mechanic coverage** panel lists actual spell IDs, selected ranks, costs, timing, partial effects and exclusions. It warns when a chosen healer kit has no modeled healing. The class catalog panel remains a separate reference. Replay, per-slot statistics, resources, charts, event logs, browser-local save, scenario import/export and result export remain available. Existing saved scenarios receive defaults for new stat fields.

## Real mechanics now applied

The synthetic Quick heal / Heavy attack / Recover kits have been removed from active simulation. `snapshots/simulation-v01.py` retains the old implementation solely for reproducibility.

- Declared class acquisitions and level-appropriate rank selection, using the catalog and 2,710 server progression entries.
- Native base-point calculation with level caps, per-level contribution and expected die roll.
- Explicit SQL AP/SP coefficients and stock coefficient-zero policy, plus 1,150 per-effect coefficient rows from ten class contracts. Tables retain source hashes. Unmodified baseline stat terms are applied; conditional talent/buff branches are not implied.
- Direct damage/healing, percent healing/energize, weapon flat/percentage/normalized effects, ordinary triggered-spell chains, periodic damage/healing/resource ticks.
- Actual flat and percentage costs, health costs, cast times, GCD, cooldowns, shared cooldown categories and charge recovery.
- Separate mana, energy, focus, rage and runic pools; native baseline rage-from-damage formula for the primary rage pool. Continuous mana/energy/focus regeneration remains an explicit scenario input.
- Unconditional supported custom resource gains/gates/consumption from the source rules. Unknown caps do not manufacture capacity. Pyromancer Heat wraps at 100 and creates Embers capped at five, matching the reviewed Resource implementation.
- Source-backed auto-attack weapon/AP calculation for melee-profile slots; no synthetic tank damage-reduction bonus.

The group engine uses greedy action scoring with shared healing reservations. It is not the standalone planner's beam search. Effects execute on completion. Periodic applications refresh per actor/ability/effect. The engine runs at 250ms resolution (timing rounds upward), with replay samples every 500ms and an additional final frame where required.

## Important coverage boundaries

This is a **source-backed baseline model, not complete native-engine parity**. Every class has executable catalog abilities, but many abilities are excluded and some execute only their supported effects. The UI exposes this distinction. Form/aura/target prerequisites, channels, reagents and rune-slot costs are rejected when not modeled. No generic attack/heal silently replaces them.

Unimplemented areas include selected talent/rune graph evaluation; pet/summon AI; most proc/conditional script chains; crowd control and native PvP rules; resist/immunity/critical/miss resolution; equipped-item eligibility; offhand and real weapon normalization selection; native mana-regeneration rules; snapshot/buff interactions; and complete core spell-correction precedence. Source coefficient tables are baseline terms, not proof of identical final live damage. Generic trigger effects execute only supported primitives, while unsupported slots are listed as partial warnings. Resource event hooks beyond the supported unconditional cases remain incomplete.

Weapon and stat inputs represent assumed equipment. Scenario incoming DPS is already post-mitigation pressure. PvE assigns 70% of that pressure to living tanks and 30% across the living party. PvP distributes scripted pressure uniformly; neither mode implements an enemy threat/decision engine. Formation is illustrative, not pathfinding.

Source DB evidence remains the catalog's captured qualification-world SQL, not a new live SQL snapshot. DBC hash previously matched the deployed realm; local C++ contracts are hashed at extraction time. Neither fact substitutes for runtime combat qualification.

## Verification

```sh
podman exec -w /work/aether-spell-catalog/webui coa-resume python3 -B -m unittest test_simulation test_class_mechanics
podman exec -w /work/aether-spell-catalog/planner coa-resume python3 -B -m unittest test_evaluate
```

14 group/real-mechanics tests and 14 planner tests passed. Checks include all 21 class kits, all five party sizes, source formula deltas, rank selection, Heat/Embers, resource/health bounds, full 40-slot 20-minute execution and rejection beyond the duration limit. UI checks confirm the 1,200-second maximum, actual Runemaster spell/rank display and editable character stats. Run receipts are in `verification.json`.

To regenerate source tables inside the existing devbox: `python3 -B /work/aether-spell-catalog/webui/extract_mechanics.py`. Review contract semantics before admitting new table layouts or conditional mechanics.

### Tank defense scenarios

Encounter controls now include melee pressure percentage (default 0 for compatibility), enemy swing interval (0.25–10 seconds), and a repeatable random seed. Select a player and open **Defense & shields** to set final effective dodge, parry and block percentages, shield equipment, block value, facing, and a finite initial absorb pool. These are scenario inputs, not imported equipment or talent calculations.

The melee share of each recipient's existing pressure allocation accumulates into swings; remaining pressure is continuous and cannot be dodged, parried or blocked. The last partial swing is resolved at the time limit. A single roll resolves miss, then frontal dodge, parry, block, then ordinary hit; chances beyond 100% are table-clipped. Block requires an equipped shield and subtracts up to its flat block value. Attacks from behind bypass all three defenses. Absorption applies after block to either pressure type and depletes without automatic refresh. Events and slot stats report avoidance, blocks, absorption and shield remaining. Incoming DPS is post-armor and before these defenses.

Baseline reference: local core `Entities/Unit/Unit.cpp`, `RollMeleeOutcomeAgainst` and melee outcome resolution. No crit/crushing table, armor calculation, expertise/level adjustment, parry haste, critical block, avoidance-generated resources, school-specific absorb, defensive spell/proc execution or native PvP qualification is claimed. Slot chance inputs must already include desired effective adjustments. Pressure allocation remains the existing illustrative party model, not threat-based mob targeting.

Verification: `python3 -B -m unittest test_simulation test_class_mechanics test_defense` covers outcome boundaries, shield/facing requirements, full blocks, absorb depletion, damage conservation, repeatability and input rejection.


### Miss and glancing

Each slot has separate **Enemy melee miss %** and **Own auto-attack miss %** inputs (default zero; final effective chances). Incoming miss resolves before dodge and still applies from behind. Missed swings do no damage and consume no absorb. Continuous pressure and spells do not use these miss inputs.

**Enemy level** defaults to 60. Outgoing melee autos can glance in PvE only against a higher-level enemy. With capped weapon skill and ordinary level-based enemy defense assumed, chance is `min(40, 10 + 5 * level_difference)` percent. After misses, that chance occupies the next segment of the simplified auto-attack table. Damage multiplier is `1 - 0.1 * min(level_difference, 3)`. This follows the local WotLK path in `Unit.cpp` and `ClassicPlusCombat.h::WotlkGlancingDamageMultiplier`, not the separate ClassicPlus ruleset. Glancing never applies to spells, incoming NPC attacks, or PvP. Enemy dodge/parry/block and outgoing crit remain unmodeled. Separate seeded incoming and outgoing rolls make defense comparisons reproducible. Slot stats show enemy misses, own misses, glancing counts and glancing damage lost; combat events label glancing auto damage.

### Character equipment panel and resource controls

The local character sheet now has 19 clickable equipment slots, a silhouette/paper-doll layout, an item editor, and effective stat readouts. It reproduces the equipment arrangement and interaction pattern, not the native client artwork or 3D model. No item-template table exists in this independent catalog: entries are explicitly custom simulation items, not claimed live game items. Equip/apply or unequip updates the selected simulation actor; gear is saved with scenario local storage and JSON import/export. Nested scenario payload limit is now 1 MB.

Supported bonuses: five attributes, AP/RAP/SP/healing, health/mana, final dodge/parry/block percentages, and flat block value. Gear adds to baseline inputs without mutating them. Stamina-to-health and intellect-to-mana use the delta of the WotLK core formula (first 20 attribute points at 1, remainder at 10/15). Source-confirmed unshifted melee AP attribute deltas are implemented for Barbarian, Reaper, Sun Cleric and Starcaller; other class/form conversions require explicit item AP. Main-hand damage and speed replace baseline weapon inputs; unequipping restores baseline. Shield equipment is derived from off-hand once gear is managed. Two-hand/off-hand conflicts are rejected. Off-hand/ranged attack execution, armor, ratings, enchants, sockets, procs, set bonuses and native class/level equip restrictions are not implemented. All equipment remains local to the simulator.

Resource fields now follow power types used by the class's modeled cost/gain abilities. The inferred primary resource remains a simulation heuristic, not proof of a native active form/power state. Users may edit initial resource and regeneration separately per supported pool; base mana/health remain in base stats. Rage and runic values display in game points, with internal units converted by ten. Class changes clear per-pool overrides; reset restores defaults. Custom class pools show source-backed capacities or an unresolved marker and remain driven by class mechanics. Scenario regeneration overrides do not claim native regen formulas.

Verified 28 simulator tests (including gear add/remove, weapon/shield conflicts, invalid gear, every class's resource controls, and changed damage output), live local kit/simulation API, 19 clickable slots, and unclipped controls at a 700px viewport. Main-hand slot selection opens weapon fields. Native assets, native item browsing, and full equipment parity remain future integration.


### Gear set catalog (current)

The character panel now includes searchable/paginated **Gear set catalog** browsing, set-piece variant selection, stat/warning previews, and validated **Equip selected pieces**. `GEAR-SETS.md` enumerates every set. Captured sources are the client `ItemSet.dbc`/`Spell.dbc` and a read-only item-template query against the existing local qualification world; this does not prove current live realm item availability.

Counts: 2,348 definitions, 1,523 populated sets, 87,435 member item variants, 667 sets with supported flat stats, and 825 definitions without matching item-template rows. Item masks establish no subset-specific CoA sets: all populated sets have some pieces shared across all 21 classes, and some variants retain legacy restrictions. Names do not establish class specialization. Missing membership, unsupported stats, armor, item spell effects, random properties/suffixes and scaling-distribution fields are retained as explicit exclusions. DBC-listed pieces are compared with the database's actual `itemset` membership instead of fabricating records. The source snapshot includes additional queried nonmember rows which are not admitted to the runtime catalog.

Catalog items save an immutable ID reference; the backend resolves authoritative snapshot stats and validates slot, level, CoA class mask, duplicate item IDs and weapon/shield conflicts. Client-supplied copied stats cannot alter catalog gear. Manual editing creates a custom item and intentionally drops set membership. Imported scenarios use the same checks. Selected slots are replaced only when the user clicks Equip selected pieces. The initial variant choices are the highest-item-level usable entries, explicitly previewed before application. This is not an assertion of best-in-slot or full native equip legality.

117 static set-bonus entries execute at their piece thresholds: nonconditional, permanent, self-targeted flat stat/AP/RAP/health/mana/block-value auras. All effects of a spell must be supported to admit it. Other set effects display **active but not simulated** when their thresholds are met. Partial proc execution is never inferred from text. Native AP item stat 38 contributes AP and RAP; spell-power item stat 45 contributes damage spell power and healing power. Item on-equip/use proc spells, rating conversions and native script hooks remain unmodeled. Fixed bonus amounts and descriptions are read from DBC, and raw description tokens may remain in unsupported effects.

Verification: 34 simulator tests including enumeration, paging, canonical item identity, tamper resistance, class/level/slot constraints, set threshold activation/removal, scenario JSON roundtrip and combat execution. Live local API confirmed set equipment and bonus removal. No realm source, runtime database, or server deployment changed.

## Client graphics preview (2026-10-14)

The local character panel now loads extracted WotLK M2/skin geometry for 20 race/sex profiles. Drag to orbit and scroll to zoom. Catalog equipment uses client inventory icons; body armor texture regions are composited onto the skin. The set browser's **Preview selected appearance** button changes only the preview, without applying equipment or changing combat inputs.

This is a static bind-pose preview, not the game renderer: Animation, full material/shader parity, and all race-specific geoset rules remain unimplemented. Missing textures can be absent from a preview. Custom manually entered items have no client visual identity. Appearance choices do not alter combat stats.

Sources: installed `wow-coa/client/ascension-live/Data` MPQs (read only), matching local qualification item display IDs and DBCs. `assets/manifest.json` records archive/path resolution; `assets/models/*.json` records source M2 SHA256. Archive precedence follows the extraction index and has not been proven identical to the live client loader. Assets remain local and are not published. Game assets retain their original ownership.

Rebuild metadata using `prepare_visual_data.py` in coa-resume, then `build_visuals.py` and `.asset-venv/bin/python -B export_character_meshes.py` locally. Extraction uses the local read-only `tools/mpqextract`, built with StormLib from the existing wow-clientdev image. It skips archive list and attribute loading; the first uncached icon test completed in 0.061 seconds. Its source is `tools/extract.cpp`. The exporter imports the existing MIT pywowlib checkout; `.asset-venv` adds bidict 0.23.1. Runtime PNG decoding uses Pillow. Three.js 0.180.0 is vendored locally with its MIT license; no runtime CDN dependency. See https://threejs.org/docs/pages/BufferGeometry and https://threejs.org/docs/pages/TextureLoader.

## Set-to-class evidence

`map_set_classes.py` follows set-bonus trigger chains, explicit aura requirements, and flat/percent spell modifier family masks against CoA acquired spell candidates. Run it after rebuilding the gear catalog. `../SET-CLASS-MAPPING.md` and `set-class-mapping.json` record the result: **zero verified structural class links in this snapshot**. Generic stat effects are shared; names and cosmetic resemblance do not establish class ownership or a tier. Script-only relationships remain unresolved. This does not prove that other server versions lack class sets.

## Slot item picker
Click any paperdoll slot to search its available catalog items by name or ID, inspect icons/stats, and Equip or Unequip. Results are filtered by slot, class mask and required level, with 40 items per page. The catalog currently contains set-member items, not every world item. Equip is validated through the kit API before updating the saved scenario, derived stats and appearance. The custom item editor remains available below the picker.

### Appearance repair
Hair and facial geosets now come from CharHairGeosets and CharacterFacialHairStyles. Hair uses its own material. Face/scalp upper and lower atlas regions are correctly ordered. Paletted BLP2 textures decode their separate 0/1/4/8-bit alpha planes rather than the palette reserved byte; this restores previously transparent armor. Corrected PNGs use the png-v2 cache. Human female with equipped Mystical Elements armor visually checked; other race profiles are exported but not all visually qualified. Run capture_appearance.py in coa-resume before build_visuals.py and export_character_meshes.py.

### Equipped item meshes
Helmet (race/sex-specific), left/right shoulder, main/off-hand, shield and ranged model references now resolve to client meshes, converted lazily through a model-ID allowlist. Character M2 attachment positions anchor the meshes in the static bind pose. Cape texture uses the character cape geoset. Equipping/unequipping rerenders attachments. Browser verification covered a helmet, paired shoulders, cape and paired weapon preview. Grips, sheathing orientation, animation, some effects and race-specific clipping are not native-renderer qualified. Custom stat-only items have no visual model. Rebuild with stage_item_models.py (which rebuilds visual metadata), followed by export_character_meshes.py. Item export uses export_item_mesh.py and its local venv; converted meshes are cached in assets/item-models.

### Equipment alignment repair
Character and item meshes now evaluate the first embedded standing frame with hierarchical bone transforms, pivot rotation, scale, weighted vertices and inverse-transpose normals. Attachment matrices use the same pose as the character. Quaternion decoding reverses the parser-specific Blender XY conversion before evaluating native-space transforms. Zero-scale hidden bones use a pseudoinverse for finite normals. Left shoulder art uses mount 6 and right shoulder art uses mount 5. Helmet visibility uses ItemDisplayInfo gender references into HelmetGeosetVisData rather than hiding all hair. Goggles retain the selected hairstyle. Table layout reference: https://trinitycore.info/files/DBC/335/helmetgeosetvisdata . The preview remains a single standing frame, not animated combat; race-specific clipping beyond the checked Human Female equipment is not visually qualified. Converted posed items now use assets/item-models-v2.

## Public deployment — since 2026-10-15

Public URL: https://aethercraft.net/simulator/ . The backend (`server.py --bind <tunnel address> --base-path /simulator --public-origin
https://aethercraft.net`) runs on a dedicated VM whose git checkout of this repository **is** the live code. The web host's reverse proxy
serves the pre-built asset library (`build_library.py`: every texture, item model and character model, plus `visuals.json` stamped with
the library `generation`) as static files and forwards everything else to the VM over a private tunnel. Library ids are path-addressed, so
library files are cached for a day and item-model fetches carry `&g=<generation>`.

- **Live edits:** `reloader.py` (a user service) watches the checkout. Static files are live on save; Python/data/config changes go live only
  after the unit tests and a candidate server on `127.0.0.1:8799` pass a smoke run — otherwise the running server keeps the old code. Every
  attempt is a `reload.jsonl` row; `/api/status` (never public) shows the last row and `reload_counts`.
- **Configuration:** copy `config/paths.example.toml` to `config/paths.toml` (untracked) and set that machine's paths and world database.
- **Rebuilding data:** build scripts write next to themselves, so rebuild in a scratch worktree with a copy of the data and promote by hand.
- **Publishing:** `tools/hooks/pre-push` (`git config core.hooksPath tools/hooks`) refuses files over 2 MB, generated/game data, credentials,
  internal addresses and `config/paths.toml`.
