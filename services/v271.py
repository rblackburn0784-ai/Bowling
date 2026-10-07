from storage.database import connect
from services.equipment import BALLS
from services.lane_physics import PATTERNS

LAYOUTS=("standard","broadcast","finals","chaos")

def bowler_loadout(bowler_id):
    with connect() as c:
        r=c.execute("SELECT primary_ball,avatar_url FROM bowler_presentation WHERE bowler_id=?",(bowler_id,)).fetchone()
    return dict(r) if r else {"primary_ball":"hybrid","avatar_url":None}

def set_bowler_ball(bowler_id,key):
    if key not in BALLS:return False
    with connect() as c:
        c.execute("INSERT INTO bowler_presentation(bowler_id,primary_ball) VALUES(?,?) ON CONFLICT(bowler_id) DO UPDATE SET primary_ball=excluded.primary_ball",(bowler_id,key))
    return True

def set_bowler_avatar(bowler_id,url):
    with connect() as c:
        c.execute("INSERT INTO bowler_presentation(bowler_id,avatar_url) VALUES(?,?) ON CONFLICT(bowler_id) DO UPDATE SET avatar_url=excluded.avatar_url",(bowler_id,url))
    return True

def team_presentation(team_name):
    with connect() as c:
        r=c.execute("SELECT t.id,p.logo_url FROM teams t LEFT JOIN team_presentation p ON p.team_id=t.id WHERE t.name=? COLLATE NOCASE",(team_name,)).fetchone()
    return dict(r) if r else None

def set_team_logo(team_name,url):
    with connect() as c:
        t=c.execute("SELECT id FROM teams WHERE name=? COLLATE NOCASE",(team_name,)).fetchone()
        if not t:return False
        c.execute("INSERT INTO team_presentation(team_id,logo_url) VALUES(?,?) ON CONFLICT(team_id) DO UPDATE SET logo_url=excluded.logo_url",(t["id"],url))
    return True

def set_tournament_presentation(name,pattern=None,layout=None,lane_start=None,brand_title=None,background_url=None):
    if pattern is not None and pattern not in PATTERNS:return False,"Unknown oil pattern."
    if layout is not None and layout not in LAYOUTS:return False,"Unknown layout."
    if lane_start is not None and (lane_start<1 or lane_start>59 or lane_start%2==0):return False,"Lane pair must start on an odd lane (1, 3, 5...)."
    with connect() as c:
        t=c.execute("SELECT id FROM tournaments WHERE name=? COLLATE NOCASE",(name,)).fetchone()
        if not t:return False,"Tournament not found."
        c.execute("INSERT OR IGNORE INTO tournament_presentation(tournament_id) VALUES(?)",(t["id"],))
        if pattern is not None:c.execute("UPDATE tournaments SET lane_condition=? WHERE id=?",(pattern,t["id"]))
        if layout is not None:c.execute("UPDATE tournament_presentation SET layout=? WHERE tournament_id=?",(layout,t["id"]))
        if lane_start is not None:c.execute("UPDATE tournament_presentation SET lane_start=? WHERE tournament_id=?",(lane_start,t["id"]))
        if brand_title is not None:c.execute("UPDATE tournament_presentation SET brand_title=? WHERE tournament_id=?",(brand_title or None,t["id"]))
        if background_url is not None:c.execute("UPDATE tournament_presentation SET background_url=? WHERE tournament_id=?",(background_url or None,t["id"]))
    return True,None

def tournament_presentation(tournament_id):
    with connect() as c:
        r=c.execute("SELECT t.lane_condition,p.layout,p.lane_start,p.brand_title,p.background_url FROM tournaments t LEFT JOIN tournament_presentation p ON p.tournament_id=t.id WHERE t.id=?",(tournament_id,)).fetchone()
    if not r:return {"lane_condition":"house","layout":"broadcast","lane_start":3,"brand_title":None,"background_url":None}
    d=dict(r);d["layout"]=d["layout"] or "broadcast";d["lane_start"]=d["lane_start"] or 3;return d
