import os
import json
import random

from dataclasses import dataclass, asdict, field
from typing import List, Dict, Tuple, Optional
from dotenv import load_dotenv

import discord
from discord import app_commands
from discord.ext import commands

DATA_FILE = "bowlers.json"

# ---- Discord bot early setup (must exist before using @tree.command) ----
intents = discord.Intents(
    guilds=True,
    members=True,  # you use member join/leave logs
    messages=True,
    message_content=False
)
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


# =========================
# PERSISTENCE
# =========================
def load_db():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "bowlers": {},
        "owners": {},
        "teams": {},
        "games": {},
        "guild_settings": {},
        "leagues": {}  # <--- Added for leagues
    }


def save_db():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DB, f, indent=2)


DB = load_db()


def guild_key(guild_id: int) -> str:
    return str(guild_id)


def get_guild_settings(guild_id: int) -> dict:
    gk = guild_key(guild_id)
    if gk not in DB["guild_settings"]:
        DB["guild_settings"][gk] = {"log_channel_id": None, "admin_gate": True}
    return DB["guild_settings"][gk]


async def send_log(bot: commands.Bot, guild_id: int, message: str):
    try:
        gs = get_guild_settings(guild_id)
        chan_id = gs.get("log_channel_id")
        if not chan_id:
            return
        chan = bot.get_channel(chan_id)
        if chan:
            await chan.send(message[:1900])
    except Exception:
        pass



# =========================
# MODEL
# =========================
STATS_KEYS = ["accuracy", "rank", "style", "flair", "consistency", "spin", "nerves"]
ALL_PINS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


@dataclass
class Bowler:
    owner_id: int
    name: str
    handedness: str = "R"
    accuracy: int = 0
    rank: int = 0
    style: int = 0
    flair: int = 0
    consistency: int = 0
    spin: int = 0
    nerves: int = 0

    def to_dict(self): return asdict(self)

    @staticmethod
    def from_dict(d): return Bowler(**d)


@dataclass
class Team:
    name: str
    captain: Optional[str] = None  # bowler name of the captain
    members: List[str] = field(default_factory=list)
    order: List[str] = field(default_factory=list)

    def to_dict(self): return asdict(self)

    @staticmethod
    def from_dict(d): return Team(**d)


@dataclass
class FrameState:
    frame: int = 1
    ball: int = 1
    remaining: int = 10
    tenth_bonus1: bool = False
    tenth_bonus2: bool = False
    # NEW: track if current frame started with a split leave
    split_pending: bool = False

@dataclass
class BowlerGame:
    bowler_name: str
    rolls: List[int] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    frames_done: int = 0
    frame_state: FrameState = field(default_factory=FrameState)

    def to_dict(self):
        return {
            "bowler_name": self.bowler_name,
            "rolls": self.rolls,
            "symbols": self.symbols,
            "frames_done": self.frames_done,
            "frame_state": asdict(self.frame_state)
        }

    @staticmethod
    def from_dict(d):
        bg = BowlerGame(bowler_name=d["bowler_name"])
        bg.rolls = list(d.get("rolls", []))
        bg.symbols = list(d.get("symbols", []))
        bg.frames_done = d.get("frames_done", 0)
        fs = d.get("frame_state", {})
        bg.frame_state = FrameState(**fs) if fs else FrameState()
        return bg


@dataclass
class GameState:
    guild_id: int
    lane: str = "normal"
    pressure: str = "none"
    teamA: str = ""
    teamB: str = ""
    orderA: List[str] = field(default_factory=list)
    orderB: List[str] = field(default_factory=list)
    frame: int = 1
    turn_tracker: List[Tuple[str, str]] = field(default_factory=list)
    turn_i: int = 0
    players: Dict[str, BowlerGame] = field(default_factory=dict)
    is_active: bool = True
    finalized: bool = False  # <-- NEW

    def to_dict(self):
        return {
            "guild_id": self.guild_id,
            "lane": self.lane,
            "pressure": self.pressure,
            "teamA": self.teamA,
            "teamB": self.teamB,
            "orderA": self.orderA, "orderB": self.orderB,
            "frame": self.frame,
            "turn_tracker": self.turn_tracker,
            "turn_i": self.turn_i,
            "players": {k: v.to_dict() for k, v in self.players.items()},
            "is_active": self.is_active,
            "finalized": self.finalized  # <-- NEW
        }

    @staticmethod
    def from_dict(d):
        gs = GameState(guild_id=d["guild_id"])
        gs.lane = d.get("lane", "normal")
        gs.pressure = d.get("pressure", "none")
        gs.teamA = d.get("teamA", "")
        gs.teamB = d.get("teamB", "")
        gs.orderA = list(d.get("orderA", []))
        gs.orderB = list(d.get("orderB", []))
        gs.frame = d.get("frame", 1)
        gs.turn_tracker = [tuple(x) for x in d.get("turn_tracker", [])]
        gs.turn_i = d.get("turn_i", 0)
        gs.players = {k: BowlerGame.from_dict(v) for k, v in d.get("players", {}).items()}
        gs.is_active = d.get("is_active", True)
        gs.finalized = d.get("finalized", False)  # <-- NEW
        return gs


# ---------- AWARD / STATS MODELS ----------

@dataclass
class BowlerSeasonStats:
    games: int = 0
    total_pins: int = 0
    high_game: int = 0
    # Keep last N game totals to compute best 3-game series (“The Dude Abides Series”)
    recent_games: List[int] = field(default_factory=list)  # we’ll cap to 12 for sanity
    high_series_3: int = 0

    strikes: int = 0
    spares: int = 0
    frames: int = 0
    clean_games: int = 0

    # Approximations
    pocket_hits: int = 0  # strike or 9 on first ball
    pocket_attempts: int = 0  # frames bowled (up to 10 per game)

    splits_converted: int = 0  # count of split-ish spares (7/..0/)
    splits_attempted: int = 0

    longest_strike_run: int = 0  # turkey metric

    worst_game: int = 10_000  # track minimum single-game (for Booby)

    def to_dict(self): return asdict(self)

    @staticmethod
    def from_dict(d): return BowlerSeasonStats(**d)


@dataclass
class TeamSeasonStats:
    games: int = 0
    total_pins: int = 0
    high_game: int = 0
    series_running: int = 0  # cumulative across games
    high_series: int = 0  # best “match series” (sum in a fixture)

    def to_dict(self): return asdict(self)

    @staticmethod
    def from_dict(d): return TeamSeasonStats(**d)


def get_stats_bucket():
    if "stats" not in DB:
        DB["stats"] = {"bowlers": {}, "teams": {}}
    return DB["stats"]


def get_bowler_stats(name: str) -> BowlerSeasonStats:
    bucket = get_stats_bucket()
    rec = bucket["bowlers"].get(name)
    return BowlerSeasonStats.from_dict(rec) if rec else BowlerSeasonStats()


def save_bowler_stats(name: str, st: BowlerSeasonStats):
    bucket = get_stats_bucket()
    bucket["bowlers"][name] = st.to_dict()
    save_db()


def get_team_stats(team: str) -> TeamSeasonStats:
    bucket = get_stats_bucket()
    rec = bucket["teams"].get(team)
    return TeamSeasonStats.from_dict(rec) if rec else TeamSeasonStats()


def save_team_stats(team: str, st: TeamSeasonStats):
    bucket = get_stats_bucket()
    bucket["teams"][team] = st.to_dict()
    save_db()

# =========================
# BOWLERS (MULTI-NAME)
# =========================
@tree.command(description="Create a new bowler with a unique name")
@app_commands.describe(name="Unique name (global)", handedness="Right or Left")
@app_commands.choices(handedness=[
    app_commands.Choice(name="Right", value="R"),
    app_commands.Choice(name="Left", value="L")
])
async def bowler_create(interaction: discord.Interaction, name: str, handedness: app_commands.Choice[str]):
    name = name.strip()
    if not name or len(name) > 24:
        await interaction.response.send_message("Pick a concise name (1–24 chars).", ephemeral=True); return
    if name in DB["bowlers"]:
        await interaction.response.send_message("That bowler name is already taken.", ephemeral=True); return
    b = Bowler(owner_id=interaction.user.id, name=name, handedness=handedness.value)
    DB["bowlers"][name] = b.to_dict()
    rec = owner_record(interaction.user.id)
    rec["owned"].append(name)
    if rec["active"] is None: rec["active"] = name
    save_db()
    await interaction.response.send_message(f"✅ Created **{name}** ({'Righty' if b.handedness=='R' else 'Lefty'}).", ephemeral=True)

@tree.command(description="Set your active bowler")
async def bowler_use(interaction: discord.Interaction, name: str):
    err = assert_owner_bowler(interaction, name)
    if err: await interaction.response.send_message(err, ephemeral=True); return
    rec = owner_record(interaction.user.id)
    rec["active"] = name
    save_db()
    await interaction.response.send_message(f"🎳 Active bowler set to **{name}**.", ephemeral=True)

@tree.command(description="Adjust a stat by −10…+10 (clamped to 0–100)")
@app_commands.describe(stat="Which stat", delta="−10…+10", name="Optional; defaults to active")
@app_commands.choices(stat=[app_commands.Choice(name=s, value=s) for s in STATS_KEYS])
async def bowler_modstat(
    interaction: discord.Interaction,
    stat: app_commands.Choice[str],
    delta: app_commands.Range[int, -10, 10],
    name: Optional[str] = None
):
    rec = owner_record(interaction.user.id)
    name = name or rec["active"]
    if not name:
        await interaction.response.send_message("No active bowler set.", ephemeral=True); return
    err = assert_owner_bowler(interaction, name)
    if err:
        await interaction.response.send_message(err, ephemeral=True); return
    b = get_bowler_by_name(name)
    cur = getattr(b, stat.value)
    newv = max(0, min(100, cur + int(delta)))
    setattr(b, stat.value, newv)
    DB["bowlers"][name] = b.to_dict()
    save_db()
    await interaction.response.send_message(
        f"✅ **{name}**: **{stat.value}** {cur} → **{newv}** (Δ {delta}).", ephemeral=True
    )

def assert_owner_bowler(inter: discord.Interaction, name: str) -> Optional[str]:
    b = get_bowler_by_name(name)
    if not b:
        return "That bowler doesn’t exist."
    if b.owner_id != inter.user.id:
        return "You don’t own that bowler."
    return None

