# Gutter Saints Bowling Bot v2.8.5o — Left Hero Re-anchor & Victory Cheers

A Discord bowling game and tournament platform with persistent SQLite careers, teams, tournaments, achievements, progression, graphical lane presentation, contextual commentary, GIF hooks and optional voice-channel audio.

## v2.8.5o — Left Hero Lane Re-anchor & Winner Cheer Sprites
- Supports the user's updated **`assets/lane/gutter_saints_empty.png`**, which now depicts only the full-length bowling lane and front pinsetter. The left hero panel no longer draws the old top-down pin deck.
- **Re-anchored LEFT lane:** forward-facing standing/fallen pins now sit in the new pinsetter opening (y ≈ 458–500 in the 941×1672 master), rather than in the old combined layout's lower pit. The animated ball releases near the camera and travels to y ≈ 495 at impact. The Dude/Jesus remain foreground, correctly proportioned and anchored close to the lane approach.
- **RIGHT panels unchanged:** the overhead pin deck uses its original 941×1672 master coordinates and camera crop; the vertical pit still uses its original coordinates/crop. Both panels remain visually independent of the new LEFT artwork and use the same engine `before/down/after` values, including moving pin knockdown animations.
- **One-time optional art install needed for the exact original two right backgrounds.** Extract the companion `Gutter_Saints_v2.8.5o_Camera_Backgrounds.zip` beside `bot.py`; it contains `assets/cameras/overhead_empty.png` and `assets/cameras/pit_empty.png`. The new `assets/lane/gutter_saints_empty.png` is *never overwritten*. Missing camera art yields a safe plain-colour fallback instead of a crash.
- New five-frame bowler approach, rolling ball artwork, selectable bowling balls, and 5-stage falling-pin animation remain unchanged in the simulation; only cosmetic left-side positions are shifted.
- **Winner celebration:** supports **`assets/sprites/the_dude/cheer.png`** and **`assets/sprites/jesus/cheer.png`** without renaming the existing `1.png`–`5.png` approach frames. When a match successfully finishes with a unique winner, the bot edits the live graphic with the winner's correct character cheering. For team matches, the highest-scoring member of the winning team represents the victory; a tied game has no artificial victor.
- `cheer.png` is optional. If missing or invalid, the renderer falls back to the normal fifth approach pose and honours/progression still finish. The final visual update is best-effort and cannot cancel a recorded result.
- Extensive new regression tests verify no overhead graphics in the left panel, hero pin deck and ball impact alignment, unchanged right camera positions when LEFT art changes, both character cheer loaders, winner identity, ties, and final Discord message editing.
- No scoring, pinfall physics, tournament logic, rank, XP or career progression was changed. Restart the bot after pulling latest code; test a new two-player exhibition to completion.

## v2.8.5n — Game Completion Reliability
- Fixed a real game-finishing crash (`NameError: cannot access free variable 'player_summary'`) caused by an unnecessary `from services.analytics import player_summary` nested inside `Games.finish()`'s friendly-match branch. Both normal and friendly games now use the shared top-level import.
- Fixed the follow-on SQLite locking risk: post-game history and seasonal statistics are committed before awarding rank/XP, calculating career tendencies and granting achievements. Previously those helpers opened a second writing connection while the first still held a SQLite write transaction.
- Player summaries are computed before the first result is persisted, so errors in analytics do not cause an early partially recorded game.
- On a replay/resume attempt, existing `game_history` entries for the same game ID and bowler will not be inserted twice or count toward season totals again; the game must still be reviewed if a previous release crashed mid-finalisation.
- Manual and Auto Play buttons now report processing exceptions in Discord while logging the details. A visible warning tells administrators not to rerun potentially recorded results before checking.
- Regression tests run against a real temporary SQLite database, verifying that normal games reach honours, create records/history, grant progression and that friendly challenges only grant capped XP. Additional tests verify Auto Play error feedback.
- No changes to the hybrid lane, sprites, RNG, physics, scores or animation timing.
- **Existing interrupted games:** The prior exception occurred AFTER `record_completed_session`, so `games`, `game_results` and `bowler_stats` may already contain the game, while `game_history`, achievements, progression and tournament advancement may be incomplete. Back up your DB and reconcile the result before replaying or manually awarding it.

