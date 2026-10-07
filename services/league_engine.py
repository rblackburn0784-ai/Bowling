import itertools, math
from storage.database import connect

STATES=('draft','registration','locked','active','completed','archived')
FORMATS=('single_elimination','double_elimination','round_robin','groups_knockout','stepladder','best_of','qualifying')
ENTRANTS=('team','individual')

def create_season(name,status='draft'):
 with connect() as c:return c.execute('INSERT INTO seasons(name,status) VALUES(?,?)',(name,status)).lastrowid

def create_competition(name,season_id=None,kind='league',format='round_robin',entrant_type='team',lane='house',points=(3,1,0),playoff_size=0,promotion=0,relegation=0):
 if format not in FORMATS:raise ValueError('Unsupported competition format.')
 if entrant_type not in ENTRANTS:raise ValueError('entrant_type must be team or individual.')
 with connect() as c:
  return c.execute('INSERT INTO competitions(season_id,name,kind,format,entrant_type,lane_condition,points_win,points_draw,points_loss,playoff_size,promotion_slots,relegation_slots) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(season_id,name,kind,format,entrant_type,lane,*points,playoff_size,promotion,relegation)).lastrowid

def competition(name):
 with connect() as c:return c.execute('SELECT * FROM competitions WHERE name=? COLLATE NOCASE ORDER BY id DESC LIMIT 1',(name,)).fetchone()

def transition(cid,target):
 if target not in STATES:return False,'Invalid state.'
 with connect() as c:
  x=c.execute('SELECT * FROM competitions WHERE id=?',(cid,)).fetchone()
  if not x:return False,'Competition not found.'
  cur=STATES.index(x['state']);nxt=STATES.index(target)
  if nxt!=cur+1:return False,f"State must move {STATES[cur]} → {STATES[cur+1] if cur+1<len(STATES) else 'none'}."
  if target=='locked':
   n=c.execute('SELECT COUNT(*) n FROM competition_entries WHERE competition_id=?',(cid,)).fetchone()['n']
   if n<2:return False,'At least two entrants are required.'
   if x['entrant_type']=='team':
    c.execute('DELETE FROM competition_rosters WHERE competition_id=?',(cid,))
    c.execute('''INSERT INTO competition_rosters(competition_id,team_id,bowler_id,slot)
      SELECT ?,tm.team_id,tm.bowler_id,tm.slot FROM team_members tm
      JOIN competition_entries e ON e.entrant_id=tm.team_id AND e.competition_id=?''',(cid,cid))
  stamps={'active':'started_at','completed':'completed_at','archived':'archived_at'}
  col=stamps.get(target)
  c.execute(f"UPDATE competitions SET state=?{','+col+'=CURRENT_TIMESTAMP' if col else ''} WHERE id=?",(target,cid))
 return True,None

def register(cid,entrant_id,seed=None,group=None):
 with connect() as c:
  x=c.execute('SELECT state,entrant_type FROM competitions WHERE id=?',(cid,)).fetchone()
  if not x or x['state']!='registration':return False
  table='teams' if x['entrant_type']=='team' else 'bowlers'
  if not c.execute(f'SELECT 1 FROM {table} WHERE id=?',(entrant_id,)).fetchone():return False
  c.execute('INSERT OR REPLACE INTO competition_entries(competition_id,entrant_id,seed,group_name) VALUES(?,?,?,?)',(cid,entrant_id,seed,group));return True

def _entries(c,cid):
 return [r['entrant_id'] for r in c.execute('SELECT entrant_id FROM competition_entries WHERE competition_id=? ORDER BY CASE WHEN seed IS NULL THEN 999999 ELSE seed END,entrant_id',(cid,))]

def _stage(c,cid,no,name,fmt,qualify=0,best_of=1):
 return c.execute('INSERT OR IGNORE INTO competition_stages(competition_id,stage_no,name,format,status,qualify_count,best_of) VALUES(?,?,?,?,?,?,?)',(cid,no,name,fmt,'active',qualify,best_of)).lastrowid or c.execute('SELECT id FROM competition_stages WHERE competition_id=? AND stage_no=?',(cid,no)).fetchone()['id']

def _fixture(c,cid,sid,r,n,a,b,best=1,status='scheduled',winner=None):
 c.execute('INSERT OR IGNORE INTO fixtures(competition_id,stage_id,round_no,fixture_no,home_id,away_id,status,winner_id,series_best_of) VALUES(?,?,?,?,?,?,?,?,?)',(cid,sid,r,n,a,b,status,winner,best))

def generate_schedule(cid):
 with connect() as c:
  x=c.execute('SELECT * FROM competitions WHERE id=?',(cid,)).fetchone()
  if not x or x['state']!='locked':return False,'Competition must be locked before scheduling.'
  ids=_entries(c,cid);fmt=x['format']
  if fmt=='round_robin':
   sid=_stage(c,cid,1,'Regular Season','round_robin')
   arr=ids+([None] if len(ids)%2 else []);rounds=len(arr)-1
   for r in range(rounds):
    for n in range(len(arr)//2):
     a,b=arr[n],arr[-1-n]
     if a and b:_fixture(c,cid,sid,r+1,n+1,a,b)
    arr=[arr[0],arr[-1],*arr[1:-1]]
  elif fmt in ('single_elimination','best_of'):
   sid=_stage(c,cid,1,'Knockout','single_elimination',best_of=3 if fmt=='best_of' else 1)
   size=1
   while size<len(ids):size*=2
   arr=ids+[None]*(size-len(ids))
   for n in range(size//2):
    a,b=arr[n],arr[-1-n];w=a if a and not b else b if b and not a else None
    _fixture(c,cid,sid,1,n+1,a,b,3 if fmt=='best_of' else 1,'complete' if w else 'scheduled',w)
  elif fmt=='stepladder':
   sid=_stage(c,cid,1,'Stepladder','stepladder')
   ordered=list(reversed(ids))
   if len(ordered)>=2:_fixture(c,cid,sid,1,1,ordered[0],ordered[1])
  elif fmt=='qualifying':
   sid=_stage(c,cid,1,'Qualifying','qualifying',x['playoff_size'] or max(2,len(ids)//2))
   for n,e in enumerate(ids,1):_fixture(c,cid,sid,1,n,e,None,status='scheduled')
  elif fmt=='groups_knockout':
   sid=_stage(c,cid,1,'Group Stage','round_robin',x['playoff_size'] or 4)
   groups={}
   rows=c.execute('SELECT entrant_id,COALESCE(group_name,"A") g FROM competition_entries WHERE competition_id=?',(cid,)).fetchall()
   for r in rows:groups.setdefault(r['g'],[]).append(r['entrant_id'])
   no=1
   for group,members in groups.items():
    for a,b in itertools.combinations(members,2):_fixture(c,cid,sid,1,no,a,b);no+=1
  elif fmt=='double_elimination':
   sid=_stage(c,cid,1,'Winners Bracket','double_elimination')
   for n,(a,b) in enumerate(zip(ids[::2],ids[1::2]),1):_fixture(c,cid,sid,1,n,a,b)
  else:return False,'Unsupported format.'
  for e in ids:c.execute('INSERT OR IGNORE INTO competition_standings(competition_id,entrant_id) VALUES(?,?)',(cid,e))
 return True,None

def report_fixture(fid,home_score,away_score):
 with connect() as c:
  f=c.execute('SELECT f.*,co.* FROM fixtures f JOIN competitions co ON co.id=f.competition_id WHERE f.id=?',(fid,)).fetchone()
  if not f or f['state']!='active' or f['status']=='complete':return False,'Fixture is not playable.'
  if f['away_id'] is None:return False,'Qualifying fixtures require game-result integration.'
  winner=f['home_id'] if home_score>away_score else f['away_id'] if away_score>home_score else None
  c.execute('UPDATE fixtures SET home_score=?,away_score=?,winner_id=?,status="complete",played_at=CURRENT_TIMESTAMP WHERE id=?',(home_score,away_score,winner,fid))
  hp=f['points_win'] if winner==f['home_id'] else f['points_draw'] if winner is None else f['points_loss'];ap=f['points_win'] if winner==f['away_id'] else f['points_draw'] if winner is None else f['points_loss']
  for eid,pf,pa,pts,w,d,l in ((f['home_id'],home_score,away_score,hp,int(winner==f['home_id']),int(winner is None),int(winner==f['away_id'])),(f['away_id'],away_score,home_score,ap,int(winner==f['away_id']),int(winner is None),int(winner==f['home_id']))):
   c.execute('UPDATE competition_standings SET played=played+1,wins=wins+?,draws=draws+?,losses=losses+?,pins_for=pins_for+?,pins_against=pins_against+?,points=points+? WHERE competition_id=? AND entrant_id=?',(w,d,l,pf,pa,pts,f['competition_id'],eid))
 return True,None

def standings(cid):
 with connect() as c:
  x=c.execute('SELECT entrant_type FROM competitions WHERE id=?',(cid,)).fetchone()
  if not x:return []
  table='teams' if x['entrant_type']=='team' else 'bowlers'
  return c.execute(f'''SELECT s.*,e.name,(s.pins_for-s.pins_against) differential FROM competition_standings s JOIN {table} e ON e.id=s.entrant_id WHERE s.competition_id=? ORDER BY points DESC,differential DESC,pins_for DESC,e.name''',(cid,)).fetchall()

def season_leaders(season_id):
 with connect() as c:return c.execute('''SELECT b.name,s.*,s.total_pins*1.0/NULLIF(s.games,0) average FROM season_bowler_stats s JOIN bowlers b ON b.id=s.bowler_id WHERE s.season_id=? ORDER BY average DESC''',(season_id,)).fetchall()

def create_template(name,format='round_robin',entrant_type='team',lane='house',points=(3,1,0),playoff_size=0,promotion=0,relegation=0,recurrence=None):
 with connect() as c:return c.execute('INSERT INTO league_templates(name,format,entrant_type,lane_condition,points_win,points_draw,points_loss,playoff_size,promotion_slots,relegation_slots,recurrence) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(name,format,entrant_type,lane,*points,playoff_size,promotion,relegation,recurrence)).lastrowid
