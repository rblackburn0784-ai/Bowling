# Gutter Saints Bowling Bot v2.8.5a — Ball Sprite Integration

A Discord bowling game and tournament platform with persistent SQLite careers, teams, tournaments, achievements, progression, graphical lane presentation, contextual commentary, GIF hooks and optional voice-channel audio.

## v2.8.5a — Ball Sprites, Spin & Approach Handoff
- Ten transparent ball sprites mapped to the existing five ball types: Solid (3), Pearl (2), Hybrid (2), Urethane (2), Plastic (1).
- The selected artwork is stable per bowler and ball type, based on bowler identity. Every actual game delivery uses its real engine-selected `event['ball_key']` (including plastic spare shots).
- Frame 5 of The Dude/Jesus approach must finish before ball travel starts; no travelling ball is drawn while a character is still holding it.
- The ball follows the previous lane path geometry using smooth arc-length progress samples, rotates according to revolutions and handedness, and shrinks with distance.
- Multiple Travel, Breakpoint and Impact subframes edit the same live Discord image and keep scoring commentary hidden until Leave.
- Missing assets fall back to the simple circular ball without modifying simulation state. Results, oil physics, progression and scoring remain unchanged.
- Varied commentary now uses a separate presentation RNG, so extra frames do not consume random numbers used for bowling shots.
- Install graphics: extract `Gutter_Saints_v2.8.5a_Complete_Sprite_Pack.zip` in the repository root (`bot.py` folder). This includes The Dude, Jesus and all ten bowling ball PNGs.
- PNGs are distributed separately from the GitHub source commit. Start/restart the bot after copying them.
- Run: `python -m unittest discover -s tests -p test_ball_sprites.py -v`
- CI tests and real Discord edit timing must be verified before production use.

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

## v2.8.3g Commentary Deduplication
- The live graphical broadcast is the sole source of routine ball-by-ball commentary.
- The Broadcast Director emits at most one priority milestone announcement per delivery.
- Strike streak milestones take priority over concurrent lead-change/comeback stories.
- Lead changes and other story events are still tracked for post-game reporting.
- Finals/Chaos retain optional theatrical GIFs without duplicated crowd hype/groans.
- Career progression notices remain separate; friendly challenges do not grant attribute growth.
- Requires beta verification with /game_auto in broadcast, finals and chaos layouts.

## v2.8.3e Unified Live Match Broadcast
- A single 1570×1064 graphical panel now combines the lane, pins, ball trajectory, bowler names, frame results and delivery commentary.
- The bot edits the same Discord attachment for each ball rather than sending separate lane and scoreboard graphics.
- Routine lane notes and broadcast director announcements are folded into the broadcast experience; Finals and Chaos retain more theatrical messaging.
- The underlying bowling engine and game scoring are unchanged.
- Beta validation still required for Discord attachment edits, graphics, and match flow.

## v2.8.3b Weekly Gazette Production Pass
- Every Monday (UTC), an hourly background job archives the preceding complete calendar week for active/completed seasons. The database prevents duplicate issues on restarts.
- Each edition now has a printable newspaper-style PNG (1200×1550), attached when published or opened from the archive.
- SQLite regression tests cover weekly duplicate prevention, immutable historical content, second-week numbering, missing seasons, newspaper rendering, and the admin permission guard.
- GitHub Actions Python 3.13 workflow runs these tests and compiles the source on pushes.
- The artwork is typographic newspaper design, not AI-generated illustrative photography.
- Publication is archived automatically; posting into a public announcement channel is not yet configured.

## v2.8.3a Weekly Gazette Archive
- Immutable weekly issues stored per season and ISO Monday-Sunday week.
- Archive browsing via Season Hub, with issue selection and historical issue retrieval.
- Admin-only Publish Weekly Issue button (Manage Server permission).
- Database unique constraints prevent duplicate editions for a season/week.
- Each issue captures completed fixtures and bowler games recorded within its week.
- Note: manual publishing only; automatic scheduled publication and image-rendered newspaper pages are not included.

## v2.8.3 Season Presentation & League Experience
- Graphical 1100×580 season hub card rendered with Pillow from persistent season data.
- Public Season Hub and Competition Director → Season Experience.
- Fixture-week match centre, W/D/L form table, promotion/relegation and playoff zones.
- Season award races: average (minimum three games), high game, strikes, split conversions and appearances.
- Season high-game records and a season-specific Gutter Gazette bulletin built from actual results.
- Competition selection through Discord dropdowns; all views work with team or individual competitions.
- Season read models never modify global career totals.