## v2.8.5m — Hybrid Broadcast Layout
- **The full portrait lane is the main hero camera on the left**, using the original 941×1672 scene, from the neon sign and top-down deck down to the bowler standing at the foul line. The image is **letterboxed within the left panel**; we never stretch the character, distort the ball or crop away the overhead/pit in the main view.
- **Right-side stack:** top-right = an enlarged view of the real top-down pin deck; bottom-right = the real front-facing pin pit. Both camera views are cropped from the **same composited frame** as the main lane, so pins cannot mysteriously appear or disappear between the views.
- Updates both GIFs and final still images to a single cohesive **4:3 frame (1000×750)**, with smaller GIF fallbacks of **920×690** and **840×630** for upload limits. All outputs retain the same composition and aspect ratio.
- Replaces the v2.8.5l arrangement where overhead/pit cameras appeared across the top and the bowler occupied a wide lower strip. The older `broadcast_layout.py` remains in the repository for reference, but is no longer used by the match renderer.
- Retains the 21+ shot stages, the smooth one-upload GIF sequence, distinct second-ball attachment names, playback headroom, the bowler foreground, larger readable ball sprites and the existing five-stage knockdown animation.
- No new art is required. Retains existing paths: `assets/lane/gutter_saints_empty.png`, `assets/pins/overhead/`, `assets/pins/vertical/`, `assets/balls/`, and `assets/sprites/{the_dude,jesus}/`.
- **Visual-only release:** no edits to pin physics, RNG, gameplay statistics, career development, competition fixtures or scoreboard controls.
- Regression tests cover unchanged lane aspect ratio, both right-hand pinfall views, a visible Plastic spare ball on the hero lane, output fallback geometry and ongoing GIF sequencing.
- Pull the latest `main`, restart the bot, and run a two-bowler exhibition to verify Discord playback and actual displayed dimensions. A local hybrid preview was generated using the existing PNGs; no art changes were committed.

## v2.8.5l — Full-Width Discord Broadcast & Visible Ball / Pin Cameras
- **Fixes the tiny portrait preview:** Discord scales long attachments to a limited inline height. Raising the original 565×1004 source resolution does not meaningfully increase its display width. The renderer now produces a compact **9:8** broadcast canvas instead of trying ever-larger portrait GIFs.
- **Three simultaneous cinematic camera views**, composited entirely from the existing 941×1672 photographic scene: a zoomed top-down pin deck, a head-on pin pit showing impact/fallen sprites, and a full-width lower action lane showing the animated bowler and the rolling ball.
- **The Dude and Jesus remain their current sprites**, with original coordinates and existing lane/pin assets left unchanged. The composition crops camera regions but does not rewrite or stretch source PNG files on disk.
- **The overhead and head-on close-ups both follow the same game-engine pin states**, including individual standing pins and only the pins actually falling on spare shots.
- **The travelling bowling-ball sprite is visually larger** (82px to 38px on the master scene) so the light-coloured Plastic spare ball remains visible when Discord downsizes the output. Ball selection, physics path, revs and scoring do not change.
- New GIF tiers are **900×800**, **810×720**, **720×640** (all 9:8, same onscreen aspect ratio) rather than 565×1004/540×960/520×925. GIF encoder retains 160 shared colours and existing 7.5MB maximum.
- The final `Leave` still switches to the corresponding wide view: no ball remains visible after the delivery is complete, which is intentional; the ball travels only within the earlier GIF stages.
- Adds tests covering aspect ratios, overhead and pit fall consistency, second-ball Plastic sprite visibility inside the actual widened action camera, and unchanged `before/down/after` state.
- All required assets stay in `assets/lane/`, `assets/pins/`, `assets/balls/` and `assets/sprites/`. **No new PNGs or file moves needed.**
- Discord's actual preview size depends on client settings and window size. Live beta verification remains necessary.