@tree.command(description="Show a bowler's stats (defaults to your active)")
async def bowler_show(interaction: discord.Interaction, name: Optional[str] = None):
    rec = owner_record(interaction.user.id)
    name = name or rec["active"]
    if not name: await interaction.response.send_message("No active bowler.", ephemeral=True); return
    b = get_bowler_by_name(name)
    if not b: await interaction.response.send_message("That bowler doesn’t exist.", ephemeral=True); return
    carry = max(0, b.rank + b.spin)
    embed = discord.Embed(title=f"{b.name} — Profile", color=0x2ecc71)
    embed.add_field(name="Owner", value=f"<@{b.owner_id}>")
    embed.add_field(name="Handedness", value="Right" if b.handedness == 'R' else "Left")
    embed.add_field(name="Carry bonus", value=f"{carry}%", inline=False)
    stats_text = "\n".join([f"**{k.capitalize()}**: {getattr(b, k)}%" for k in STATS_KEYS])
    embed.add_field(name="Stats", value=stats_text, inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(description="Debug: show a bowler's 7 core stats (defaults to your active)")
async def debug_stats(interaction: discord.Interaction, name: Optional[str] = None):
    # Resolve bowler (default to active)
    rec = owner_record(interaction.user.id)
    name = name or rec.get("active")
    if not name:
        await interaction.response.send_message("No bowler specified and no active bowler set.", ephemeral=True)
        return

    b = get_bowler_by_name(name)
    if not b:
        await interaction.response.send_message("That bowler doesn’t exist.", ephemeral=True)
        return

    team = team_of_bowler(name) or "—"
    embed = discord.Embed(title=f"🛠️ Debug — {b.name}", color=0x95a5a6)
    embed.add_field(name="Team", value=team, inline=True)
    embed.add_field(name="Handedness", value=("Right" if b.handedness == "R" else "Left"), inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=False)

    # 7 core stats
    embed.add_field(name="Accuracy", value=f"{b.accuracy}", inline=True)
    embed.add_field(name="Rank", value=f"{b.rank}", inline=True)
    embed.add_field(name="Style", value=f"{b.style}", inline=True)
    embed.add_field(name="Flair", value=f"{b.flair}", inline=True)
    embed.add_field(name="Consistency", value=f"{b.consistency}", inline=True)
    embed.add_field(name="Spin", value=f"{b.spin}", inline=True)
    embed.add_field(name="Nerves", value=f"{b.nerves}", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(description="List your bowlers")
async def bowler_my(interaction: discord.Interaction):
    rec = owner_record(interaction.user.id)
    if not rec["owned"]:
        await interaction.response.send_message("You have no bowlers. Use `/bowler create`.", ephemeral=True);
        return
    lines = [f"- **{n}**" + (" *(active)*" if n == rec["active"] else "") for n in rec["owned"]]
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


# ----- LEAGUE MODELS -----
@dataclass
class LeagueTeamStats:
    team: str
    wins: int = 0
    draws: int = 0
    losses: int = 0

    def to_dict(self): return asdict(self)

    @staticmethod
    def from_dict(d): return LeagueTeamStats(**d)


@dataclass
class League:
    name: str
    teams: List[LeagueTeamStats] = field(default_factory=list)

    def to_dict(self):
        return {
            "name": self.name,
            "teams": [t.to_dict() for t in self.teams]
        }

    @staticmethod
    def from_dict(d):
        league = League(name=d["name"])
        league.teams = [LeagueTeamStats.from_dict(t) for t in d.get("teams", [])]
        return league


def get_league_by_name(name: str) -> Optional[League]:
    rec = DB.get("leagues", {}).get(name)
    return League.from_dict(rec) if rec else None


def save_league(league: League):
    if "leagues" not in DB:
        DB["leagues"] = {}
    DB["leagues"][league.name] = league.to_dict()
    save_db()


def league_record_result(teamA: str, teamB: str, scoreA: int, scoreB: int):
    for league in DB.get("leagues", {}).values():
        l = League.from_dict(league)
        ta = next((ts for ts in l.teams if ts.team == teamA), None)
        tb = next((ts for ts in l.teams if ts.team == teamB), None)
        if ta and tb:
            if scoreA > scoreB:
                ta.wins += 1
                tb.losses += 1
            elif scoreA < scoreB:
                tb.wins += 1
                ta.losses += 1
            else:
                ta.draws += 1
                tb.draws += 1
            save_league(l)


# =========================
# RNG / SHOT ENGINE
# =========================
def roll_d20(): return random.randint(1, 20)


def jitter_amount(consistency_pct: int) -> float:
    base = 3.0
    shrink = max(0.0, min(0.60, 0.05 * consistency_pct))
    return base * (1.0 - shrink)


def uniform_jitter(width: float) -> float:
    return random.uniform(-width, width)


def advantage_if_flair(d: int, flair_pct: int) -> int:
    if flair_pct > 0 and (d == 1 or d == 20):
        return max(d, roll_d20())
    return d


# Tiny pooled boost: each stat point = +0.01% (= 0.0001 SQ)
MICRO_BONUS_PER_POINT = 0.0001  # 0.01% per 1 point; 700 points total => +0.07 SQ

def stats_to_sq(b: Bowler, clutch: bool) -> float:
    # Core SQ from main stats (unchanged)
    sq = 0.15 * min(b.accuracy, 50) + 0.05 * min(b.rank, 50) + 0.1 * b.style
    if clutch:
        sq += 2.0 if b.nerves >= 0 else -2.0

    # NEW: pooled micro-bonus across ALL seven stats
    total_stats = (
        b.accuracy + b.rank + b.style +
        b.flair + b.consistency + b.spin + b.nerves
    )
    micro_bonus = total_stats * MICRO_BONUS_PER_POINT  # max +0.07 SQ at 700 total

    return sq + micro_bonus


def lane_mod(lane: str) -> float:
    lane = (lane or "normal").lower()
    return 0.5 if lane == "fresh" else (-1.0 if lane == "burnt" else 0.0)


def spare_shape_mod(remaining_pins: List[int]) -> float:
    if not remaining_pins: return 0.0
    if len(remaining_pins) == 1: return 3.0
    return -0.5 * (len(remaining_pins) - 1)


def tier_from_sq(SQ: float) -> str:
    # Hard-squeeze the top: anything >23 behaves like 23.
    s = max(0.0, min(SQ, 23.0))
    if s <= 6:  return "t0"
    if s <= 10: return "t1"
    if s <= 13: return "t2"
    if s <= 17: return "t3"   # 13–17  → t3
    if s <= 20: return "t4"   # 17–20  → t4
    return "t5"               # 20–23+ → t5 (no t6 in normal play)


PATTERNS_R = {
    "t0": [([1, 2, 4, 7], 20), ([1, 3, 6, 10], 20), ([7, 10], 15), ([1, 2, 10], 15), ([1, 3, 5, 9], 15), ([], 5)],
    "t1": [([1, 2, 4], 25), ([1, 3, 6], 25), ([2, 4, 5, 8], 20), ([3, 6, 10], 15), ([1, 2, 10], 15)],
    "t2": [([4, 6, 7], 20), ([2, 4, 10], 20), ([3, 6, 7], 20), ([2, 5, 8], 20), ([5, 7], 20)],
    "t3": [([10], 40), ([7], 25), ([8], 20), ([4, 10], 10), ([], 5)],
    "t4": [([], 40), ([10], 30), ([7], 15), ([8], 10), ([7, 10], 5)],
    "t5": [([],    60),([10],  22),([7],    8),([8],    5),([7,10], 5)],
}


def weighted_choice(items: List[Tuple[object, int]]):
    total = sum(w for _, w in items)
    r = random.uniform(0, total);
    upto = 0
    for item, w in items:
        if upto + w >= r: return item
        upto += w
    return items[-1][0]


def mirror_lefty(pins: List[int]) -> List[int]:
    swap = {7: 10, 10: 7, 2: 3, 3: 2, 4: 6, 6: 4}
    return [swap.get(p, p) for p in pins]


def sample_pattern_from_tier(tier: str, handed: str) -> List[int]:
    pins = list(weighted_choice(PATTERNS_R[tier]))
    if handed.upper() == "L": pins = mirror_lefty(pins)
    return sorted(pins)


def carry_upgrade(standing: List[int], b: Bowler) -> List[int]:
    if len(standing) == 1 and standing[0] in (7, 10, 8, 5):
        carry_pct = max(0, b.rank + b.spin)
        if random.randint(1, 100) <= carry_pct: return []
    return standing


def spare_conversion_chance(SQ: float, remaining_cnt: int, b: Bowler) -> int:
    if remaining_cnt == 1:
        base = 50 if SQ <= 9 else 70 if SQ <= 13 else 85 if SQ <= 16 else 92 if SQ <= 19 else 97
    else:
        base = max(5, 95 - remaining_cnt * 12)
    t = tier_from_sq(SQ)
    adjust = {
        "t0": -15, "t1": -10, "t2": -5,
        "t3": 0, "t4": +5, "t5": +10
    }[t]
    p = base + adjust
    p += int(0.5 * b.accuracy + 0.25 * b.consistency)
    return int(max(1, min(99, p)))


def first_ball_roll(b: Bowler, lane: str, pressure: str) -> Tuple[List[int], dict]:
    d = advantage_if_flair(roll_d20(), b.flair)
    jit = uniform_jitter(jitter_amount(b.consistency))
    SQ = d + stats_to_sq(b, clutch=(pressure == "clutch")) + lane_mod(lane) + jit
    tier = tier_from_sq(SQ)
    standing = sample_pattern_from_tier(tier, b.handedness)
    standing = carry_upgrade(standing, b)
    meta = {"d20": d, "SQ": round(SQ, 2), "tier": tier, "jitter": round(jit, 2)}
    return standing, meta


def spare_ball_roll(b: Bowler, remaining_cnt: int) -> Tuple[int, dict]:
    d = advantage_if_flair(roll_d20(), b.flair)
    jit = uniform_jitter(jitter_amount(b.consistency))
    SQ = d + stats_to_sq(b, clutch=False) + spare_shape_mod(list(range(remaining_cnt))) + jit
    p = spare_conversion_chance(SQ, remaining_cnt, b)
    made = random.randint(1, 100) <= p
    knocked = remaining_cnt if made else 0
    meta = {"d20": d, "SQ": round(SQ, 2), "make%": p, "jitter": round(jit, 2)}
    return knocked, meta


# =========================
# SCORING
# =========================
def score_bowling(rolls: List[int]) -> Tuple[int, List[Optional[int]], List[str]]:
    total = 0
    frame_scores: List[Optional[int]] = [None] * 10
    symbols: List[str] = [""] * 10
    i = 0
    for f in range(10):
        if i >= len(rolls):
            break
        if rolls[i] == 10:
            if i + 2 < len(rolls):
                total += 10 + rolls[i + 1] + rolls[i + 2]
                frame_scores[f] = total
            symbols[f] = "X"
            i += 1
        else:
            if i + 1 >= len(rolls):
                r1 = rolls[i]
                symbols[f] = f"{r1}-"
                break
            r1, r2 = rolls[i], rolls[i + 1]
            frame_sum = r1 + r2
            if frame_sum == 10:
                if i + 2 < len(rolls):
                    total += 10 + rolls[i + 2]
                    frame_scores[f] = total
                symbols[f] = f"{r1}/"
            else:
                total += frame_sum
                frame_scores[f] = total
                s1 = str(r1) if r1 > 0 else "-"
                s2 = str(r2) if r2 > 0 else "-"
                symbols[f] = f"{s1}{s2}"
            i += 2

    idx = 0
    for f in range(9):
        if idx >= len(rolls): break
        if rolls[idx] == 10:
            idx += 1
        else:
            idx += 2
    if idx < len(rolls):
        tenth = rolls[idx:]
        if len(tenth) == 1:
            symbols[9] = "X" if tenth[0] == 10 else (str(tenth[0]) if tenth[0] > 0 else "-")
        elif len(tenth) == 2:
            a, b = tenth[0], tenth[1]
            if a == 10:
                s = "X" + ("X" if b == 10 else (str(b) if b > 0 else "-"))
                symbols[9] = s
            else:
                if a + b == 10:
                    symbols[9] = f"{a}/"
                else:
                    s1 = str(a) if a > 0 else "-"
                    s2 = str(b) if b > 0 else "-"
                    symbols[9] = f"{s1}{s2}"
        else:
            a, b, c = tenth[0], tenth[1], tenth[2]
            s = ""
            s += "X" if a == 10 else (str(a) if a > 0 else "-")
            s += "X" if b == 10 else ("/" if (a != 10 and a + b == 10) else (str(b) if b > 0 else "-"))
            s += "X" if c == 10 else (
                "/" if ((a == 10 and b != 10 and b + c == 10) or (a != 10 and a + b == 10 and c == 10)) else (
                    str(c) if c > 0 else "-"))
            symbols[9] = s[:3]
    return (frame_scores[9] or 0), frame_scores, symbols


# =========================
# HELPERS: ownership, lookups, games
# =========================

@tree.command(
    name="team-awards",
    description="Show prize-tracking stats for team members"
)
@app_commands.describe(team="Exact team name")
async def awards_team_members(interaction: discord.Interaction, team: str):
    # Local, safe helper — avoid relying on global pct()
    def safe_pct(a: int, b: int) -> float:
        try:
            return (100.0 * float(a) / float(b)) if b else 0.0
        except Exception:
            return 0.0

    t = get_team_by_name(team)
    if not t:
        await interaction.response.send_message("No such team.", ephemeral=True)
        return

    if not t.members:
        await interaction.response.send_message(f"**{team}** has no members.", ephemeral=True)
        return

    rows = []
    for name in t.members:
        st = get_bowler_stats(name)
        b  = get_bowler_by_name(name)

        acc    = b.accuracy    if b else 0
        rank   = b.rank        if b else 0
        style  = b.style       if b else 0
        flair  = b.flair       if b else 0
        cons   = b.consistency if b else 0
        spin   = b.spin        if b else 0
        nerves = b.nerves      if b else 0

        acc_pct   = safe_pct(st.pocket_hits, st.pocket_attempts)
        spare_pct = safe_pct(st.spares, st.frames)
        turkeys   = st.longest_strike_run // 3
        worst     = st.worst_game if st.worst_game != 10_000 else 0
        mvp_score = st.total_pins + st.strikes * 5 + st.spares * 2 + st.clean_games * 10

        rows.append({
            "name": name,
            "games": st.games,
            "pins": st.total_pins,
            "high_game": st.high_game,
            "high_series": st.high_series_3,
            "strikes": st.strikes,
            "spares": st.spares,
            "clean": st.clean_games,
            "acc_pct": acc_pct,
            "spare_pct": spare_pct,
            "turkeys": turkeys,
            "splits_conv": st.splits_converted,
            "worst": worst,
            "acc": acc, "rank": rank, "style": style, "flair": flair,
            "cons": cons, "spin": spin, "nerves": nerves,
            "mvp_score": mvp_score,
        })

    if not rows:
        await interaction.response.send_message(f"No tracked bowlers found on **{team}**.", ephemeral=True)
        return

    rows.sort(key=lambda r: r["mvp_score"], reverse=True)

    lines = []
    for r in rows:
        lines.append(
            f"**{r['name']}**\n"
            f"• Games {r['games']} | Pins {r['pins']} | HighG {r['high_game']} | HighS {r['high_series']}\n"
            f"• Strikes {r['strikes']} | Spares {r['spares']} | Clean {r['clean']}\n"
            f"• Pocket% {r['acc_pct']:.1f}% | Spare% {r['spare_pct']:.1f}% | Turkeys {r['turkeys']} | Splits {r['splits_conv']} | Worst {r['worst']}\n"
            f"• Stats — ACC {r['acc']} | RANK {r['rank']} | STYLE {r['style']} | FLAIR {r['flair']} | CONS {r['cons']} | SPIN {r['spin']} | NERV {r['nerves']}\n"
        )

    embed = discord.Embed(
        title=f"Individual Prize Stats — {team}",
        color=0x9b59b6,
        description=f"Bowlers: **{len(rows)}**  •  Sorted by MVP score"
    )

    MAX = 1024
    parts, buf, cur = [], [], 0
    for ln in lines:
        add = (2 if buf else 0) + len(ln)
        if cur + add > MAX:
            parts.append("\n\n".join(buf))
            buf, cur = [ln], len(ln)
        else:
            if buf: cur += 2
            buf.append(ln); cur += len(ln)
    if buf:
        parts.append("\n\n".join(buf))

    if len(parts) > 24:
        visible = parts[:24]
        hidden = len(parts) - 24
        parts = visible + [f"…and **{hidden}** more sections not shown. Narrow your query or export."]

    for i, block in enumerate(parts, 1):
        embed.add_field(name=f"{team} Bowlers ({i})", value=(block[:1024] if block else "—"), inline=False)

    await interaction.response.send_message(embed=embed)




def owner_record(user_id: int) -> Dict:
    u = str(user_id)
    if u not in DB["owners"]:
        DB["owners"][u] = {"active": None, "owned": []}
    return DB["owners"][u]

def get_game_archive_bucket():
    """Ensure and return the archive bucket for finished games."""
    if "games_archive" not in DB:
        DB["games_archive"] = {}
    return DB["games_archive"]

def archive_game(gs: GameState):
    """Append a completed GameState to the guild's archive."""
    bucket = get_game_archive_bucket()
    gk = str(gs.guild_id)
    bucket.setdefault(gk, []).append(gs.to_dict())
    save_db()

def archived_games_for_guild(guild_id: int) -> List[dict]:
    bucket = get_game_archive_bucket()
    return list(bucket.get(str(guild_id), []))

def build_game_result_embed(gs: GameState) -> discord.Embed:
    """Build an embed with scoreboard + result + MVP + head-to-head for a completed GameState."""
    # Per-bowler + team totals
    per_bowler_totals = {name: score_bowling(bg.rolls)[0] for name, bg in gs.players.items()}
    totA = sum(per_bowler_totals.get(n, 0) for n in gs.orderA)
    totB = sum(per_bowler_totals.get(n, 0) for n in gs.orderB)

    # Winner text
    if totA > totB:
        result_text = f"🏆 **Winner:** {gs.teamA} — {totA} to {totB}"
    elif totB > totA:
        result_text = f"🏆 **Winner:** {gs.teamB} — {totB} to {totA}"
    else:
        result_text = f"🤝 **Tie:** {gs.teamA} {totA} — {gs.teamB} {totB}"

    # MVP (highest game)
    top_score = max(per_bowler_totals.values()) if per_bowler_totals else 0
    mvps = [n for n, sc in per_bowler_totals.items() if sc == top_score] if top_score > 0 else []

    def team_of(bname: str) -> str:
        return gs.teamA if bname in gs.orderA else (gs.teamB if bname in gs.orderB else "?")

    mvp_text = ", ".join(f"**{n}** ({team_of(n)}) — {top_score}" for n in mvps) if mvps else "—"

    # Head-to-head recap
    results = pretty_head_to_head_results(gs)

    # Scoreboard + details
    embed = pretty_scoreboard(gs)
    embed.title = f"Archived Game — {gs.teamA} vs {gs.teamB}"
    embed.add_field(name="Result", value=result_text, inline=False)
    embed.add_field(name="MVP (highest game)", value=mvp_text, inline=False)
    if results:
        embed.add_field(
            name="Head-to-Head Results",
            value=(results if len(results) <= 1024 else results[:1015] + "…"),
            inline=False
        )
    embed.set_footer(text="From archive")
    return embed

def finalize_and_build_game_embed(gs: GameState) -> discord.Embed:
    """
    If the game is not finalized, finalize it (archive + stats + league).
    Then build and return the full 'result' embed (scoreboard + result + MVP + H2H).
    Safe to call multiple times; it only finalizes once.
    """
    # Per-bowler & team totals for result/MVP text
    per_bowler_totals = {name: score_bowling(bg.rolls)[0] for name, bg in gs.players.items()}
    totA = sum(per_bowler_totals.get(n, 0) for n in gs.orderA)
    totB = sum(per_bowler_totals.get(n, 0) for n in gs.orderB)

    # Winner / tie
    if totA > totB:
        result_text = f"🏆 **Winner:** {gs.teamA} — {totA} to {totB}"
    elif totB > totA:
        result_text = f"🏆 **Winner:** {gs.teamB} — {totB} to {totA}"
    else:
        result_text = f"🤝 **Tie:** {gs.teamA} {totA} — {gs.teamB} {totB}"

    # MVP
    top_score = max(per_bowler_totals.values()) if per_bowler_totals else 0
    mvps = [n for n, sc in per_bowler_totals.items() if sc == top_score] if top_score > 0 else []
    def team_of(bname: str) -> str:
        return gs.teamA if bname in gs.orderA else (gs.teamB if bname in gs.orderB else "?")
    mvp_text = ", ".join(f"**{n}** ({team_of(n)}) — {top_score}" for n in mvps) if mvps else "—"

    # Finalize once
    if not gs.finalized:
        gs.is_active = False  # should already be false when last ball thrown
        set_active_game(gs)

        # Archive
        archive_game(gs)

        # League + season awards
        league_record_result(gs.teamA, gs.teamB, totA, totB)
        finalize_stats_for_game(gs)

        # Mark finalized
        gs.finalized = True
        set_active_game(gs)

    # Build the nice embed (scoreboard + sections)
    results = pretty_head_to_head_results(gs)
    embed = pretty_scoreboard(gs)  # footer will say "Game complete" once frame>10
    embed.title = f"Game — {gs.teamA} vs {gs.teamB} (Frame 10)"
    embed.add_field(name="Result", value=result_text, inline=False)
    embed.add_field(name="MVP (highest game)", value=mvp_text, inline=False)
    if results:
        embed.add_field(
            name="Head-to-Head Results",
            value=(results if len(results) <= 1024 else results[:1015] + "…"),
            inline=False
        )
    return embed

@tree.command(description="Show the most recent archived game for this server")
async def game_last(interaction: discord.Interaction):
    gid = interaction.guild_id or 0
    games = archived_games_for_guild(gid)
    if not games:
        await interaction.response.send_message("No archived games found for this server.", ephemeral=True)
        return

    # Most recent is the last appended → treat that as index 1 for users
    rec = games[-1]
    gs = GameState.from_dict(rec)

    # Make sure we don’t mutate anything; just render
    embed = build_game_result_embed(gs)
    embed.add_field(name="Archive Slot", value="Newest (index **1**)", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(description="List archived games for this server (newest first)")
async def games_list(
    interaction: discord.Interaction,
    page: app_commands.Range[int, 1, 1000] = 1,
    per_page: app_commands.Range[int, 5, 20] = 10
):
    gid = interaction.guild_id or 0
    games = archived_games_for_guild(gid)
    total = len(games)
    if total == 0:
        await interaction.response.send_message(
            "No archived games found for this server.",
            ephemeral=True
        )
        return

    # Newest first (index 1 = newest)
    # Slice the "view" from the end of the list.
    import math
    total_pages = max(1, math.ceil(total / per_page))
    if page > total_pages:
        await interaction.response.send_message(
            f"Only **{total_pages}** page(s) available. Try a smaller page number.",
            ephemeral=True
        )
        return

    # Convert page/per_page (1=newest) into list slice on reversed order
    # Build a list of (index_from_newest, GameState)
    indexed = []
    for i, rec in enumerate(reversed(games), start=1):
        try:
            gs = GameState.from_dict(rec)
            indexed.append((i, gs))
        except Exception:
            # Skip any malformed archive entry
            continue

    start = (page - 1) * per_page
    end = min(start + per_page, len(indexed))
    view = indexed[start:end]

    # Format each row: "  1. TeamA 742 — 709 TeamB | 3v3"
    lines = []
    for idx, gs in view:
        # Totals
        totA = sum(score_bowling(gs.players.get(n, BowlerGame(bowler_name=n)).rolls)[0] for n in gs.orderA)
        totB = sum(score_bowling(gs.players.get(n, BowlerGame(bowler_name=n)).rolls)[0] for n in gs.orderB)
        vs = f"{len(gs.orderA)}v{len(gs.orderB)}"
        lines.append(f"{idx:>3}. {gs.teamA} {totA} — {totB} {gs.teamB}  |  {vs}")

    body = "```\n" + "\n".join(lines) + "\n```"

    embed = discord.Embed(
        title=f"Archived Games — Page {page}/{total_pages}",
        color=0x95a5a6,
        description=body
    )
    embed.add_field(
        name="How to view a game",
        value="Use **/game_show index:<n>** (where **1 = newest**).",
        inline=False
    )
    embed.set_footer(text=f"Total archived games: {total}")

    await interaction.response.send_message(embed=embed)


@tree.command(description="Show a specific archived game by index (1 = newest)")
async def game_show(interaction: discord.Interaction, index: app_commands.Range[int, 1, 5000]):
    """
    index = 1 → newest archived game
    index = 2 → second newest, and so on.
    """
    gid = interaction.guild_id or 0
    games = archived_games_for_guild(gid)
    if not games:
        await interaction.response.send_message("No archived games found for this server.", ephemeral=True)
        return

    if index > len(games):
        await interaction.response.send_message(
            f"Only **{len(games)}** archived game(s) available. Try a smaller index.",
            ephemeral=True
        )
        return

    # Indexing from the end: 1=newest → -1, 2 → -2, ...
    rec = games[-index]
    gs = GameState.from_dict(rec)

    embed = build_game_result_embed(gs)
    embed.add_field(name="Archive Slot", value=f"Index **{index}** (1 = newest)", inline=False)
    await interaction.response.send_message(embed=embed)


def adjust_accuracy_strike_gutter(b: Bowler, knocked: int, ball_num: int):
    """
    Adjust accuracy only for strikes (+1) or gutterballs (0 pins) on ANY ball (-1).
    (ball_num kept for signature compatibility with call sites)
    """
    delta = 0
    if knocked == 10:
        delta = 1
    elif knocked == 0:  # tweak: any-ball gutter is -1
        delta = -1

    if delta != 0:
        before = b.accuracy
        b.accuracy = max(0, min(100, b.accuracy + delta))
        DB["bowlers"][b.name] = b.to_dict()
        save_db()
        return f"Accuracy {before} → {b.accuracy} (Δ {delta})"
    return None

def adjust_nerves_single_pin(b: Bowler, remaining: int, knocked: int):
    """
    Adjust nerves if bowler shoots a single-pin spare.
    +1 if converted, -1 if missed.
    """
    if remaining == 1:  # single-pin spare attempt
        delta = 1 if knocked == 1 else -1
        before = b.nerves
        b.nerves = max(0, min(100, b.nerves + delta))
        DB["bowlers"][b.name] = b.to_dict()
        save_db()
        return f"Nerves {before} → {b.nerves} (Δ {delta})"
    return None

def award_style_for_strike(bowler_name: str, amt: int = 1):
    """+Style when the bowler throws a strike (clamped 0–100)."""
    b = get_bowler_by_name(bowler_name)
    if not b:
        return
    b.style = max(0, min(100, b.style + amt))
    DB["bowlers"][bowler_name] = b.to_dict()
    save_db()

def award_flair_for_split(bowler_name: str, amt: int = 1):
    """+Flair when the bowler converts a split (clamped 0–100)."""
    b = get_bowler_by_name(bowler_name)
    if not b:
        return
    b.flair = max(0, min(100, b.flair + amt))
    DB["bowlers"][bowler_name] = b.to_dict()
    save_db()

def bump_consistency(b: Bowler, reason: str = "") -> None:
    """+1 consistency (cap 100) and persist immediately."""
    before = b.consistency
    if before < 100:
        b.consistency = min(100, before + 1)
        DB["bowlers"][b.name] = b.to_dict()
        save_db()

def maybe_award_back_to_back_strike(b: Bowler, rolls: List[int]) -> bool:
    """
    Check frame symbols and award +1 consistency if the last two *frames* are both 'X'.
    Returns True if awarded.
    """
    _, _, symbols = score_bowling(rolls)
    # Keep only filled frame symbols (non-empty)
    non_empty = [s for s in symbols if s]
    if len(non_empty) >= 2 and non_empty[-1] == "X" and non_empty[-2] == "X":
        bump_consistency(b, "back_to_back_strikes")
        return True
    return False

def team_of_bowler(name: str) -> Optional[str]:
    """Return the first team that lists this bowler as a member (or None)."""
    for tname, trec in DB.get("teams", {}).items():
        try:
            if name in trec.get("members", []):
                return tname
        except Exception:
            pass
    return None

def is_split(pins: List[int]) -> bool:
    """
    Naive split detection given the *standing pin numbers* after a first ball.
    We have the exact standing list from first_ball_roll; check common split sets.
    """
    if not pins:
        return False
    S = set(pins)
    SPLITS = [
        {7, 10}, {4, 6}, {2, 7}, {3, 10}, {2, 10}, {3, 7},
        {4, 7, 10}, {6, 7, 10}, {2, 4, 10}, {2, 6, 7}, {3, 6, 10}, {3, 4, 7},
        {5, 7}, {5, 10}, {8, 10}, {7, 9},  # a few tricky “split-ish” shapes
    ]
    return any(S == x for x in SPLITS)

def get_bowler_by_name(name: str) -> Optional[Bowler]:
    rec = DB["bowlers"].get(name)
    return Bowler.from_dict(rec) if rec else None


def assert_captain_team(inter: discord.Interaction, name: str) -> Optional[str]:
    t = get_team_by_name(name)
    if not t: return f"Team **{name}** does not exist."
    if t.captain is not None and t.captain != owner_record(inter.user.id).get("active"):
        return "You don't have permission. Only the team captain can manage this team."
    return None


def get_team_by_name(name: str) -> Optional[Team]:
    rec = DB["teams"].get(name)
    return Team.from_dict(rec) if rec else None


def active_game(guild_id: int) -> Optional[GameState]:
    """Return the *active* game only. Ignore finished games."""
    g = DB["games"].get(str(guild_id))
    if not g:
        return None
    # Only treat as active if flagged
    if isinstance(g, dict) and g.get("is_active", True):
        return GameState.from_dict(g)
    return None


def set_active_game(gs: GameState):
    DB["games"][str(gs.guild_id)] = gs.to_dict()
    save_db()


def build_turn_tracker(orderA: List[str], orderB: List[str]) -> List[Tuple[str, str]]:
    """One frame worth of turns, reused each frame."""
    out: List[Tuple[str, str]] = []
    for a, b in zip(orderA, orderB):
        out.append(("A", a))
        out.append(("B", b))
    return out


def advance_turn(gs: GameState):
    gs.turn_i += 1
    if gs.turn_i >= len(gs.turn_tracker):
        gs.frame += 1
        gs.turn_i = 0
        if gs.frame > 10:
            gs.is_active = False
    set_active_game(gs)


def random_order(members: List[str]) -> List[str]:
    shuffled = members[:]
    random.shuffle(shuffled)
    return shuffled


def new_game(guild_id: int, teamA: Team, teamB: Team, lane: str, pressure: str) -> GameState:
    orderA = random_order(teamA.members)
    orderB = random_order(teamB.members)
    gs = GameState(
        guild_id=guild_id, lane=lane, pressure=pressure,
        teamA=teamA.name, teamB=teamB.name,
        orderA=orderA, orderB=orderB,
        frame=1, turn_i=0, is_active=True
    )
    gs.turn_tracker = build_turn_tracker(orderA, orderB)
    for name in orderA + orderB:
        gs.players[name] = BowlerGame(bowler_name=name)
    return gs


def current_turn(gs: GameState) -> Optional[Tuple[str, str]]:
    if not gs.is_active or gs.frame > 10 or gs.turn_i >= len(gs.turn_tracker):
        return None
    side, bowler = gs.turn_tracker[gs.turn_i]
    team_name = gs.teamA if side == "A" else gs.teamB
    return (team_name, bowler)

def _add_team_fields_chunked(embed: discord.Embed, team_name: str, lines: List[str], total: int, max_parts: int = 12):
    """
    Add team lines across multiple fields if needed.
    - Each field value is <= 1024 chars.
    - At most `max_parts` fields per team (last field will summarize overflow).
    """
    MAX = 1024
    if not lines:
        embed.add_field(name=f"{team_name} — Team Total: {total}", value="—", inline=False)
        return

    parts = []
    buf = []
    cur_len = 0

    for line in lines:
        line = line or " "
        # +1 for newline if buf is not empty
        extra = (1 if buf else 0) + len(line)
        if cur_len + extra > MAX:
            parts.append("\n".join(buf))
            buf = [line]
            cur_len = len(line)
        else:
            if buf:
                cur_len += 1  # newline
            buf.append(line)
            cur_len += len(line)

    if buf:
        parts.append("\n".join(buf))

    # Enforce a max number of parts to keep total embed fields well under 25
    if len(parts) > max_parts:
        visible = parts[:max_parts - 1]
        hidden_count = sum(s.count("\n") + 1 for s in parts[max_parts - 1:])
        parts = visible
        parts.append(f"…and **{hidden_count}** more lines not shown.")

    # Add fields; first one keeps the total in the title, subsequent ones are continuations
    for i, block in enumerate(parts, start=1):
        if i == 1:
            title = f"{team_name} — Team Total: {total}"
        else:
            title = f"{team_name} (cont. {i})"
        embed.add_field(name=title, value=block if block else "—", inline=False)


def pretty_scoreboard(gs: GameState) -> discord.Embed:
    def row_line(name: str, sym: List[str], total: int) -> str:
        # name col, 10 frame cols (2 chars each), total col
        name_col = name[:16].ljust(16)
        frames = " ".join(f"{(s or ' '):>2}" for s in sym[:10])
        total_col = f"{total:>4}"
        return f"{name_col}  {frames}  {total_col}"

    def header_line() -> str:
        name_h = "NAME".ljust(16)
        frames_h = " ".join(f"{i:>2}" for i in range(1, 11))
        return f"{name_h}  {frames_h}  TOT "

    def team_block(order: List[str]) -> Tuple[List[str], int]:
        lines = [header_line()]
        team_total = 0
        for name in order:
            bg = gs.players[name]
            tot, _, sym = score_bowling(bg.rolls)
            team_total += tot
            lines.append(row_line(name, sym, tot))
        return lines, team_total

    # Build blocks
    linesA, totalA = team_block(gs.orderA)
    linesB, totalB = team_block(gs.orderB)

    # Wrap each block in a code fence so it’s monospaced & aligned
    blockA = "```" + "\n".join(linesA) + "```"
    blockB = "```" + "\n".join(linesB) + "```"

    # Create embed
    embed = discord.Embed(
        title=f"Game — {gs.teamA} vs {gs.teamB} (Frame {min(gs.frame, 10)})",
        color=0xf1c40f
    )
    embed.add_field(name=f"{gs.teamA} — Team Total: {totalA}", value=blockA, inline=False)
    embed.add_field(name=f"{gs.teamB} — Team Total: {totalB}", value=blockB, inline=False)

    turn = current_turn(gs)
    if turn:
        team_name, bowler = turn
        embed.set_footer(text=f"Up: {bowler} ({team_name})")
    else:
        embed.set_footer(text="Game complete" if gs.frame > 10 else "Next frame soon")
    return embed


def pretty_head_to_head_results(gs: GameState) -> str:
    count = min(len(gs.orderA), len(gs.orderB))
    result_lines = []
    for i in range(count):
        bowlerA = gs.orderA[i]
        bowlerB = gs.orderB[i]
        scoreA = score_bowling(gs.players[bowlerA].rolls)[0]
        scoreB = score_bowling(gs.players[bowlerB].rolls)[0]
        if scoreA > scoreB:
            winner = f"🏆 {bowlerA}"
        elif scoreB > scoreA:
            winner = f"🏆 {bowlerB}"
        else:
            winner = "🤝 Tie"
        result_lines.append(f"{bowlerA} vs {bowlerB}: {scoreA} - {scoreB} ({winner})")
    return "\n".join(result_lines) if result_lines else "No head-to-head results."

import re

DIGIT = re.compile(r"^\d$")

def analyze_frame_symbol(sym: str):
    """Return tuple: (is_strike, is_spare, is_open, first_ball_count, splitish_spare)
       splitish_spare: spare where first ball digit <= 7 (proxy for 'split-ish')
    """
    if not sym:
        return (False, False, False, 0, False)
    # Strike frames
    if sym == "X":
        return (True, False, False, 10, False)
    # Normal frames like "9/" or "81"
    if len(sym) == 2:
        a, b = sym[0], sym[1]
        if b == "/":
            first = int(a) if DIGIT.match(a) else 0
            return (False, True, False, first, first <= 7)
        # open
        first = int(a) if DIGIT.match(a) else 0
        return (False, False, True, first, False)
    # 10th frame e.g. "XXX","X9/","9/X","9-"
    first = 0
    if DIGIT.match(sym[0]):
        first = int(sym[0])
    elif sym[0] == "X":
        first = 10
    # spare in 10th if any '/' present
    is_spare = ("/" in sym)
    # count a strike if first char is X
    is_strike = (sym[0] == "X")
    # open if no strike or spare and length>=2
    is_open = (not is_spare and "X" not in sym and len(sym) >= 2)
    splitish = False
    # only count split-ish on the first spare in the frame
    if is_spare and DIGIT.match(sym[0]) and int(sym[0]) <= 7:
        splitish = True
    return (is_strike, is_spare, is_open, first, splitish)

def analyze_game_for_awards(rolls: List[int], symbols: List[str]):
    """Compute per-game stats for one bowler."""
    strikes = spares = opens = frames = pocket_hits = pocket_attempts = 0
    splits_conv = splits_att = 0
    # strike run across the game (10th can add extra X’s)
    longest_run = cur_run = 0

    # Build a roll-level strike sequence to capture 10th extra X’s
    strike_sequence: List[bool] = []

    for f in range(10):
        sym = symbols[f] if f < len(symbols) else ""
        is_strike, is_spare, is_open, first_cnt, splitish = analyze_frame_symbol(sym)
        frames += 1
        pocket_attempts += 1
        if first_cnt >= 9:
            pocket_hits += 1

        if is_strike:
            strikes += 1
            # For 10th: add as many X as appear
            if f == 9 and sym:
                xs = sym.count("X")
                strike_sequence.extend([True] * xs)
            else:
                strike_sequence.append(True)
        else:
            # 10th may still contain later X but first wasn’t X – count them in sequence
            if f == 9 and sym:
                xs = sym.count("X")
                # if first not X, they’re not consecutive from frame to frame unless previous was X.
                # We’ll just append in order; run logic below will handle it.
                strike_sequence.extend([True] * xs)
            if is_spare:
                spares += 1
                if splitish:
                    splits_att += 1
                    splits_conv += 1
            elif is_open:
                opens += 1
            # Count split attempts when spare wasn’t made (rare info loss). We’ll skip to avoid noise.

    # compute longest consecutive strikes run
    for s in strike_sequence:
        if s:
            cur_run += 1
            longest_run = max(longest_run, cur_run)
        else:
            cur_run = 0

    return {
        "strikes": strikes,
        "spares": spares,
        "opens": opens,
        "frames": frames,
        "pocket_hits": pocket_hits,
        "pocket_attempts": pocket_attempts,
        "splits_conv": splits_conv,
        "splits_att": splits_att,
        "longest_run": longest_run
    }

# =========================
# DISCORD BOOTSTRAP
# =========================

def is_admin(inter: discord.Interaction) -> bool:
    try:
        return bool(inter.user.guild_permissions.administrator)
    except Exception:
        return False


# =========================
# EVENTS & GLOBAL LOGGING
# =========================
@bot.event
async def on_ready():
    try:
        for g in bot.guilds:
            cmds = await tree.sync(guild=g)  # instant in each server
            print(f"✅ Synced {len(cmds)} cmds to {g.name}: {[c.name for c in cmds]}")
        print(f"Logged in as {bot.user}")
    except Exception as e:
        print("Sync error:", e)
    for g in bot.guilds:
        await send_log(bot, g.id, f"✅ **{bot.user}** is online and slash commands synced.")


@bot.event
async def on_guild_join(guild: discord.Guild):
    await send_log(bot, guild.id, f"➕ Joined guild: **{guild.name}** (id {guild.id})")


@bot.event
async def on_guild_remove(guild: discord.Guild):
    await send_log(bot, guild.id, f"➖ Removed from guild: **{guild.name}** (id {guild.id})")


@bot.event
async def on_member_join(member: discord.Member):
    await send_log(bot, member.guild.id, f"👋 Member joined: **{member}**")


@bot.event
async def on_member_remove(member: discord.Member):
    await send_log(bot, member.guild.id, f"👋 Member left: **{member}**")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: Exception):
    await send_log(bot, interaction.guild_id or 0,
                   f"❌ Command error: `/{interaction.command.name if interaction.command else '?'}` by {interaction.user} — {error}")
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message("Something went wrong running that command.", ephemeral=True)
    except Exception:
        pass


@bot.event
async def on_application_command_completion(interaction: discord.Interaction):
    await send_log(bot, interaction.guild_id or 0, f"✅ `/{interaction.command.name}` used by {interaction.user}")


@tree.command(description="Set the bot's log channel (admin only)")
async def admin_setlog(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(interaction):
        await interaction.response.send_message("⛔ Admin only.", ephemeral=True)
        return
    gs = get_guild_settings(interaction.guild_id or 0)
    gs["log_channel_id"] = channel.id
    save_db()
    await interaction.response.send_message(f"✅ Log channel set to {channel.mention}.", ephemeral=True)

# =========================
# LEAGUE COMMANDS
# =========================

@tree.command(description="Create a new league")
async def league_create(interaction: discord.Interaction, name: str):
    name = name.strip()
    if not name or len(name) > 32:
        await interaction.response.send_message("Pick a league name (1–32 chars).", ephemeral=True)
        return
    if "leagues" not in DB:
        DB["leagues"] = {}
    if name in DB["leagues"]:
        await interaction.response.send_message("That league name is taken.", ephemeral=True)
        return
    league = League(name=name)
    DB["leagues"][name] = league.to_dict()
    save_db()
    await interaction.response.send_message(f"✅ League **{name}** created.", ephemeral=True)

@tree.command(description="Add a team to a league")
async def league_addteam(interaction: discord.Interaction, league: str, team: str):
    l = get_league_by_name(league)
    t = get_team_by_name(team)
    if not l: await interaction.response.send_message("No such league.", ephemeral=True); return
    if not t: await interaction.response.send_message("No such team.", ephemeral=True); return
    if any(ts.team == team for ts in l.teams):
        await interaction.response.send_message("Team already in league.", ephemeral=True);
        return
    l.teams.append(LeagueTeamStats(team=team))
    save_league(l)
    await interaction.response.send_message(f"✅ Added **{team}** to league **{league}**.", ephemeral=True)

@tree.command(description="Show league standings")
async def league_show(interaction: discord.Interaction, league: str):
    l = get_league_by_name(league)
    if not l:
        await interaction.response.send_message("No such league.", ephemeral=True)
        return
    standings = sorted(l.teams, key=lambda ts: (-ts.wins, -ts.draws, ts.losses, ts.team))
    embed = discord.Embed(
        title=f"🏆 League: {league}",
        color=0x3498db,
        description=f"**Teams:** {len(standings)}"
    )
    if standings:
        for i, ts in enumerate(standings):
            pos = f"#{i + 1}"
            team_stats = f"W: {ts.wins} | D: {ts.draws} | L: {ts.losses}"
            embed.add_field(
                name=f"{pos} — {ts.team}",
                value=team_stats,
                inline=False
            )
        embed.set_footer(text="Positions sorted by Wins, Draws, Losses")
    else:
        embed.description = "No teams in this league."

    await interaction.response.send_message(embed=embed)

@tree.command(description="List all leagues")
async def league_list(interaction: discord.Interaction):
    if "leagues" not in DB or not DB["leagues"]:
        await interaction.response.send_message("No leagues created yet.", ephemeral=True)
        return
    names = sorted(DB["leagues"].keys())
    await interaction.response.send_message("**Leagues:** " + ", ".join(names))

def league_playoff_matches(league: League) -> Dict[str, List[str]]:
    """
    Picks top 4 teams from league standings, creates playoff match rounds.
    Returns:
        {
            "semifinals": [[team1, team2], [team3, team4]],
            "final": [winnerA, winnerB], # to be filled in after semis played
            "third_place": [loserA, loserB] # to be filled in after semis played
        }
    """
    # Sort by wins, then draws, then losses, then name
    standings = sorted(league.teams, key=lambda ts: (-ts.wins, -ts.draws, ts.losses, ts.team))
    if len(standings) < 4:
        return {"error": "Not enough teams for playoffs (need at least 4)."}

    # Pick top 4 teams
    top4 = standings[:4]
    t1, t2, t3, t4 = [ts.team for ts in top4]
    # Semifinals: 1 vs 4, 2 vs 3
    return {
        "semifinals": [[t1, t4], [t2, t3]],
        "final": [],
        "third_place": []
    }

# Example usage (after league is loaded):
# playoff = league_playoff_matches(league)
# This gives you the matchups for the semifinals.
# You then run games for each matchup, record winners/losers,
# then run playoff["final"] and playoff["third_place"] after the semifinals.

# =========================
# TEAM COMMANDS
# =========================
@tree.command(description="Create a team")
async def team_create(interaction: discord.Interaction, name: str):
    name = name.strip()
    if not name or len(name) > 32:
        await interaction.response.send_message("Pick a team name (1–32 chars).", ephemeral=True)
        return
    if name in DB["teams"]:
        await interaction.response.send_message("That team name is taken.", ephemeral=True)
        return
    t = Team(name=name, captain=None, members=[], order=[])
    DB["teams"][name] = t.to_dict()
    save_db()
    await send_log(bot, interaction.guild_id or 0, f"🆕 Team created: **{name}** by {interaction.user}")
    await interaction.response.send_message(f"✅ Team **{name}** created.", ephemeral=True)

@tree.command(description="Set a team's captain (must be a member)")
async def team_setcaptain(interaction: discord.Interaction, team: str, captain: str):
    t = get_team_by_name(team)
    if not t:
        await interaction.response.send_message("No such team.", ephemeral=True)
        return
    if captain not in t.members:
        await interaction.response.send_message("Captain must be a current team member.", ephemeral=True)
        return
    t.captain = captain
    DB["teams"][team] = t.to_dict()
    save_db()
    await interaction.response.send_message(f"✅ Team captain for **{team}** set to **{captain}**.", ephemeral=True)

@tree.command(description="Add a bowler to your team")
async def team_add(interaction: discord.Interaction, team: str, bowler: str):
    err = assert_captain_team(interaction, team)
    if err: await interaction.response.send_message(err, ephemeral=True); return
    t = get_team_by_name(team)
    if bowler not in DB["bowlers"]:
        await interaction.response.send_message("Unknown bowler name.", ephemeral=True)
        return
    if bowler in t.members:
        await interaction.response.send_message("Already on the team.", ephemeral=True)
        return
    t.members.append(bowler)
    if not t.order: t.order = list(t.members)
    DB["teams"][team] = t.to_dict();
    save_db()
    await send_log(bot, interaction.guild_id or 0, f"👥 {interaction.user} added **{bowler}** to **{team}**")
    await interaction.response.send_message(f"✅ Added **{bowler}** to **{team}**.", ephemeral=True)

@tree.command(description="Remove a bowler from your team")
async def team_remove(interaction: discord.Interaction, team: str, bowler: str):
    err = assert_captain_team(interaction, team)
    if err: await interaction.response.send_message(err, ephemeral=True); return
    t = get_team_by_name(team)
    if bowler not in t.members:
        await interaction.response.send_message("That bowler isn’t on the team.", ephemeral=True)
        return
    t.members = [m for m in t.members if m != bowler]
    t.order = [m for m in t.order if m != bowler]
    if t.captain == bowler:
        t.captain = None
    DB["teams"][team] = t.to_dict();
    save_db()
    await send_log(bot, interaction.guild_id or 0, f"🗑️ {interaction.user} removed **{bowler}** from **{team}**")
    await interaction.response.send_message(f"🗑️ Removed **{bowler}** from **{team}**.", ephemeral=True)

@tree.command(description="Set batting order for your team (space-separated bowler names)")
async def team_setorder(interaction: discord.Interaction, team: str, order: str):
    err = assert_captain_team(interaction, team)
    if err: await interaction.response.send_message(err, ephemeral=True); return
    t = get_team_by_name(team)
    names = [x for x in order.split() if x]
    if not names or any(n not in t.members for n in names):
        await interaction.response.send_message("All names must be current team members.", ephemeral=True)
        return
    t.order = names
    DB["teams"][team] = t.to_dict();
    save_db()
    await send_log(bot, interaction.guild_id or 0,
                   f"🔢 {interaction.user} set order for **{team}** → {', '.join(names)}")
    await interaction.response.send_message(f"✅ **{team}** order set: {', '.join(names)}", ephemeral=True)

@tree.command(description="Show a team")
async def team_show(interaction: discord.Interaction, team: str):
    t = get_team_by_name(team)
    if not t:
        await interaction.response.send_message("No such team.", ephemeral=True)
        return
    embed = discord.Embed(title=f"Team — {t.name}", color=0x1abc9c)
    embed.add_field(name="Team Captain", value=t.captain if t.captain else "—", inline=False)
    embed.add_field(name="Members", value=", ".join(t.members) if t.members else "—", inline=False)
    embed.add_field(name="Order", value=" → ".join(t.order) if t.order else "—", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(description="List all teams")
async def team_list(interaction: discord.Interaction):
    if not DB["teams"]:
        await interaction.response.send_message("No teams created yet.", ephemeral=True)
        return
    names = sorted(DB["teams"].keys())
    await interaction.response.send_message("**Teams:** " + ", ".join(names))

# =========================
# GAME FLOW (ADMIN-GATED)
# =========================
@tree.command(description="Start a game between two teams")
@app_commands.choices(
    lane=[
        app_commands.Choice(name="normal", value="normal"),
        app_commands.Choice(name="fresh", value="fresh"),
        app_commands.Choice(name="burnt", value="burnt")
    ],
    pressure=[
        app_commands.Choice(name="none", value="none"),
        app_commands.Choice(name="clutch", value="clutch")
    ]
)
async def game_start(
        interaction: discord.Interaction,
        team_a: str,
        team_b: str,
        lane: app_commands.Choice[str] = None,
        pressure: app_commands.Choice[str] = None
):
    if not is_admin(interaction):
        await interaction.response.send_message("⛔ Admin only.", ephemeral=True)
        return
    guild_id = interaction.guild_id
    if not guild_id:
        await interaction.response.send_message("Run this in a server.", ephemeral=True)
        return
    existing = active_game(guild_id)
    if existing and existing.is_active:
        await interaction.response.send_message("A game is already active in this server. Use `/game_end` first.",
                                                ephemeral=True)
        return
    tA = get_team_by_name(team_a)
    tB = get_team_by_name(team_b)
    if not tA or not tB:
        await interaction.response.send_message("One or both teams not found.", ephemeral=True)
        return
    if not tA.members or not tB.members:
        await interaction.response.send_message("Both teams need at least one member.", ephemeral=True)
        return
    if len(tA.members) != len(tB.members):
        await interaction.response.send_message("Teams must have the same number of members for head-to-head play.",
                                                ephemeral=True)
        return

    gs = new_game(
        guild_id, tA, tB,
        lane.value if lane else "normal",
        pressure.value if pressure else "none"
    )
    set_active_game(gs)
    await send_log(bot, guild_id,
                   f"🎳 Game started: **{tA.name}** vs **{tB.name}** (lane={gs.lane}, pressure={gs.pressure}) by {interaction.user}")
    await interaction.response.send_message(
        content=(
            f"🎳 Game started: **{tA.name}** vs **{tB.name}**\n"
            f"Bowler orders rolled!\n"
            f"{tA.name}: {', '.join(gs.orderA)}\n"
            f"{tB.name}: {', '.join(gs.orderB)}"
        ),
        embed=pretty_scoreboard(gs)
    )

@tree.command(description="Show head-to-head matchup results for the current game")
async def game_headtohead(interaction: discord.Interaction):
    gs = active_game(interaction.guild_id or 0)
    if not gs:
        await interaction.response.send_message("No active game.", ephemeral=True)
        return
    if gs.finalized:
        await interaction.response.send_message("This game was already finalized. Stats won’t be counted again.",
                                                ephemeral=True)
        return
    results = pretty_head_to_head_results(gs)
    await interaction.response.send_message(content="**Head-to-Head Results:**\n" + results)

@tree.command(description="End the current game")
async def game_end(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("⛔ Admin only.", ephemeral=True); return
    gs = active_game(interaction.guild_id or 0)
    if not gs:
        await interaction.response.send_message("No active game.", ephemeral=True); return

    # Calculate team totals (and per-bowler totals for MVP) before mutating anything
    per_bowler_totals = {}
    for name, bg in gs.players.items():
        total, _, _ = score_bowling(bg.rolls)
        per_bowler_totals[name] = total

    totA = sum(per_bowler_totals.get(n, 0) for n in gs.orderA)
    totB = sum(per_bowler_totals.get(n, 0) for n in gs.orderB)

    # Winner / tie text
    if totA > totB:
        result_text = f"🏆 **Winner:** {gs.teamA} — {totA} to {totB}"
    elif totB > totA:
        result_text = f"🏆 **Winner:** {gs.teamB} — {totB} to {totA}"
    else:
        result_text = f"🤝 **Tie:** {gs.teamA} {totA} — {gs.teamB} {totB}"

    # MVP = highest single-game score across all bowlers in this game
    top_score = max(per_bowler_totals.values()) if per_bowler_totals else 0
    mvps = [name for name, sc in per_bowler_totals.items() if sc == top_score] if top_score > 0 else []
    if mvps:
        # include team tag next to each MVP name for clarity
        def team_of(bname: str) -> str:
            return gs.teamA if bname in gs.orderA else (gs.teamB if bname in gs.orderB else "?")
        mvp_text = ", ".join([f"**{n}** ({team_of(n)}) — {top_score}" for n in mvps])
    else:
        mvp_text = "—"

    # Close the game & persist
    gs.is_active = False
    set_active_game(gs)

    # Archive the just-finished game
    archive_game(gs)

    # Update league record and season/awards stats ONCE
    league_record_result(gs.teamA, gs.teamB, totA, totB)
    finalize_stats_for_game(gs)

    # Mark finalized and persist
    gs.finalized = True
    set_active_game(gs)

    # Head-to-head recap (kept from your original flow)
    results = pretty_head_to_head_results(gs)

    # Build embed: scoreboard + result + MVP + H2H
    embed = pretty_scoreboard(gs)
    embed.add_field(name="Result", value=result_text, inline=False)
    embed.add_field(name="MVP (highest game)", value=mvp_text, inline=False)
    if results:
        # Trim in case the list is very long
        embed.add_field(
            name="Head-to-Head Results",
            value=(results if len(results) <= 1024 else results[:1015] + "…"),
            inline=False
        )

    await send_log(
        bot,
        interaction.guild_id or 0,
        f"🧹 Game ended. {result_text} | MVP: {mvp_text}"
    )
    await interaction.response.send_message(embed=embed)


@tree.command(description="Forfeit the current game (declare winner by higher current total)")
async def game_forfeit(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("⛔ Admin only.", ephemeral=True); return
    gs = active_game(interaction.guild_id or 0)
    if not gs:
        await interaction.response.send_message("No active game.", ephemeral=True); return

    totA = sum(score_bowling(gs.players[n].rolls)[0] for n in gs.orderA)
    totB = sum(score_bowling(gs.players[n].rolls)[0] for n in gs.orderB)
    result = f"🏁 Forfeit: **{gs.teamA} {totA}** — **{gs.teamB} {totB}**. Winner: " + (gs.teamA if totA >= totB else gs.teamB)

    gs.is_active = False
    set_active_game(gs)

    # Archive the forfeited game too
    archive_game(gs)

    # league update
    league_record_result(gs.teamA, gs.teamB, totA, totB)
    # NEW: award stats (still count toward stats even on forfeit)
    finalize_stats_for_game(gs)

    results = pretty_head_to_head_results(gs)
    await send_log(bot, interaction.guild_id or 0, f"🏁 Game forfeited. {result} (stats updated)")
    await interaction.response.send_message(content=result + "\n\n**Head-to-Head Results:**\n" + results, embed=pretty_scoreboard(gs))

@tree.command(description="Show current game status")
async def game_status(interaction: discord.Interaction):
    gs = active_game(interaction.guild_id or 0)
    if not gs: await interaction.response.send_message("No active game.", ephemeral=True); return
    await interaction.response.send_message(embed=pretty_scoreboard(gs))

def take_turn_roll(gs: GameState) -> Tuple[str, str, dict]:
    turn = current_turn(gs)
    if not turn:
        return ("", "", {"msg": "No active turn."})

    team_name, bowler_name = turn
    b = get_bowler_by_name(bowler_name)
    bg = gs.players[bowler_name]
    fs = bg.frame_state

    # ----- BALL 1 -----
    if fs.ball == 1:
        standing_list, meta = first_ball_roll(b, gs.lane, gs.pressure)
        knocked = 10 - len(standing_list)
        bg.rolls.append(knocked)

        # Track split opportunity
        bg.frame_state.split_pending = is_split(standing_list)

        # Accuracy adjust
        adjust_accuracy_strike_gutter(b, knocked, 1)

        if fs.frame < 10:
            if knocked == 10:  # strike
                award_style_for_strike(bowler_name)  # +Style
                maybe_award_back_to_back_strike(b, bg.rolls)
                bg.frame_state.split_pending = False
                bg.frames_done += 1
                bg.frame_state = FrameState(frame=fs.frame + 1, ball=1, remaining=10)
                advance_turn(gs)
            else:
                bg.frame_state.ball = 2
                bg.frame_state.remaining = 10 - knocked
                set_active_game(gs)
        else:
            if knocked == 10:  # 10th frame strike
                award_style_for_strike(bowler_name)  # +Style
                maybe_award_back_to_back_strike(b, bg.rolls)
                bg.frame_state.ball = 2
                bg.frame_state.remaining = 10
                bg.frame_state.tenth_bonus1 = True
                bg.frame_state.split_pending = False
            else:
                bg.frame_state.ball = 2
                bg.frame_state.remaining = 10 - knocked
            set_active_game(gs)

        desc = f"{bowler_name} — Ball 1: knocked **{knocked}** (SQ {meta['SQ']})"
        return (team_name, bowler_name, {"desc": desc, "remaining": bg.frame_state.remaining})

    # ----- BALL 2 -----
    if fs.ball == 2:
        if fs.frame < 10:
            remaining = fs.remaining
            knocked, meta = spare_ball_roll(b, remaining)
            bg.rolls.append(knocked)

            adjust_accuracy_strike_gutter(b, knocked, 2)
            adjust_nerves_single_pin(b, remaining, knocked)

            if knocked == remaining:
                bump_consistency(b, "spare_made")
                if bg.frame_state.split_pending:
                    award_flair_for_split(b.name, 1)
                bg.frame_state.split_pending = False
            else:
                bg.frame_state.split_pending = False

            bg.frames_done += 1
            bg.frame_state = FrameState(frame=fs.frame + 1, ball=1, remaining=10)
            advance_turn(gs)
            desc = f"{bowler_name} — Ball 2: {'SPARE' if knocked == remaining else f'missed ({knocked} of {remaining})'}"
            return (team_name, bowler_name, {"desc": desc})

        # ----- 10th frame -----
        if fs.tenth_bonus1:  # Ball 1 was strike → fresh rack
            standing_list, meta = first_ball_roll(b, gs.lane, gs.pressure)
            knocked2 = 10 - len(standing_list)
            bg.rolls.append(knocked2)

            bg.frame_state.split_pending = is_split(standing_list) if knocked2 != 10 else False
            adjust_accuracy_strike_gutter(b, knocked2, 2)

            bg.frame_state.ball = 3
            bg.frame_state.tenth_bonus2 = True
            if knocked2 == 10:
                award_style_for_strike(bowler_name)  # +Style
                bg.frame_state.remaining = 10
                desc = f"{bowler_name} — Ball 2: **STRIKE** (SQ {meta['SQ']}) → bonus ball"
            else:
                bg.frame_state.remaining = 10 - knocked2
                desc = f"{bowler_name} — Ball 2: knocked **{knocked2}** (SQ {meta['SQ']}) → bonus ball"
            set_active_game(gs)
            return (team_name, bowler_name, {"desc": desc, "remaining": bg.frame_state.remaining})

        else:  # Ball 1 not strike → spare attempt
            remaining = fs.remaining
            knocked, meta = spare_ball_roll(b, remaining)
            bg.rolls.append(knocked)

            adjust_accuracy_strike_gutter(b, knocked, 2)
            adjust_nerves_single_pin(b, remaining, knocked)

            if knocked == remaining:
                bump_consistency(b, "spare_made")
                if bg.frame_state.split_pending:
                    award_flair_for_split(b.name, 1)
                bg.frame_state.split_pending = False

                bg.frame_state.ball = 3
                bg.frame_state.tenth_bonus2 = True
                bg.frame_state.remaining = 10
                set_active_game(gs)
                desc = f"{bowler_name} — Ball 2: **SPARE** → bonus ball"
                return (team_name, bowler_name, {"desc": desc, "remaining": 10})
            else:
                bg.frame_state.split_pending = False
                bg.frames_done += 1
                bg.frame_state = FrameState(frame=fs.frame + 1, ball=1, remaining=10)
                advance_turn(gs)
                return (team_name, bowler_name,
                        {"desc": f"{bowler_name} — Ball 2: missed ({knocked} of {remaining}) (frame end)"})

    # ----- BALL 3 (10th frame only) -----
    if fs.ball == 3:
        if fs.remaining == 10:
            standing_list, meta = first_ball_roll(b, gs.lane, gs.pressure)
            knocked3 = 10 - len(standing_list)
            bg.rolls.append(knocked3)

            bg.frame_state.split_pending = is_split(standing_list) if knocked3 != 10 else False
            adjust_accuracy_strike_gutter(b, knocked3, 3)

            if knocked3 == 10:
                award_style_for_strike(bowler_name)  # +Style
            note = f"**STRIKE** (SQ {meta['SQ']})" if knocked3 == 10 else f"knocked **{knocked3}** (SQ {meta['SQ']})"
        else:
            knocked3, meta = spare_ball_roll(b, fs.remaining)
            bg.rolls.append(knocked3)

            adjust_accuracy_strike_gutter(b, knocked3, 3)
            adjust_nerves_single_pin(b, fs.remaining, knocked3)

            if knocked3 == fs.remaining:
                bump_consistency(b, "spare_made")
                if bg.frame_state.split_pending:
                    award_flair_for_split(b.name, 1)
            bg.frame_state.split_pending = False

            note = f"**SPARE**" if knocked3 == fs.remaining else f"missed ({knocked3} of {fs.remaining})"

        bg.frames_done += 1
        bg.frame_state = FrameState(frame=fs.frame + 1, ball=1, remaining=10)
        advance_turn(gs)
        return (team_name, bowler_name, {"desc": f"{bowler_name} — Bonus ball: {note} (frame end)"})

    # Fallback
    return (team_name, bowler_name, {"desc": f"{bowler_name} — no-op"})

def roll_two_balls_for_current_bowler(gs: GameState) -> Tuple[str, str, List[str]]:
    """
    Rolls up to two balls for the current bowler.
    Stops early if the frame ends (e.g., strike on ball 1 in frames 1–9),
    or if the game advances to the next bowler.
    Returns: (team_name, bowler_name, [play_descriptions...])
    """
    turn = current_turn(gs)
    if not turn:
        return "", "", ["No active turn."]
    start_team, start_bowler = turn
    plays: List[str] = []

    # First roll
    team_name, bowler_name, info1 = take_turn_roll(gs)
    if bowler_name:
        plays.append(info1.get("desc", ""))
    else:
        return "", "", [info1.get("msg", "No active turn.")]

    # Check if still same bowler for a possible second roll
    turn2 = current_turn(gs)
    if not turn2:
        return team_name, bowler_name, plays  # game might have progressed/completed
    next_team, next_bowler = turn2

    # If the bowler changed, we had a strike/frame end — stop here
    if next_bowler != start_bowler:
        return team_name, bowler_name, plays

    # Same bowler still up: do second roll
    team_name2, bowler_name2, info2 = take_turn_roll(gs)
    if bowler_name2:
        plays.append(info2.get("desc", ""))
    return team_name, bowler_name, plays

@tree.command(description="Roll up to two balls for the current bowler")
async def game_roll(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("⛔ Admin only.", ephemeral=True)
        return
    gs = active_game(interaction.guild_id or 0)
    if not gs or not gs.is_active:
        # If there is an archived-but-not-cleared game, show final embed instead of a plain message
        if gs and gs.finalized:
            await interaction.response.send_message(embed=finalize_and_build_game_embed(gs))
        else:
            await interaction.response.send_message("No active game.", ephemeral=True)
        return

    turn = current_turn(gs)
    if not turn:
        # Just in case we've rolled through the last shot already
        final_embed = finalize_and_build_game_embed(gs)
        await interaction.response.send_message(embed=final_embed)
        return

    team_name, bowler_name, plays = roll_two_balls_for_current_bowler(gs)

    # Log each play
    for p in plays:
        if p:
            await send_log(bot, interaction.guild_id or 0, f"🎳 Roll — {bowler_name} ({team_name}): {p}")

    # If the game just ended on this roll, announce full final result
    gs_after = active_game(interaction.guild_id or 0) or gs
    if not gs_after.is_active:
        final_embed = finalize_and_build_game_embed(gs_after)
        await send_log(bot, interaction.guild_id or 0, "🏁 Game completed (auto-finalized on last ball).")
        await interaction.response.send_message(embed=final_embed)
        return

    # Otherwise, show regular scoreboard + plays
    embed = pretty_scoreboard(gs_after)
    if plays:
        embed.add_field(name="Plays", value="\n".join(f"• {p}" for p in plays if p)[:1024], inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(description="Roll two shots for everyone left this frame")
async def game_roll_round(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("⛔ Admin only.", ephemeral=True)
        return

    gs = active_game(interaction.guild_id or 0)
    if not gs or not gs.is_active:
        await interaction.response.send_message("No active game.", ephemeral=True)
        return

    # How many bowlers remain in this frame?
    remaining_turns = max(0, len(gs.turn_tracker) - gs.turn_i)
    if remaining_turns == 0:
        await interaction.response.send_message("This frame is already complete.", ephemeral=True)
        return

    # Roll two shots for each remaining bowler (or until the game ends)
    lines: List[str] = []
    rolled_count = 0

    for _ in range(remaining_turns):
        turn = current_turn(gs)
        if not turn:
            break  # game might be complete (10th done)
        team_name, bowler_name, plays = roll_two_balls_for_current_bowler(gs)
        rolled_count += 1

        # Log & collect messages
        display_name = f"{bowler_name} ({team_name})"
        for p in plays:
            if p:
                await send_log(bot, interaction.guild_id or 0, f"🎳 Roll — {display_name}: {p}")

        # Summarize this bowler’s two plays (could be 1 if strike or game state)
        if plays:
            bullet = " • ".join([x for x in plays if x])
            lines.append(f"**{display_name}** — {bullet}")
        else:
            lines.append(f"**{display_name}** — (no result)")

        # If game ended mid-batch, stop
        if not gs.is_active or not current_turn(gs):
            break

    # Build scoreboard with a compact recap
    embed = pretty_scoreboard(gs)
    if lines:
        recap = "\n".join(lines)
        # Discord field value limit is 1024 chars; trim if needed
        if len(recap) > 1024:
            recap = recap[:1015] + "…"
        embed.add_field(name=f"Plays (this frame, {rolled_count} bowlers)", value=recap, inline=False)

    await interaction.response.send_message(embed=embed)

def finalize_stats_for_game(gs: GameState):
    """Aggregate team + bowler stats and persist award metrics."""
    # Team totals this game
    teamA_total = sum(score_bowling(gs.players[n].rolls)[0] for n in gs.orderA)
    teamB_total = sum(score_bowling(gs.players[n].rolls)[0] for n in gs.orderB)

    # ---- Team season stats ----
    for team_name, total in ((gs.teamA, teamA_total), (gs.teamB, teamB_total)):
        tstats = get_team_stats(team_name)
        tstats.games += 1
        tstats.total_pins += total
        tstats.high_game = max(tstats.high_game, total)
        # treat each match as one "series" for now (one game match) – if you later add multi-game nights,
        # sum them before calling finalize once per night.
        tstats.series_running += total
        tstats.high_series = max(tstats.high_series, tstats.series_running)
        save_team_stats(team_name, tstats)

    # ---- Individual stats ----
    for name, bg in gs.players.items():
        game_total, _, symbols = score_bowling(bg.rolls)
        per = analyze_game_for_awards(bg.rolls, symbols)

        st = get_bowler_stats(name)
        st.games += 1
        st.total_pins += game_total
        st.high_game = max(st.high_game, game_total)
        st.worst_game = min(st.worst_game, game_total)

        # series tracking (store last 12 games; compute best 3)
        st.recent_games.append(game_total)
        if len(st.recent_games) > 12:
            st.recent_games = st.recent_games[-12:]
        # best 3-game sum
        best3 = 0
        if len(st.recent_games) >= 3:
            # sliding window sums
            for i in range(len(st.recent_games) - 2):
                s3 = st.recent_games[i] + st.recent_games[i+1] + st.recent_games[i+2]
                if s3 > best3: best3 = s3
        st.high_series_3 = max(st.high_series_3, best3)

        st.strikes += per["strikes"]
        st.spares += per["spares"]
        st.frames += per["frames"]
        if per["opens"] == 0 and per["frames"] > 0:
            st.clean_games += 1

        st.pocket_hits += per["pocket_hits"]
        st.pocket_attempts += per["pocket_attempts"]

        st.splits_converted += per["splits_conv"]
        st.splits_attempted += per["splits_att"]

        st.longest_strike_run = max(st.longest_strike_run, per["longest_run"])

        save_bowler_stats(name, st)

# =========================
# PRIZE BOARD
# =========================

def pct(a, b):
    return (100.0 * a / b) if b else 0.0

@tree.command(description="Show individual prize leaders (Saints’ Specials)")
async def awards_individual(interaction: discord.Interaction):
    if not DB.get("bowlers"):
        await interaction.response.send_message("No bowlers created yet.", ephemeral=True)
        return

    rows = []
    for name in sorted(DB["bowlers"].keys()):
        st = get_bowler_stats(name)  # <- returns default stats if none saved yet
        b = get_bowler_by_name(name)

        acc   = b.accuracy if b else 0
        rank  = b.rank if b else 0
        style = b.style if b else 0
        flair = b.flair if b else 0

        rows.append({
            "name": name,
            "team": team_of_bowler(name) or "—",
            "high_game": st.high_game,
            "high_series": st.high_series_3,
            "mvp_score": st.total_pins + st.strikes*5 + st.spares*2 + st.clean_games*10,
            "style": style,
            "flair": flair,
            "rank": rank,
            "accuracy_pct": pct(st.pocket_hits, st.pocket_attempts),
            "strikes": st.strikes,
            "spare_pct": pct(st.spares, st.frames),
            "turkeys": (st.longest_strike_run // 3),
            "splits_conv": st.splits_converted,
            "worst_game": st.worst_game if st.worst_game != 10_000 else 0
        })

    if not rows:
        await interaction.response.send_message("No stats yet. Finish a game first.", ephemeral=True)
        return

    def top(key, reverse=True, filter_fn=None):
        cand = rows if not filter_fn else [r for r in rows if filter_fn(r)]
        if not cand: return None
        return sorted(cand, key=lambda r: r[key], reverse=reverse)[0]


    # ——— Main “Saints’ Specials” winners ———
    hi_game        = top("high_game")
    hi_series      = top("high_series")
    team_stats     = get_stats_bucket().get("teams", {})
    # team awards
    team_rows = []
    for team, rec in team_stats.items():
        stt = TeamSeasonStats.from_dict(rec)
        team_rows.append({"team": team, "high_game": stt.high_game, "high_series": stt.high_series})
    team_hi_game   = sorted(team_rows, key=lambda r: r["high_game"], reverse=True)[0] if team_rows else None
    team_hi_series = sorted(team_rows, key=lambda r: r["high_series"], reverse=True)[0] if team_rows else None

    mvp           = top("mvp_score")
    jersey        = top("rank")            # “Holy Jersey Award” → player rank
    swagger       = top("style")           # “Saint of Swagger” → style
    flair_aw      = top("flair")           # “Flair of the Faithful” → flair
    accuracy      = top("accuracy_pct")
    strike_ap     = top("strikes")
    spare_saint   = top("spare_pct")
    turkey_gospel = top("turkeys")
    split_res     = top("splits_conv")
    booby         = top("worst_game", reverse=False, filter_fn=lambda r: r["worst_game"] > 0)

    e = discord.Embed(
        title="🎳 The Gutter Saints Invitational — Prize Board",
        color=0xe67e22,
        description="*(Final ‘Final’ Updated Board)*"
    )

    # Main prize labels (informational; the actual bracket placement is outside this command)
    main_txt = (
        "🏆 **Main Prizes (Top 4)**\n"
        "1st: **$35M + 70 credits + Double CA** — “The Holy Strike” Champion\n"
        "2nd: **$20M + 40 credits** — “The Saint’s Shadow” Runner-Up\n"
        "3rd: **$10M + 20 credits** — “The Alley Ghost” Third Place\n"
        "4th: **$7.5M + 12 credits** — “The Gutter Prophet” Fourth Place\n"
    )
    e.add_field(name="Main Prizes", value=main_txt, inline=False)

    # Side prizes
    if hi_game:         e.add_field(name="💥 White Russian High Roller", value=f"**{hi_game['name']}** — {hi_game['high_game']}", inline=False)
    if hi_series:       e.add_field(name="📈 The Dude Abides Series", value=f"**{hi_series['name']}** — {hi_series['high_series']}", inline=False)
    if team_hi_game:    e.add_field(name="🎳 The Neon Glow Cup (Team High Game)", value=f"**{team_hi_game['team']}** — {team_hi_game['high_game']}", inline=False)
    if team_hi_series:  e.add_field(name="📊 Saints of the Lane (Team High Series)", value=f"**{team_hi_series['team']}** — {team_hi_series['high_series']}", inline=False)
    if mvp:             e.add_field(name="⭐ Bowling Messiah (MVP – best all-around)", value=f"**{mvp['name']}**", inline=False)
    if jersey:          e.add_field(name="👕 Holy Jersey Award (Best Jersey Design)", value=f"**{jersey['name']}** — rank {jersey['rank']} *(Team: {jersey['team']})*", inline=False)
    if swagger:         e.add_field(name="✨ Saint of Swagger (Best Style)", value=f"**{swagger['name']}** — style {swagger['style']}", inline=False)
    if flair_aw:        e.add_field(name="🎭 Flair of the Faithful (Best Flair)", value=f"**{flair_aw['name']}** — flair {flair_aw['flair']}", inline=False)
    if accuracy:        e.add_field(name="🎯 Cross-Alley Sniper (Accuracy Award)", value=f"**{accuracy['name']}** — {accuracy['accuracy_pct']:.1f}%", inline=False)
    if strike_ap:       e.add_field(name="🔥 Strike Apostle (Most Strikes)", value=f"**{strike_ap['name']}** — {strike_ap['strikes']}", inline=False)
    if spare_saint:     e.add_field(name="🧩 Saint of Spares (Highest spare %)", value=f"**{spare_saint['name']}** — {spare_saint['spare_pct']:.1f}%", inline=False)
    if turkey_gospel:   e.add_field(name="🍗 Turkey Gospel (Most consecutive turkeys)", value=f"**{turkey_gospel['name']}** — {turkey_gospel['turkeys']}", inline=False)
    if split_res:       e.add_field(name="💥 Split Resurrection (Most outrageous split conversion)", value=f"**{split_res['name']}** — {split_res['splits_conv']}", inline=False)
    if booby:           e.add_field(name="🪣 The JimCasey Memorial Gutterball (Worst Player)", value=f"**{booby['name']}** — {booby['worst_game']}", inline=False)

    # Special Add-On Prize (informational)
    e.add_field(
        name="🎲 Special Add-On Prize",
        value="“The Matt-Proof Miracle Quad” – **1 Quad CA** *(Awarded by fate’s hand, but locked away from Matt forever.)*",
        inline=False
    )

    await interaction.response.send_message(embed=e)

@tree.command(description="Show all players’ cumulative prize-tracking stats")
async def show_all_player_stat(interaction: discord.Interaction):
    bowl_stats = get_stats_bucket().get("bowlers", {})
    if not bowl_stats:
        await interaction.response.send_message("No stats yet. Finish a game first.", ephemeral=True)
        return

    # Build a summary line for each bowler
    lines = []
    for name, rec in bowl_stats.items():
        st = BowlerSeasonStats.from_dict(rec)
        b = get_bowler_by_name(name)
        acc = b.accuracy if b else 0
        rank = b.rank if b else 0
        style = b.style if b else 0
        flair = b.flair if b else 0
        cons = b.consistency if b else 0
        spin = b.spin if b else 0
        nerves = b.nerves if b else 0

        team = team_of_bowler(name) or "—"
        acc_pct = pct(st.pocket_hits, st.pocket_attempts)
        spare_pct = pct(st.spares, st.frames)
        turkeys = st.longest_strike_run // 3
        worst = st.worst_game if st.worst_game != 10_000 else 0

        line = (
            f"**{name}** (Team: {team})\n"
            f"• Games {st.games} | Pins {st.total_pins} | HighG {st.high_game} | HighS {st.high_series_3}\n"
            f"• Strikes {st.strikes} | Spares {st.spares} | Clean {st.clean_games}\n"
            f"• Pocket% {acc_pct:.1f}% | Spare% {spare_pct:.1f}% | Turkeys {turkeys} | Splits {st.splits_converted} | Worst {worst}\n"
            f"• Stats — ACC {acc} | RANK {rank} | STYLE {style} | FLAIR {flair} | CONS {cons} | SPIN {spin} | NERV {nerves}"
        )
        lines.append(line)

    # Chunk into multiple fields (<=1024 chars per field, <=25 total fields)
    embed = discord.Embed(title="All Player Stats — Prize Tracking", color=0x7289DA)
    MAX = 1024
    parts = []
    buf = []
    cur = 0
    for ln in lines:
        extra = (1 if buf else 0) + len(ln)
        if cur + extra > MAX:
            parts.append("\n\n".join(buf))
            buf = [ln]
            cur = len(ln)
        else:
            if buf:
                cur += 2  # for double newline join
            buf.append(ln)
            cur += len(ln)
    if buf:
        parts.append("\n\n".join(buf))

    # Keep under 25 fields; summarize overflow
    if len(parts) > 24:
        visible = parts[:24]
        hidden = len(parts) - 24
        parts = visible + [f"…and **{hidden}** more sections not shown. Narrow your query or export."]

    for i, block in enumerate(parts, 1):
        embed.add_field(name=f"Players ({i})", value=block[:1024] if block else "—", inline=False)

    await interaction.response.send_message(embed=embed)

@tree.command(description="Show team prize leaders")
async def awards_team(interaction: discord.Interaction):
    stats = get_stats_bucket().get("teams", {})
    if not stats:
        await interaction.response.send_message("No team stats yet. Finish a game first.", ephemeral=True); return
    rows = []
    for team, rec in stats.items():
        st = TeamSeasonStats.from_dict(rec)
        rows.append({"team": team, "high_game": st.high_game, "high_series": st.high_series, "total": st.total_pins})
    if not rows:
        await interaction.response.send_message("No team stats yet.", ephemeral=True); return
    hg = sorted(rows, key=lambda r: r["high_game"], reverse=True)[0]
    hs = sorted(rows, key=lambda r: r["high_series"], reverse=True)[0]
    e = discord.Embed(title="🏆 Team Awards", color=0x3498db)
    e.add_field(name="🎳 The Neon Glow Cup (Team High Game)", value=f"**{hg['team']}** — {hg['high_game']}", inline=False)
    e.add_field(name="📊 Saints of the Lane (Team High Series)", value=f"**{hs['team']}** — {hs['high_series']}", inline=False)
    await interaction.response.send_message(embed=e)

@tree.command(description="Draw Clean Game Raffle from last game")
async def awards_cleanraffle(interaction: discord.Interaction):
    gs = active_game(interaction.guild_id or 0)
    if gs and gs.is_active:
        await interaction.response.send_message("Finish the game first to draw the raffle.", ephemeral=True); return
    # Find the most recent completed game’s players from DB games record if you keep history;
    # We’ll derive from stats instead: list bowlers with a clean game in their most recent entry.
    # Simpler: show all bowlers with at least one clean game this season.
    stats = get_stats_bucket().get("bowlers", {})
    eligible = [name for name, rec in stats.items() if BowlerSeasonStats.from_dict(rec).clean_games > 0]
    if not eligible:
        await interaction.response.send_message("No eligible clean games yet.", ephemeral=True); return
    import random
    winner = random.choice(eligible)
    await interaction.response.send_message(f"🎟️ **Clean Slate Raffle** winner: **{winner}**")

@tree.command(description="Clear/remove the current game record (admin only)")
async def game_clear(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("⛔ Admin only.", ephemeral=True)
        return

    gid = str(interaction.guild_id or 0)
    if gid not in DB["games"] or not DB["games"][gid]:
        await interaction.response.send_message("No game found to clear.", ephemeral=True)
        return

    # Delete the game entry
    DB["games"].pop(gid, None)
    save_db()

    await send_log(bot, interaction.guild_id or 0, f"🗑️ Game record cleared by {interaction.user}")
    await interaction.response.send_message("🗑️ Current game record removed.", ephemeral=True)

@tree.command(description="Show how many finished games are archived for this server")
async def games_history(interaction: discord.Interaction):
    bucket = get_game_archive_bucket()
    gk = str(interaction.guild_id or 0)
    lst = bucket.get(gk, [])
    await interaction.response.send_message(f"Archived games for this server: **{len(lst)}**", ephemeral=True)

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("Set DISCORD_TOKEN in .env");
        raise SystemExit(1)
    bot.run(token)
