# Gutter Saints Bowling Bot v2.7.9.2 — Living Lanes

A Discord bowling game and tournament platform with persistent SQLite careers, teams, tournaments, achievements, progression, graphical lane presentation, contextual commentary, GIF hooks and optional voice-channel audio.

## v2.7.1 integration
- Public **My Arsenal** selector persists each bowler's primary strike ball; Plastic remains automatic for spares.
- Tournament Director **Presentation** control sets oil pattern, Standard/Broadcast/Finals/Chaos layout, odd-numbered lane-pair start and broadcast title.
- Broadcast/Finals/Chaos now play the generated Approach → Path → Breakpoint → Impact → Leave sequence by editing one Discord image message rather than flooding the channel.
- Layout policy now actually controls lane graphics, GIF priority and audio.
- Recovery snapshots persist ball selection, layout, branding and each lane's independent oil/traffic state.
- Database presentation tables support bowler avatar URLs, team logo URLs and tournament branding/background URLs for match graphics.

## v2.7 highlights
- Lane-pair model with alternating lanes and independent transition.
- Custom pattern framework (House 40', Fresh House, Neon Flood, Burnt Saints, Transition).
- Derived ball speed, rev rate, breakpoint and entry angle from existing bowler stats.
- Strategic ball arsenal: Solid, Pearl, Hybrid, Urethane and Plastic. Balls change shape/control and oil fit; they do not add raw stat points.
- Spare shots target surviving pins and default to plastic rather than using the strike pocket model.
- Carry vocabulary/events including Brooklyn, messenger, trip-4, ringing 10, stone 8/9, light mixer and pocket 7–10.
- Generated lane sequence stages: approach, path, breakpoint, impact and leave.
- Left/right-handed path mirroring and visible oil/transition data.
- Event priority so rare/spectacular moments beat generic strike/spare reactions.
- Presentation policies: Standard, Broadcast, Finals and Chaos.
- Branding placeholder file at `assets/branding.json` for tournament titles/backgrounds.
- Existing team logos/bowler avatar database support can be layered into cards without changing physics.

## Setup
1. Install Python 3.13+.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set `DISCORD_TOKEN`.
4. For voice effects, install FFmpeg and place licensed audio in `assets/sounds/`.
5. Run `python bot.py`.

## v2.7.9.2 Living Lanes
- Left and right lanes now evolve independently with spatial inside/track/outside burn plus carrydown.
- Ball hook, Spin, Style, line and handedness influence where traffic changes the lane.
- Auto bowlers read transition and can change Solid/Hybrid/Pearl/Urethane and move boards as conditions evolve.
- Better Accuracy/Consistency/Style makes bowlers react to transition sooner; it does not grant a hidden scoring bonus.
- Lane adaptations are mirrored for left-handers.
- Broadcast commentary announces meaningful lane changes, ball switches and line moves.
- Live Shot Decision panels expose outside/track/inside wear and current board movement.
- Full lane-zone and bowler-adaptation state survives Undo/Restore.

## v2.7.9 Bowling Depth
- Adds Normal, Safe, Aggressive, Recovery and Spare shot intents plus Auto strategy.
- Shot intent is a bounded tactical modifier: Safe/Recovery trade carry for control; Aggressive trades control for carry; Spare prioritises targeting.
- Accuracy and Consistency govern execution variance, Spin/Style help aggressive shape/carry, and Nerves influences pressure decisions.
- Auto strategy reads standing pins, lane oil/transition, pressure and bowler profile; tournament autoplay remains hands-off.
- Spare intent and Plastic ball are automatic whenever pins remain standing.
- Optional `/game_shot` overrides the next delivery without changing the bowler's permanent setup.
- Live scoreboards show ball, intent, lane, transition and target for each delivery.
- Shot strategy survives Undo/Restore session persistence.

## v2.7.8.6 Career Honours
- Completed tournaments can now issue permanent, duplicate-safe career honours.
- Championship and runner-up honours are awarded to the recorded final rosters.
- Tournament High Average, High Game, Strike Leader and Split Slayer honours are derived automatically from tournament stats.
- Honours feed the Career Timeline and career profile honours count.
- Tournament Director gains a Career Honours ceremony button; players gain an Honours browser from their career card.
- Re-running a ceremony is safe: `(bowler, tournament, honour)` is unique and cannot duplicate.

## v2.7.8.5 Career Evolution
- Replaces independent random +/- stat rolls with persistent performance tendencies.
- Every meaningful delivery can add positive or negative evidence to Accuracy, Consistency, Spin, Nerves, Style or Flair.
- Sustained evidence at +/-10 converts into a permanent +/-1 career attribute movement, still clamped to the 1–50 career range.
- Gutter patterns, single-pin misses, late pressure misses, difficult split conversions, creative carry, strike streaks and clutch shots all shape different tendencies.
- Clean games, six-packs, 250+ pressure games and severe open-frame collapses add game-level evidence.
- Rank changes and attribute changes are written to a persistent Career Timeline.
- My Bowler/My Stats now expose Career Timeline and Tendencies buttons.

## v2.7.8 Bowler Career & Identity
- Rich Career Profile with named Rank, XP and next-Rank progress.
- Persistent rookie attribute baseline and Rookie → Current movement.
- Recent five-game form, career average and personal best.
- Career 200/250/300 counts, clean games, strike/spare rates and split conversions.
- Preferred ball, archetype, achievements, awards and upgrade credits.
- Existing bowlers are safely backfilled on first v2.7.8 database initialization; future changes remain measured from that baseline.
- My Bowler and My Stats now share the canonical career card.

## v2.7.7 Dashboard UI Conversion
- Admin dashboards now perform actions directly instead of replying with “use /command”.
- Team UI: create teams, assign/move bowlers to slots and inspect rosters.
- Tournament UI: create tournaments, enter teams, start brackets, show brackets and open Tournament Director.
- Match UI: guided Team A/opponent/oil-pattern setup, graphical Lane View and Undo/Restore recovery.
- Records UI: Hall of Fame, bowler award browser/giver and Simulation Lab modal.
- Settings UI: join/move/leave presentation voice directly.
- Slash commands remain available as fallback/power-user entry points and share the same underlying services.

## Main UI
Use `/menu` as the normal entry point. Admin Control now provides the full dashboard-driven management flow; `/director` and the existing slash commands remain optional shortcuts. The original bot remains preserved on `legacy-v0.1`.

## Media
GIF/media URLs live in `assets/media.json`. Audio mappings live in `assets/audio.json`. Local copyrighted assets are intentionally not bundled.

## Data safety
The live SQLite DB, backups, exports, generated lane cards, `.env`, caches and local sound files remain ignored by Git.
\n\n## v2.7.5 Simulation & Balance Lab\nAdmin-only /simulation_lab runs 1,000–100,000 headless games per build. Controlled tests cover Rank 20 vs 30, Accuracy vs Spin, handedness and Nerves, across all oil patterns and fresh/transitioned/burnt starting lanes. Reports average, 95% CI, strike/spare rates, 200+/250+/300 rates and dominance warnings, with optional CSV export. Deterministic seeds make balance changes regression-testable.\n