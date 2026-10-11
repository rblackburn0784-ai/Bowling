# Gutter Saints Bowling — Rule and Second-Delivery Audit

Date: 11 October 2026
Scope: current `main` 2.8.5q codebase, including rule fixes added in this pass.
Reference: International Bowling Federation Universal Playing Rules 2.1–2.4 and BTBA Rule 2 (conventional tenpins).

## Review / code paths
- `services/scoring.py`: all 10 frames, strike and spare bonuses, 10th fill balls, incomplete and invalid data, scoreboard frame notation.
- `services/game_engine.py`, `services/pin_engine.py`, `services/lane_physics.py`: player order, consecutive throws, lane-pair rotation, standing pin subsets, spare ball selection, 10th-frame rack resets and foul/gutter edge cases.
- `services/analytics.py`: strike/turkey and spare counts, including tenth-frame bonus deliveries.
- `services/shot_animation.py`, `services/scene_renderer.py`, `services/hybrid_broadcast.py`, `services/ball_sprites.py`, `cogs/games.py`: ball/sprite linkage, before/down/after pin rendering, second-delivery file identity, travel/breakpoint/impact frames and live scoreboard timing.
- `storage/database.py`, `services/v25.py`, `cogs/games.py`: persisted game summaries, full-match completion and snapshot restore after first ball.
- All 19 test modules in `tests/`, plus Python syntax compilation and the added rules/graphics tests in GitHub Actions.

## Fixed issues
1. Player turns incorrectly advanced after each *ball*, splitting a bowler's frame across other players. Player now retains the turn through second delivery and 10th bonus shots.
2. Lane 3/4 alternated after each *ball*, placing spare attempts on the opposite lane. Lane remains fixed during the frame and switches after frame completion.
3. Second delivery after a tenth-frame strike was recorded as ball 1. Now numbered ball 2 (then ball 3).
4. A zero-pin first ball (gutter or complete miss) left all pins standing and caused the next shot to use strike targeting, not spare equipment. `0/` now correctly uses the plastic spare ball and spare intent.
5. Tenth-frame `X-/` bonus shot was similarly treated as a new strike attempt. It now uses spare targeting and correctly records the fill-ball conversion.
6. Frame notation represented `0/` as `-X`; fixed `-/`, `X-/`, `X7/`, `9/X`, `XXX`, and ordinary 10th notation.
7. Incomplete or malformed 10-frame data could index off the end of the scoring rolls or receive impossible bonus scoring. Complete games are now validated before computing scores. Incomplete games return 0; invalid complete frames raise `ValueError`.
8. Tenth-frame 0/ was falsely counted as a strike in live streak logic. Tenth-frame X-/ fill spare also inflated strike stats; corrected.
9. Bonus strikes were omitted from longest strike streaks and overlapping turkeys (a perfect 300 now has 12 strikes, longest streak 12, and ten overlapping three-strike windows).
10. Tenth-frame X7/ (including X-/) converted fill-ball spares now count as conversions in summary statistics, without changing scored pins.
11. Converted split after a tenth-frame first-ball strike now gets recorded in career split-conversion state.

## Automated verification
- Standard scores: 0, 90, 150 (five-per-roll spare), 190 (nine-spare sequence), 180 IBF example, 278, 287 and 300.
- Reject illegal frame values, excess strikes/bonus rolls and impossible pin sums.
- Complete and partial 10th: `XXX`, `X7/`, `X-/`, `9/X`, `-/X`, open tens, and partial unfinished bonus rolls.
- Two linked bowlers: ordinary second ball retains player, frame, physical standing pins, lane and spare ball, including zero-pin opening balls.
- 10th: strike resets rack; spare resets rack; bonus deliveries keep player and lane; no third ball after open frame.
- Mid-frame snapshot restoration retains pin leave and lane choice.
- Seeded live bowling physics: set arithmetic always satisfies `before = down ∪ after`; down and standing are disjoint, with a 0–300 score range and no more than allowed deliveries.
- Full first-and-second delivery event integrated with hybrid renderer: multiple distinct ball-travel positions, breakpoint, progressive pin-impact frames, correct final leave and encoded GIF.
- Existing match controls, match completion, career, shot GIF, winner sprite, lane scale, scoreboard, dual pin camera and Gazette tests remain in CI.

## Remaining limitations / operational risks
- **Client playback:** automated GIF tests cannot replicate Discord's actual image autoplay, caching, network delays or reduced-motion settings. Verify in one live two-bowler exhibition with at least one spare attempt and final winner.
- **Pin artwork geometry:** the user-supplied overhead background contains locator dots in a decorative 5-3-2 arrangement, rather than the official 4-3-2-1 pin configuration. The engine uses true ten-pin IDs and pinfall, but the camera is not a regulation physical depiction.
- **Sanctioned procedural rules:** foul detection, dead-ball/re-spotting adjudication, provisional balls and bowling-equipment certification are not implemented as a full sanctioned tournament rule system. These are simulation rules rather than a USBC/BTBA certified system.
- **Persistence:** match finalisation involves multiple SQLite transactions for scores, progression, achievements, history and tournaments. If externally interrupted at precisely the wrong moment, reconciliation may be needed; previously recorded games should never be replayed blindly. Full end-to-end transaction/idempotency is still a separate hardening task.
- **Active sessions from earlier code:** old snapshots encoded lane switching per ball. Complete or cancel any active matches before pulling this patch, then start a new match; do not assume mid-game migration between versions is compatible.

## Install and smoke test
1. Back up `data/*.db` and pull latest `main`; leave all PNGs where they are.
2. Restart bot and create a **new** two-player exhibition.
3. Check a 7 then 3: same bowler, same lane, plastic second-ball GIF, correct pin disappearances and spare `7/`.
4. Check 0 then 10: spare `-/`, no false strike.
5. Complete a 10th X7/ or 9/X, check bonus shot count and final score.
6. Verify the winner's `cheer.png` and game history/stats are committed once.
