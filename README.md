# Gutter Saints Bowling Bot v2.7.5 — Simulation & Balance Lab

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

## Main UI
Use `/menu` for players and `/director` for Tournament Director. The original bot remains preserved on `legacy-v0.1`.

## Media
GIF/media URLs live in `assets/media.json`. Audio mappings live in `assets/audio.json`. Local copyrighted assets are intentionally not bundled.

## Data safety
The live SQLite DB, backups, exports, generated lane cards, `.env`, caches and local sound files remain ignored by Git.
\n\n## v2.7.5 Simulation & Balance Lab\nAdmin-only /simulation_lab runs 1,000–100,000 headless games per build. Controlled tests cover Rank 20 vs 30, Accuracy vs Spin, handedness and Nerves, across all oil patterns and fresh/transitioned/burnt starting lanes. Reports average, 95% CI, strike/spare rates, 200+/250+/300 rates and dominance warnings, with optional CSV export. Deterministic seeds make balance changes regression-testable.\n