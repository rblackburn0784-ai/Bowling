import math,random
from storage.database import connect

def team(name):
    with connect() as c:return c.execute('SELECT * FROM teams WHERE name=? COLLATE NOCASE',(name,)).fetchone()

def create_series(name,a,b,best_of=3):
    ta,tb=team(a),team(b)
    if not ta or not tb:return None
    with connect() as c:return c.execute('INSERT INTO series(name,team_a_id,team_b_id,best_of) VALUES(?,?,?,?)',(name,ta['id'],tb['id'],best_of)).lastrowid

def create_tournament(name,lane='house'):
    with connect() as c:return c.execute('INSERT INTO tournaments(name,lane_condition) VALUES(?,?)',(name,lane)).lastrowid

def add_entry(tname,team_name,seed=None):
    with connect() as c:
        t=c.execute('SELECT id,status FROM tournaments WHERE name=? COLLATE NOCASE',(tname,)).fetchone(); tm=c.execute('SELECT id FROM teams WHERE name=? COLLATE NOCASE',(team_name,)).fetchone()
        if not t or not tm or t['status']!='registration':return False
        c.execute('INSERT OR REPLACE INTO tournament_entries(tournament_id,team_id,seed) VALUES(?,?,?)',(t['id'],tm['id'],seed));return True

def start_tournament(name):
    with connect() as c:
        t=c.execute('SELECT * FROM tournaments WHERE name=? COLLATE NOCASE',(name,)).fetchone()
        if not t:return None,'Tournament not found.'
        entries=c.execute('SELECT e.*,tm.name FROM tournament_entries e JOIN teams tm ON tm.id=e.team_id WHERE tournament_id=? ORDER BY CASE WHEN seed IS NULL THEN 999999 ELSE seed END,tm.name',(t['id'],)).fetchall()
        if len(entries)<2:return None,'At least two teams are required.'
        n=1
        while n<len(entries):n*=2
        ids=[x['team_id'] for x in entries]+[None]*(n-len(entries)); pairs=[]
        for i in range(n//2):pairs.append((ids[i],ids[n-1-i]))
        c.execute("UPDATE tournaments SET status='active' WHERE id=?",(t['id'],))
        for m,(a,b) in enumerate(pairs,1):
            winner=a if a and not b else b if b and not a else None; status='complete' if winner else 'pending'
            c.execute('INSERT OR REPLACE INTO tournament_matches(tournament_id,round_no,match_no,team_a_id,team_b_id,winner_id,status) VALUES(?,?,?,?,?,?,?)',(t['id'],1,m,a,b,winner,status))
        _advance_byes(c,t['id'])
        return t['id'],None

def _advance_byes(c,tid):
    while True:
        r=c.execute('SELECT MAX(round_no) r FROM tournament_matches WHERE tournament_id=?',(tid,)).fetchone()['r']
        rows=c.execute('SELECT * FROM tournament_matches WHERE tournament_id=? AND round_no=? ORDER BY match_no',(tid,r)).fetchall()
        if not rows or any(x['status']!='complete' for x in rows):return
        if len(rows)==1:
            c.execute("UPDATE tournaments SET status='complete',finished_at=CURRENT_TIMESTAMP WHERE id=?",(tid,));return
        winners=[x['winner_id'] for x in rows]
        for i in range(0,len(winners),2):
            a=winners[i];b=winners[i+1] if i+1<len(winners) else None; w=a if a and not b else None; st='complete' if w else 'pending'
            c.execute('INSERT OR IGNORE INTO tournament_matches(tournament_id,round_no,match_no,team_a_id,team_b_id,winner_id,status) VALUES(?,?,?,?,?,?,?)',(tid,r+1,i//2+1,a,b,w,st))

def report_match(tname,round_no,match_no,score_a,score_b):
    if score_a==score_b:return False,'Tournament matches cannot end tied.'
    with connect() as c:
        t=c.execute('SELECT id FROM tournaments WHERE name=? COLLATE NOCASE',(tname,)).fetchone()
        if not t:return False,'Tournament not found.'
        m=c.execute('SELECT * FROM tournament_matches WHERE tournament_id=? AND round_no=? AND match_no=?',(t['id'],round_no,match_no)).fetchone()
        if not m or not m['team_a_id'] or not m['team_b_id']:return False,'Playable match not found.'
        w=m['team_a_id'] if score_a>score_b else m['team_b_id']
        c.execute("UPDATE tournament_matches SET score_a=?,score_b=?,winner_id=?,status='complete' WHERE id=?",(score_a,score_b,w,m['id']));_advance_byes(c,t['id']);return True,None

def bracket(name):
    with connect() as c:
        t=c.execute('SELECT * FROM tournaments WHERE name=? COLLATE NOCASE',(name,)).fetchone()
        if not t:return None,[]
        rows=c.execute('''SELECT m.*,a.name team_a,b.name team_b,w.name winner FROM tournament_matches m LEFT JOIN teams a ON a.id=m.team_a_id LEFT JOIN teams b ON b.id=m.team_b_id LEFT JOIN teams w ON w.id=m.winner_id WHERE m.tournament_id=? ORDER BY round_no,match_no''',(t['id'],)).fetchall();return t,rows
