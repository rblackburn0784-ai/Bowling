"""v2.9.2 career records, earned milestones, and competition integrity read models.

Only committed regulation games contribute. Queries never modify match state and
no simulation RNG is used. Importable without discord.py.
"""
from contextlib import nullcontext
from storage.database import connect
from services.career import ATTRS, rank_from_xp, rank_title, rank_progress

# Lifetime thresholds: each code is a one-time, idempotent achievement.
MILESTONES = (
    ('debut', 'League Debut', 'Completed a first ranked game.', 'games', 1),
    ('regular_10', 'Regular', 'Completed 10 ranked games.', 'games', 10),
    ('veteran_25', 'Seasoned Bowler', 'Completed 25 ranked games.', 'games', 25),
    ('veteran_50', 'Veteran', 'Completed 50 ranked games.', 'games', 50),
    ('centurion', 'Century Club', 'Completed 100 ranked games.', 'games', 100),
    ('striker_50', 'Strike Collector', 'Recorded 50 career strikes.', 'strikes', 50),
    ('striker_100', 'Strike Specialist', 'Recorded 100 career strikes.', 'strikes', 100),
    ('spare_50', 'Spare Specialist', 'Converted 50 career spares.', 'spares', 50),
    ('clean_5', 'Clean Machine', 'Completed five clean games.', 'clean_games', 5),
    ('clean_10', 'Spotless', 'Completed ten clean games.', 'clean_games', 10),
    ('splits_5', 'Split Artist', 'Converted five career splits.', 'split_conversions', 5),
    ('splits_20', 'Split Surgeon', 'Converted 20 career splits.', 'split_conversions', 20),
)

BOARDS = {
    'average': ('s.total_pins * 1.0 / s.games', 's.games >= ?', 'Average', 3),
    'high_game': ('s.high_game', 's.games > 0', 'High Game', None),
    'perfect_games': ('s.perfect_games', 's.games > 0', 'Perfect Games', None),
    'strikes': ('s.strikes', 's.games > 0', 'Career Strikes', None),
    'spares': ('s.spares', 's.games > 0', 'Career Spares', None),
    'split_conversions': ('s.split_conversions', 's.games > 0', 'Split Conversions', None),
    'clean_games': ('s.clean_games', 's.games > 0', 'Clean Games', None),
    'games': ('s.games', 's.games > 0', 'Games Played', None),
}


def unlock_career_milestones(bowler_id, db=None):
    """Call in the same post-game transaction, *after* bowler_stats updates."""
    with (nullcontext(db) if db is not None else connect()) as c:
        s = c.execute('SELECT * FROM bowler_stats WHERE bowler_id=?', (bowler_id,)).fetchone()
        if not s:
            return []
        new = []
        for code, title, detail, stat, minimum in MILESTONES:
            if (s[stat] or 0) >= minimum:
                cur = c.execute('INSERT OR IGNORE INTO achievements(bowler_id,code,title,detail) VALUES(?,?,?,?)',
                                (bowler_id, code, title, detail))
                if cur.rowcount:
                    new.append((title, detail))
        return new


def career_profile(bowler_id, db=None):
    with (nullcontext(db) if db is not None else connect()) as c:
        r = c.execute('''SELECT b.*,COALESCE(s.games,0) games,COALESCE(s.total_pins,0) pins,
                     COALESCE(s.high_game,0) high_game,COALESCE(s.strikes,0) strikes,
                     COALESCE(s.spares,0) spares,COALESCE(s.clean_games,0) clean_games,
                     COALESCE(s.split_conversions,0) split_conversions,
                     COALESCE(p.xp,0) xp,COALESCE(p.credits,0) credits,
                     COALESCE(e.cosmetic_xp,0) cosmetic_xp
                  FROM bowlers b LEFT JOIN bowler_stats s ON b.id=s.bowler_id
                  LEFT JOIN bowler_progression p ON b.id=p.bowler_id
                  LEFT JOIN exhibition_rewards e ON b.id=e.bowler_id
                  WHERE b.id=?''', (bowler_id,)).fetchone()
        if not r:return None
        d=dict(r);d['average']=round(d['pins']/d['games'],2) if d['games'] else 0.0
        d['rank_expected']=rank_from_xp(d['xp'])
        d['rank_title']=rank_title(d['rank'])
        d['rank_percent'],d['next_rank_xp']=rank_progress(d['xp'],d['rank_expected'])
        d['attributes']={stat:d[stat] for stat in ATTRS}
        d['achievement_count']=c.execute('SELECT COUNT(*) FROM achievements WHERE bowler_id=?',(bowler_id,)).fetchone()[0]
        d['honours_count']=c.execute('SELECT COUNT(*) FROM career_honours WHERE bowler_id=?',(bowler_id,)).fetchone()[0]
        return d


