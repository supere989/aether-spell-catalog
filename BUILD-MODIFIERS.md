# Player-controlled build modifications

Status: catalog design and discovery candidates; no runtime planner integration yet.

A rotation belongs to a character build. Preserve baseline spell records, then resolve the character's selected runes, talents, equipment effects and other selectable modifications into an effective ability set. Never assume a class label determines the complete build.

## Required modification record

- Stable modification identity and source version; separate item, spell, enchant and selection IDs.
- Ownership/unlock, class/spec/level requirements, slots, maximum count, exclusivity groups, rank and stacking rules. Unknown values remain unknown.
- Affected spells through explicit IDs, family masks, tags or reviewed script predicates.
- Changes to cost, resource generation/regeneration/caps, damage/scaling, cast time, GCD, cooldown, charges, duration, targets and proc conditions.
- Operation (add, multiply, replace, grant, suppress), units, application order and activation predicate; retain evidence for each rule.
- Triggered abilities and temporary state transitions, including internal cooldowns and proc chances.

## Character build input

Record character identity, level, specialization, learned spells, stats, gear/enchantments and selected modification IDs with rank and slot. Record temporary auras and encounter state separately. A learned or owned rune is not necessarily selected or active. Changing a selection invalidates the effective-ability and rotation caches.

Evaluate eligibility first, then apply verified modifiers in native order. Recompute expected damage, resource trajectories and sustainable rotations from the effective build. Check available resources at every action, including regeneration timing, caps and proc-dependent gains. Keep unsupported modifier semantics visible; do not silently optimize as if they had no effect. Report baseline and modified DPS separately under identical encounter assumptions.

For optional build optimization, search only legal, available selections. Recommend changes for player review; a rotation planner should not silently change the player's chosen runes.

## Discovery evidence and unresolved mapping

`rune-candidates.jsonl` is a case-insensitive name search of the existing Spell.dbc index. It is deliberately a discovery list, not an approved customization catalog: it contains NPC effects, runeforging, Runemaster class abilities and other unrelated uses of the word rune. Every candidate has unknown player-selectability and unverified modifier semantics.

The source `AscensionRunePouches.cpp` identifies item 375250 as Rune of Ascension currency and pouch payouts. Currency ownership is not proof of an equipped build modifier. Runemaster mechanics and Death Knight rune resource costs must likewise remain distinct from player-selected modifications.

Next evidence required: identify the actual player's rune selection UI and its stored selections, trace those identities to effective server effects, then extract slot/exclusivity rules and reviewed modifier formulas. No live character selections or runtime behavior have been verified here.

## DPS rune scope

Include only modifications affecting damage output, offensive scaling, resource costs/gains/regeneration/caps, or offensive ability timing. Pure cosmetic and unrelated utility modifications are outside this planner's scope. Mixed runes remain candidates if any effect is relevant; model only the relevant effect and its prerequisites. Healing-only timing and defensive resources do not qualify without an offensive interaction.

`filter_runes.py` partitions the existing name-search cohort into `runes-combat_candidates.jsonl`, `runes-out_of_scope_candidates.jsonl` and `runes-unresolved.jsonl`. It retains matching description words as audit evidence. This is a preliminary description filter: damage taken, ordinary spell costs, healing cooldowns and NPC attacks can produce false positives. Nothing is marked planner-eligible. Blank descriptions and indirect effects require linked-spell/script review before exclusion or admission. See `rune-triage-summary.json` for counts and checks.