## v2.8.5j — Second-Ball GIF Playback & Visible Pinfall
- Addresses reports that the **first ball animated fully** but a **second-ball spare showed a bowler approach followed by an apparently instant result, without visible ball travel or pin collapse**.
- Distinct, per-delivery GIF filenames (`gutter_motion_<seed>_<ball_count>.gif`) prevent stale single-play GIF attachments from being reused between balls.
- Waits for the animated GIF's duration **plus 1.5 seconds of client playback headroom**, instead of replacing it with the final result after a mere quarter-second. This accommodates Discord's attachment-loading and image-decoding delay; results remain hidden until after the moving picture should finish.
- Enlarged impact presentation from 3 to **5 GIF frames**, showing contact, tipping and fallen pins, ending with a visible held-down pose. The 10-pin overhead view and head-on rack use the same engine `before`/`down`/`after` state.
- Ball flight still uses the same Solid/Pearl/Hybrid/Urethane/Plastic artwork selected by the engine, a single GIF upload, foreground bowler and smooth visual release path. No additional PNGs or renamed files are necessary.
- Added tests for distinct second-ball attachments, sufficient GIF playback time, progressive pinfall on an actual second-ball leave, and an encoded GIF containing visible ball flight and pinfall.
- This is **presentation-only**. No bowling RNG, physics, score, career, rank or tournament progression changes.
- Beta test in Discord remains important: playback start latency and reduced-motion/autoplay preferences are client-specific. The additional 1.5-second safety margin makes Auto Play marginally longer but is meant to avoid truncating the shot before impact.

## v2.8.5i — First & Second Ball Visual Release Fix
- Fixes first-ball visual regression where the bowling ball appeared unnaturally **on top of** The Dude/Jesus character's torso after the v2.8.5g update.
- Fixes disappearing second-ball/spare travel: the actual `Plastic` PNG is present and healthy, but the old projected ball line ran directly **behind the enlarged 760px bowler** for most of the GIF. It was a projection/occlusion issue, not missing PNGs.
- Restores natural **foreground bowler compositing** and starts the released ball along the visible side of the character before smoothly easing back onto its unchanged existing lane path by the breakpoint.
- Maintains the selected Solid, Hybrid, Pearl, Urethane and Plastic sprite appearance, perspective scale, rotation and single-upload GIF playback. The shot result and scoring remain concealed until after impact.
- Adds tests for both strike and spare ball visibility, preventing a ball painted over the bowler, continuous projection and return to the original physics-derived endpoint, plus loading `plastic_cream_black.png` from the existing assets location.
- **No asset replacement is necessary.** Continue using `assets/lane/gutter_saints_empty.png`, `assets/pins/{overhead,vertical}`, `assets/balls`, and `assets/sprites/{the_dude,jesus}`.
- No changes to physics, scoring, ball selection, lane transition, rank, progression or career records. A fresh Discord exhibition remains the final visual verification step.

## v2.8.5h — Clear Scoreboard Identity and Sprite Labels
- Live scoreboard now shows **Bowler Name — Team Name** for team-v-team games and other sessions with a real scoring team.
- Solo exhibitions and player challenges no longer set the bowler's name as a fake team. When the bowler is registered on a team roster, that affiliation is shown **for display only**; otherwise the label reads **Independent**.
- Each bowler's score field identifies their animation: `🎭 Sprite: The Dude`, `🎭 Sprite: Jesus`, or `None (standard approach)`. If a character was assigned but the sprite PNGs are missing, the scoreboard explicitly shows an art-missing fallback.
- Frame-by-frame scoreboard and final totals are unchanged. Registered team affiliation does **not** count toward team totals in independent exhibition matches.
- The additional display affiliation is stored in match snapshots and restores; older saved snapshots load with no affiliation if it was not previously recorded.
- New regression tests cover real teams, solo affiliation, old duplicate-name data, sprite assignment and snapshot restoration.
- No artwork, assets or bowling physics changed. Pull and restart to apply the embed update.