## v2.8.2 Competition Director & UI
- Makes Competition Director the primary admin tournament/league surface instead of requiring IDs and slash commands for routine operation.
- Competition selector with overview, fixtures/results, standings, bracket/stage viewer, playoff picture, locked roster/substitute manager and Start Next Fixture.
- Start Next Fixture launches the next playable scheduled fixture directly into the full live bowling engine.
- Double elimination fixtures persist explicit Winners Bracket, Losers Bracket and Grand Final/Reset identity for presentation.
- Locked team rosters can switch starters/substitutes from dropdown controls; individual competitions need no roster administration.
- Public Main Menu adds My Competition. Owned bowlers can see current competitions, placement, record, next fixture and active/eliminated state.
- Double-elimination player status exposes losses used out of two lives.
- UI remains backed by the same v2.8 competition/stage/fixture engine, so team and individual competitions share one operational model.

## v2.8.1 Competition Operations
- Makes every v2.8 format operational for both team and individual entrants through the shared fixture engine.
- Single elimination advances winners round-by-round; seeded byes remain supported.
- Double elimination tracks entrant losses, eliminates on the second loss and progresses winners/losers pools toward the final/reset.
- Groups → Knockout ranks each group, qualifies the top two and cross-seeds the knockout stage.
- Stepladder advances each match winner into the next higher seed.
- Best-of-X persists individual fixture games and resolves only when an entrant reaches the required series wins.
- Qualifying now uses playable round-robin qualifying fixtures and advances configured qualifiers into knockout finals.
- Round-robin competitions can automatically create a playoff stage from the configured top N.
- Locked competition rosters support designated substitutes without mutating historical team membership.
- Promotion/relegation outcomes are persisted from completed final standings.
- Scheduled fixtures can launch directly into the normal live GameSession, for teams or individual bowlers, and completed bowling games report back into fixture/series progression.
- Competition context survives the existing session recovery path.

## v2.8 Seasons, Leagues & Competition
- Adds a unified persistent competition model: season → competition → stage → fixture/series → bowling game.
- Controlled lifecycle: Draft → Registration → Locked → Active → Completed → Archived.
- Supports team and individual entrants, seeded registration and immutable competition roster snapshots at lock.
- Competition formats: Single Elimination, Double Elimination, Round Robin, Groups → Knockout, Stepladder, Best-of-X and Qualifying.
- Round-robin scheduling, seeded knockout/byes, group fixtures and stage-driven advanced-format foundations.
- Persistent standings track played, W/D/L, pins for/against, differential and configurable league points.
- Adds league templates for recurring competition configuration plus playoff, promotion and relegation settings.
- Adds season-specific bowler statistics while preserving global career XP, Rank, attributes, tendencies and lifetime records.
- Career profiles now expose seasons played and championships.
- Season dashboard surfaces upcoming fixtures and leaders for average, high game, strikes and split conversions.
- Existing tournament tables remain intact for legacy compatibility while v2.8 competitions use the new engine.

## v2.7.9.9 Integration, Balance & Reliability
- Release-gate audit across scoring, game physics, Living Lanes, shot strategy, career systems, tournament honours, Broadcast Director, Gazette and recovery.
- Undo/Restore now persists Python RNG internal state, making the next delivery deterministic after recovery rather than merely restoring the original seed.
- Tournament championship/finals history is idempotent when Career Honours is rerun.
- Automatic Gazette publishing is idempotent for unchanged tournament state; manual Director publishing remains explicit.
- Broadcast tournament-pressure stories are bowler-specific to prevent unrelated story dedupe collisions.
- Simulation Lab rookie profiles now enforce the real 90-point, 5–25 creation rules and include a legal archetype balance suite.
- Added `python -m services.release_audit` offline release gate for core syntax, 300/all-spare scoring, deterministic restore and rookie balance warnings.

## v2.7.9.7 Gutter Gazette
- Adds persistent newspaper-style tournament issues built entirely from recorded match/story/stat data.
- Headlines prioritise real perfect-game watches and comebacks, then fall back to the tournament high-game story.
- Issues include Player of the Issue, High Game, strike threat, Split Slayer, comeback/match drama, career attribute movement and latest result when available.
- Each issue is stored as a historical snapshot; later stat changes do not rewrite old editions.
- Tournament Director can publish an issue manually and tournament matches auto-publish after completion.
- Public menu gains Gutter Gazette access with the latest issue and a compact recent-issue archive.

## v2.7.9.5 Broadcast Director & Match Stories
- Adds a stateful Broadcast Director that remembers match context instead of generating isolated reactions.
- Detects meaningful lead changes, comeback swings, close late matches, PB pace, long perfect-game runs, rivalry responses, lane adaptations and late tournament pressure.
- Story beats are de-duplicated so the same narrative is not repeated every delivery.
- Tournament story beats persist in `tournament_stories` and survive match/session recovery.
- Post-game Match Story selects the strongest narrative beats from the contest for a compact recap.
- Broadcast state (leader, comeback lows and already-used story beats) survives Undo/Restore.

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