def leaderboard(category='average',limit=10,min_games=3,db=None):
    if category not in BOARDS:raise ValueError('Unknown leaderboard category')
    if type(limit) is not int or not 1<=limit<=25:raise ValueError('Limit must be 1–25')
    if type(min_games) is not int or min_games<1:raise ValueError('Minimum games must be positive')
    metric,predicate,label,default_min=BOARDS[category]
    params=(min_games,limit) if default_min is not None else (limit,)
    with (nullcontext(db) if db is not None else connect()) as c:
        rs=c.execute(f'''SELECT b.id,b.name,s.games,s.high_game,s.strikes,s.spares,
                          s.split_conversions,s.clean_games,s.perfect_games,
                          ROUND(s.total_pins*1.0/s.games,2) average,
                          {metric} value FROM bowler_stats s JOIN bowlers b ON b.id=s.bowler_id
                          WHERE {predicate} ORDER BY value DESC,s.games DESC,b.name COLLATE NOCASE,b.id LIMIT ?''',params).fetchall()
        return label,[dict(x) for x in rs]


def competition_health(competition_id,db=None):
    """Non-mutating pre-flight: safe for admin dashboards and live fixtures."""
    with (nullcontext(db) if db is not None else connect()) as c:
        co=c.execute('SELECT id,name,state,format FROM competitions WHERE id=?',(competition_id,)).fetchone()
        if not co:return None
        fixtures=c.execute('SELECT * FROM fixtures WHERE competition_id=? ORDER BY stage_id,round_no,fixture_no',(competition_id,)).fetchall()
        issues=[]
        for f in fixtures:
            if f['status']=='complete' and f['home_id'] is not None and f['away_id'] is not None and (f['home_score'] is None or f['away_score'] is None):
                issues.append(f"Fixture #{f['id']}: completed without a score")
            if any(f[k] is not None and f[k]<0 for k in ('home_score','away_score')):
                issues.append(f"Fixture #{f['id']}: negative score")
            if f['status']=='playing':
                assigned=c.execute('SELECT COUNT(*) FROM fixture_games WHERE fixture_id=?',(f['id'],)).fetchone()[0]
                if not f['home_id'] or not f['away_id']:
                    issues.append(f"Fixture #{f['id']}: playing with a missing entrant")
                if assigned==0:issues.append(f"Fixture #{f['id']}: playing (check live session or recover)")
            if f['status']=='complete' and f['winner_id'] is not None and f['winner_id'] not in (f['home_id'],f['away_id']):
                issues.append(f"Fixture #{f['id']}: winner does not match entrants")
        if co['state'] in ('completed','archived') and any(f['status'] in ('scheduled','playing') and f['home_id'] and f['away_id'] for f in fixtures):
            issues.append('Competition closed while playable fixtures remain unfinished')
        next_up=next((f for f in fixtures if f['status']=='scheduled' and f['home_id'] and f['away_id']),None)
        completed=sum(f['status']=='complete' for f in fixtures)
        return {'name':co['name'],'state':co['state'],'format':co['format'],
                'total':len(fixtures),'completed':completed,'next_fixture_id':next_up['id'] if next_up else None,
                'issues':issues}