## v2.8.5g — Second Delivery Ball Visibility
- Fixes the second-ball/spare presentation where The Dude or Jesus animated but the travelling ball was obscured.
- The larger character sprite used to be drawn on top of the ball and could hide its early journey. The compositor now draws the bowler first, then the released ball over the scene.
- Adds a subtle dark contrast/shadow ring around the travelling ball, particularly useful for the light cream-and-black **Plastic** spare ball against the polished wooden lane.
- Animated GIFs now derive a shared 256-colour palette from approach, travel, breakpoint and impact frames, instead of just the first approach frame. This preserves colours when a spare uses a different ball from the character's carrying pose.
- Uses the correct gameplay `event['ball_key']`: strike balls remain the bowler's chosen type; spare shots use Plastic. No physics, RNG, rank or career changes.
- Adds automated second-delivery regressions for bowler occlusion and preservation of the spare ball in the encoded GIF.
- No changes to assets or folders. Pull the source update and restart. Live Discord testing is still required.

## v2.8.5f — Smooth Motion, Fixed Jesus Frame 2 & Consistent Bowler Scale
- **Smooth playback:** an entire delivery is encoded as a short single-play animated GIF before upload. The same live Discord message changes just twice per shot (GIF, then result), rather than uploading an image for each movement frame. This is substantially smoother and reduces API-rate-limit delays.
- Timeline: 5 character approach poses → 8 travelling-ball poses → 5 breakpoint poses → 3 impact poses (21 frames; approximately **2.6 seconds** playback).
- Automatic matches pause **0.7 seconds between completed deliveries**, plus the animation and rendering/upload time. `/game_auto` continues to use a fixed pace with no delay argument.
- Game outcomes, frame results and Broadcast Director calls are shown **only after the GIF finishes**, never during the moving-ball animation.
- Jesus sprite **frame 2** now gets its missing dark ball composited next to his carrying hand at render time; the original PNG does **not** need replacing.
- All five Dude/Jesus animation frames now use a consistent **760px target body height** instead of making frame 5 visibly smaller. Feet remain anchored near the camera end of the lane.
- The GIF is computed in a worker thread; colour palette, cropping and size are optimised, with smaller-resolution alternatives if an upload would exceed 7.5 MB. If rendering fails or cinematic art is absent, the original per-stage graphics remain as fallback.
- Preserves `assets/lane/gutter_saints_empty.png`, `assets/pins/{overhead,vertical}`, `assets/balls` and `assets/sprites/{the_dude,jesus}`. **No artwork downloads or folder changes.**
- Physics, lane transition, selected balls, scorekeeping and player stats remain untouched.
- Added GIF regression tests and updated character-scale, Auto Play timing and asset-path test expectations.
- GIF playback depends on viewers' Discord animated-media preferences. A complete match in Discord is still required to confirm real-world playback/synchronisation and GIF handling.

## v2.8.5e — Auto Sprite Assignment & Live Match Controls
- **Canonical art folders only.** Use `assets/lane/gutter_saints_empty.png`, `assets/pins/overhead/*.png` and `assets/pins/vertical/*.png`. The 10 bowling balls remain in `assets/balls/` and the two 5-frame character sequences in `assets/sprites/the_dude/` and `assets/sprites/jesus/`. The older root-level artwork folder aliases are no longer used.
- **Automatic character mapping at match creation.** For two unassigned bowlers, the first is shown as **The Dude** and the second as **Jesus**, regardless of registered bowler name. Works for team games, admin exhibitions, friendly challenges and competition fixtures because it is applied in `GameSession`.
- Existing explicit character assignments are preserved, including **No Sprite**. A real bowler named TheDude/Jesus keeps the matching character. For larger matches, unassigned bowlers share/reuse the available character sprites.
- Assignments are for the current match **only**. They do not overwrite registered bowler data or affect physics, rank, gameplay RNG or career development.
- Every newly started match displays a live scoreboard with **🎳 Bowl Next Ball** and **▶ Auto Play** buttons. The live lane message is edited in place as before. The same controls appear on the administrator's Match Dashboard.
- Competing Discord-linked players and server administrators can use public live-match buttons. Non-participants and old/stale match-control messages are rejected.
- Auto Play uses a fixed presentation pace: approximately **1.25 seconds between completed deliveries**, plus the existing approach/ball-flight frames. The `/game_auto` slash command now takes **no delay argument**. `/game_bowl` remains available.
- Guards prevent the buttons, manual command and Auto Play from bowling simultaneously in the same channel. When auto completes, the existing result/awards flow remains unchanged.
- Added tests: `python -m unittest discover -s tests -p test_match_controls.py -v` and refreshed canonical asset folder tests.
- No replacement assets are required if the canonical folders are already populated. Restart the bot after updating its Python code and let Discord resync the changed `/game_auto` command.

