from models.bowler import Bowler
from storage.database import connect

def create_bowler(b: Bowler):
    with connect() as con:
        cur=con.execute("INSERT INTO bowlers(name,owner_id,handedness,rank,accuracy,style,flair,consistency,spin,nerves) VALUES(?,?,?,?,?,?,?,?,?,?)",(b.name,b.owner_id,b.handedness,1,b.accuracy,b.style,b.flair,b.consistency,b.spin,b.nerves))
        con.execute("INSERT OR IGNORE INTO bowler_stats(bowler_id) VALUES(?)",(cur.lastrowid,)); con.execute("INSERT INTO bowler_origins(bowler_id,accuracy,consistency,spin,nerves,style,flair) VALUES(?,?,?,?,?,?,?)",(cur.lastrowid,b.accuracy,b.consistency,b.spin,b.nerves,b.style,b.flair)); return cur.lastrowid

def get_bowler(name):
    with connect() as con:r=con.execute("SELECT * FROM bowlers WHERE name=? COLLATE NOCASE",(name,)).fetchone()
    return Bowler(**{k:r[k] for k in ['id','name','owner_id','handedness','rank','accuracy','style','flair','consistency','spin','nerves']}) if r else None

def get_bowler_by_owner(owner_id):
    with connect() as con:r=con.execute("SELECT * FROM bowlers WHERE owner_id=? ORDER BY id LIMIT 1",(owner_id,)).fetchone()
    return Bowler(**{k:r[k] for k in ['id','name','owner_id','handedness','rank','accuracy','style','flair','consistency','spin','nerves']}) if r else None

def update_owned_bowler(owner_id,name,handedness,rank,accuracy,style,flair,consistency,spin,nerves):
    with connect() as con:
        r=con.execute('SELECT id FROM bowlers WHERE owner_id=? ORDER BY id LIMIT 1',(owner_id,)).fetchone()
        if not r:return False,'You do not have a bowler yet.'
        try:con.execute('UPDATE bowlers SET name=?,handedness=?,rank=?,accuracy=?,style=?,flair=?,consistency=?,spin=?,nerves=? WHERE id=?',(name,handedness,rank,accuracy,style,flair,consistency,spin,nerves,r['id']))
        except Exception as e:return False,str(e)
        return True,None

def list_bowlers():
    with connect() as con:return con.execute("SELECT * FROM bowlers ORDER BY name COLLATE NOCASE").fetchall()

def create_team(name,captain_id,flair=0):
    with connect() as con:return con.execute("INSERT INTO teams(name,captain_id,flair) VALUES(?,?,?)",(name,captain_id,flair)).lastrowid

def add_team_member(team_name,bowler_name,slot):
    with connect() as con:
        t=con.execute("SELECT id FROM teams WHERE name=? COLLATE NOCASE",(team_name,)).fetchone();b=con.execute("SELECT id FROM bowlers WHERE name=? COLLATE NOCASE",(bowler_name,)).fetchone()
        if not t or not b:return False
        con.execute("INSERT OR REPLACE INTO team_members(team_id,bowler_id,slot) VALUES(?,?,?)",(t['id'],b['id'],slot));return True

def team_roster(team_name):
    with connect() as con:return con.execute("SELECT b.*,tm.slot FROM teams t JOIN team_members tm ON tm.team_id=t.id JOIN bowlers b ON b.id=tm.bowler_id WHERE t.name=? COLLATE NOCASE ORDER BY tm.slot",(team_name,)).fetchall()
