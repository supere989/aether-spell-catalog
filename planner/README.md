# Preliminary DPS, HPS and PvP evaluator

`evaluate.py` implements a deterministic, bounded beam search over legal actions and waiting. It is an offline planning prototype, not a live bot controller or native-combat replacement. No server files or databases were changed for this implementation.

## Run

Inside the existing devbox:

```sh
podman exec -w /work/aether-spell-catalog/planner coa-resume python3 -B evaluate.py example-dps.json
podman exec -w /work/aether-spell-catalog/planner coa-resume python3 -B evaluate.py example-hps.json
podman exec -w /work/aether-spell-catalog/planner coa-resume python3 -B evaluate.py example-pvp.json
podman exec -w /work/aether-spell-catalog/planner coa-resume python3 -B -m unittest test_evaluate
```

The script uses only Python's standard library and also runs locally. `--output PATH` saves a result. All supplied examples are synthetic fixtures, not live class/rune balance data.

## Algorithm and objectives

At each time step, enumerate legal abilities plus waiting. Check resources, cooldown, occupancy, distance, movement, silence and the supplied tank-threat permission. Pay costs at cast start. Apply effects and resource gains at completion; start cooldown at the configured cast-start or completion time. Regenerate resources continuously, cap them, process periodic ticks, and stop acting after death. GCD/cast occupancy prevents overlapping actions. Periodic recasts replace future ticks from the previous application of that same ability.

Retain a configurable number of promising states; identical future states retain the better objective. Pending direct effects get a heuristic allowance during pruning so long casts can compete. The final result uses only effects actually delivered within the horizon. This is approximate search, not a guarantee of the globally optimal rotation. Increasing beam width or extending the horizon can change the result.

- **DPS:** total modeled damage / full encounter duration. Inputs are resolved expected damage per hit/tick; the scenario supplies a post-calculation damage multiplier. No raw DBC base-points-as-damage shortcut.
- **HPS:** effective healing / full encounter duration. Health missing limits healing, with overhealing reported separately. Incoming damage occurs over each interval before endpoint heals. The single health pool represents the healing target in HPS mode; its death ends that trajectory.
- **PvP:** configurable weighted objective combining damage, effective self-healing, control seconds and survival seconds. Report the underlying vector: pressure DPS, effective HPS, peak five-second damage, control uptime, remaining health and survival. This is not a win probability or a universal PvP rating.

The opening resource pool contributes to results: finite-horizon DPS is not proof of indefinitely sustainable DPS. Inspect remaining resources and compare longer horizons before calling a rotation sustainable. The current regeneration model is constant-rate; resource ticks, rune recharge and casting-related mana-regeneration rules require explicit later models.

## Build/rune input contract

Abilities require `reviewed: true` and an evidence reference. Each supplies identity, resolved damage/healing, cost/gain, resource type, timing, restrictions, optional periodic effects and generic PvP control. See example JSON files for the exact input shape. Unsupported fields are rejected rather than silently ignored.

Selected modifiers can add, multiply or replace supported numeric fields for explicit ability IDs. They require evidence and review, and apply in supplied order. The caller must validate selection ownership, slots, rank, exclusivity and native stacking order. The evaluator does not claim to validate a live character's build. Unknown ability targets, duplicate IDs, negative effective values and unsupported operations fail validation. Timing changes must align with the selected simulation grid.

The 443 generated catalog descriptions and live `aether_generated_spell_description` rows remain provisional. This prototype does **not** automatically turn them into executable modifiers or label them reviewed. A reviewed adapter from server-effective character/spell state is the next integration step.

## PvP assumptions

One generic opponent supplies incoming damage; configured control reduces that incoming damage. Shared control categories use diminishing returns of full, half, quarter, then immune, resetting after a configurable interval following the last applied control's end. Reduced durations round down to the simulation grid. This is an explicit model assumption, not verification of CoA's deployed PvP rules. Healing is self-healing in this mode. Opponent kill time, reactions, range changes and counterplay are not modeled.

## Remaining integration

1. Resolve native character stats, learned abilities and selected runes into reviewed effect inputs, including spell corrections and scripted behavior.
2. Add stochastic procs, conditional buffs, native regeneration, absorbs, auto-attacks, pets, channels and multi-target/party health pools.
3. Add PvP opponent policies, movement, interrupts, dispels, immunities, healing reduction and encounter-specific diminishing returns.
4. Compare resource and damage/healing event traces against native execution before enabling bot decisions.

Current tests exercise conservation, legal timing, modifiers, refresh behavior, healing caps, restrictions, control, death and action selection. Example traces and their assumptions are retained alongside the implementation.