## v2.8.5d — Asset Folder Compatibility
- Fixes the visual fallback for installs that extracted the earlier sprite ZIP at the root of `assets/`: the cinematic lane renderer now recognises `assets/Lane.png` in addition to `assets/lane/gutter_saints_empty.png`.
- Detects both `assets/overhead/` and `assets/vertical/` plus the canonical `assets/pins/overhead/` and `assets/pins/vertical/`.
- On the older root-level overhead pack, remaps the original mislabeled sprite filenames so pin artwork visually matches the correct physical pin positions. Canonical `assets/pins/overhead` numbering is left unchanged.
- Existing `assets/balls/` and `assets/sprites/the_dude/`, `assets/sprites/jesus/` already match and do not need moving.
- Cinematic render activates automatically when a valid lane image is found; restart the bot after pulling to clear the cached legacy fallback.
- Named bowlers other than The Dude or Jesus require assigning a character using admin `/bowler_sprite` (name exactly matching the registered bowler). For instance assign Benny to The Dude and Josh to Jesus for a beta test. Other bowlers retain an empty approach when no character is assigned.
- Tests added: `python -m unittest discover -s tests -p test_asset_path_compatibility.py -v`; no changes to physics or career logic.

## v2.8.5c — Scale Tuning Pass
- The Dude and Jesus approach sprites enlarged from the former 440→382px pose-height sequence to 760→650px, and maximum pose width expanded from 390px to 650px. Their feet remain anchored near the close end of the 941×1672 photographic lane.
- Settled fallen head-on pin sprites enlarged by 12%; overhead fallen sprites by 10%. Upright pins and the intermediate tipping frames retain their existing scale and locations.
- This is a visual-only change to `services/scene_renderer.py`. It does not alter lane art assets, selected ball types, scores, gameplay RNG, stat progression, or pin states.
- The v2.8.5b cinematic sprite asset ZIP remains compatible; **no replacement ZIP or sprite redownload is needed**.
- Added `tests/test_scene_scale_tuning.py` to CI to protect bowler anchors, falling-pin scale and pin-state immutability.
- Live Discord timing and mobile layout still require beta confirmation.

## v2.8.5b — Cinematic Lane, Real Pin Sprites & Synced Bowlers
- Replaces the geometric drawing with a Gutter Saints 941×1672 master background, rendered at 753×1338 for Discord. All gameplay information remains in the separate readable embed beneath the image.
- Two independent pin decks: numbered dirty/scuffed 10-pin overhead view, plus realistic head-on pins in the lane pit. Both read the same event's before/down/after lists.
- Impact has three visual states: upright → leaning → fallen. Only pins in event.down animate; event.after alone controls the settled leave. Reset racks and subsequent spares are driven by the engine, never by a guessed visual result.
- The Dude and Jesus use the existing five-frame approach animations, scaled to the near end of the new photographic lane. Their follow-through pose stays visible during ball travel, breakpoint, impact and result.
- The real selected Solid/Pearl/Hybrid/Urethane/Plastic ball follows the existing engine-rendered trajectory on the new lane and rotates according to the derived rev rate. No scoring/physics/rank/stat changes.
- Existing `lane_card` and Discord message-editing pathways automatically use the new scene when its image exists. If absent, the old lane renderer remains available.
- Install the required graphic files from **Gutter_Saints_v2.8.5b_Cinematic_Lane_Assets.zip** by extracting its `assets/` directory next to `bot.py`. This supersedes the earlier ball, bowler and pin sprite ZIPs and corrects the initial overhead sprite file numbering.
- The generated photo background is intentionally pin-free; actual pins are composited over it at render time.
- Regression tests: `python -m unittest discover -s tests -p test_scene_renderer.py -v`.
- Discord's message-edit rate limits can make frame playback slower than the configured pause. Beta-test a full match before using it for a tournament.

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