# Gutter Saints Bowling Bot v2.6 — Broadcast Edition

A Discord bowling game and tournament platform with persistent SQLite careers, teams, tournament brackets, achievements, progression, graphical lane cards, contextual commentary, GIF hooks and optional voice-channel sound effects.

## Setup
1. Install Python 3.13+.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set `DISCORD_TOKEN` (optionally `GUILD_ID` for fast guild command sync).
4. For voice effects, install FFmpeg and place your licensed audio files in `assets/sounds/` using names from `assets/audio.json`.
5. Run `python bot.py`.

## Main UI
Use `/menu` for the public menu. Players can view their bowler, stats and achievements. Admins can open the admin console for bowlers, teams, tournaments, matches, records and settings.

Use `/director` for the Tournament Director dashboard. Recovery uses persisted match snapshots, including Undo Last Ball and Restore Match.

## Broadcast presentation
`/lane_view` renders the current lane and standing pins. `assets/media.json` contains GIF/media URL pools. `/audio_join` connects to the invoking user's voice channel; audio is optional and requires FFmpeg/PyNaCl.

## Data safety
The live SQLite database, backups, generated exports, lane cards, `.env`, Python caches and local sound files are ignored by Git. Never commit your Discord token.

## Legacy
The original v0.1 bot is preserved on branch `legacy-v0.1`.
