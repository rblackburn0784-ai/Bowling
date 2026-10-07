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

def _fixture(c,cid,sid,r,n,a,b,best=1,status='scheduled',winner=None,bracket='main'):
 c.execute('INSERT OR IGNORE INTO fixtures(competition_id,stage_id,round_no,fixture_no,home_id,away_id,status,winner_id,series_best_of,bracket) VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,sid,r,n,a,b,status,winner,best,bracket))

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
   sid=_stage(c,cid,1,'Qualifying','round_robin',x['playoff_size'] or max(2,len(ids)//2))
   arr=ids+([None] if len(ids)%2 else [])
   for r in range(len(arr)-1):
    for n in range(len(arr)//2):
     a,b=arr[n],arr[-1-n]
     if a and b:_fixture(c,cid,sid,r+1,n+1,a,b)
    arr=[arr[0],arr[-1],*arr[1:-1]]
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
  if f['status'] not in ('scheduled','playing'):return False,'Fixture is not playable.'
  winner=f['home_id'] if home_score>away_score else f['away_id'] if away_score>home_score else None
  c.execute('UPDATE fixtures SET home_score=?,away_score=?,winner_id=?,status="complete",played_at=CURRENT_TIMESTAMP WHERE id=?',(home_score,away_score,winner,fid))
  hp=f['points_win'] if winner==f['home_id'] else f['points_draw'] if winner is None else f['points_loss'];ap=f['points_win'] if winner==f['away_id'] else f['points_draw'] if winner is None else f['points_loss']
  for eid,pf,pa,pts,w,d,l in ((f['home_id'],home_score,away_score,hp,int(winner==f['home_id']),int(winner is None),int(winner==f['away_id'])),(f['away_id'],away_score,home_score,ap,int(winner==f['away_id']),int(winner is None),int(winner==f['home_id']))):
   c.execute('UPDATE competition_standings SET played=played+1,wins=wins+?,draws=draws+?,losses=losses+?,pins_for=pins_for+?,pins_against=pins_against+?,points=points+? WHERE competition_id=? AND entrant_id=?',(w,d,l,pf,pa,pts,f['competition_id'],eid))
 if f['series_best_of']<=1:progress_fixture(fid)
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


def fixture_roster(fixture_id,entrant_id,substitutes=None):
 substitutes=set(substitutes or [])
 with connect() as c:
  f=c.execute('SELECT f.*,co.entrant_type FROM fixtures f JOIN competitions co ON co.id=f.competition_id WHERE f.id=?',(fixture_id,)).fetchone()
  if not f or entrant_id not in (f['home_id'],f['away_id']):return []
  if f['entrant_type']=='individual':return c.execute('SELECT * FROM bowlers WHERE id=?',(entrant_id,)).fetchall()
  rows=c.execute('SELECT b.*,r.slot,r.is_substitute FROM competition_rosters r JOIN bowlers b ON b.id=r.bowler_id WHERE r.competition_id=? AND r.team_id=? ORDER BY r.is_substitute,r.slot',(f['competition_id'],entrant_id)).fetchall()
  active=[r for r in rows if not r['is_substitute']]
  for sub in [r for r in rows if r['bowler_id'] in substitutes and r['is_substitute']]:
   if active:active[-1]=sub
  return active

def set_substitute(cid,team_id,bowler_id,value=True):
 with connect() as c:
  co=c.execute('SELECT state,entrant_type FROM competitions WHERE id=?',(cid,)).fetchone()
  if not co or co['entrant_type']!='team' or co['state'] not in ('locked','active'):return False
  cur=c.execute('UPDATE competition_rosters SET is_substitute=? WHERE competition_id=? AND team_id=? AND bowler_id=?',(int(value),cid,team_id,bowler_id))
  return cur.rowcount>0

def _round(c,co,sid,ids,r,best=1):
 for n in range(0,len(ids),2):
  a=ids[n];b=ids[n+1] if n+1<len(ids) else None;w=a if a and not b else None
  _fixture(c,co['id'],sid,r,n//2+1,a,b,best,'complete' if w else 'scheduled',w)

def _finish(c,co,winner=None):
 c.execute("UPDATE competitions SET state='completed',completed_at=CURRENT_TIMESTAMP WHERE id=?",(co['id'],))
 if winner and co['entrant_type']=='individual' and co['season_id']:
  c.execute('INSERT OR IGNORE INTO season_bowler_stats(season_id,bowler_id) VALUES(?,?)',(co['season_id'],winner));c.execute('UPDATE season_bowler_stats SET championships=championships+1 WHERE season_id=? AND bowler_id=?',(co['season_id'],winner))

def _knockout(c,co,stage):
 r=c.execute('SELECT MAX(round_no) n FROM fixtures WHERE stage_id=?',(stage['id'],)).fetchone()['n'];cur=c.execute('SELECT * FROM fixtures WHERE stage_id=? AND round_no=? ORDER BY fixture_no',(stage['id'],r)).fetchall()
 if not cur or any(x['status']!='complete' for x in cur):return
 ids=[x['winner_id'] for x in cur]
 if len(ids)==1:return _finish(c,co,ids[0])
 if not c.execute('SELECT 1 FROM fixtures WHERE stage_id=? AND round_no=?',(stage['id'],r+1)).fetchone():_round(c,co,stage['id'],ids,r+1,stage['best_of'])


def _groups(c,co,stage):
 if c.execute("SELECT 1 FROM fixtures WHERE stage_id=? AND status!='complete' LIMIT 1",(stage['id'],)).fetchone():return
 erows=c.execute('SELECT entrant_id,COALESCE(group_name,"A") g FROM competition_entries WHERE competition_id=?',(co['id'],)).fetchall();groups={}
 for x in erows:groups.setdefault(x['g'],[]).append(x['entrant_id'])
 qualified=[]
 allstand=standings(co['id'])
 for g in sorted(groups):
  ranked=[x for x in allstand if x['entrant_id'] in groups[g]];qualified+= [x['entrant_id'] for x in ranked[:2]]
 sid=_stage(c,co['id'],2,'Knockout Stage','single_elimination')
 if len(groups)==2 and len(qualified)>=4:qualified=[qualified[0],qualified[3],qualified[2],qualified[1]]
 _round(c,co,sid,qualified,1)

def _stepladder(c,co,stage,last):
 ids=list(reversed(_entries(c,co['id'])));played=c.execute('SELECT COUNT(*) n FROM fixtures WHERE stage_id=?',(stage['id'],)).fetchone()['n']
 if played>=len(ids)-1:return _finish(c,co,last['winner_id'])
 _fixture(c,co['id'],stage['id'],played+1,played+1,last['winner_id'],ids[played+1])

def _double(c,co,stage,last):
 loser=last['away_id'] if last['winner_id']==last['home_id'] else last['home_id']
 c.execute('INSERT OR IGNORE INTO competition_losses(competition_id,entrant_id) VALUES(?,?)',(co['id'],loser));c.execute('UPDATE competition_losses SET losses=losses+1,eliminated=CASE WHEN losses+1>=2 THEN 1 ELSE eliminated END WHERE competition_id=? AND entrant_id=?',(co['id'],loser))
 if c.execute("SELECT 1 FROM fixtures WHERE competition_id=? AND status='scheduled' LIMIT 1",(co['id'],)).fetchone():return
 active=c.execute('''SELECT e.entrant_id,COALESCE(l.losses,0) losses FROM competition_entries e LEFT JOIN competition_losses l ON l.competition_id=e.competition_id AND l.entrant_id=e.entrant_id WHERE e.competition_id=? AND COALESCE(l.eliminated,0)=0 ORDER BY losses,COALESCE(e.seed,999999),e.entrant_id''',(co['id'],)).fetchall()
 if len(active)==1:return _finish(c,co,active[0]['entrant_id'])
 r=c.execute('SELECT COALESCE(MAX(round_no),0)+1 n FROM fixtures WHERE competition_id=?',(co['id'],)).fetchone()['n'];zero=[x['entrant_id'] for x in active if x['losses']==0];one=[x['entrant_id'] for x in active if x['losses']==1];pairs=[]
 for bucket in (zero,one):
  while len(bucket)>=2:pairs.append((bucket.pop(0),bucket.pop(0)))
 if zero and one:pairs.append((zero[0],one[0]))
 for n,(a,b) in enumerate(pairs,1):
  bracket='grand_final' if len(active)==2 and {x['losses'] for x in active}=={0,1} else ('winners' if a in zero and b in zero else 'losers')
  _fixture(c,co['id'],stage['id'],r,n,a,b,bracket=bracket)

def progress_fixture(fid):
 with connect() as c:
  f=c.execute('SELECT * FROM fixtures WHERE id=?',(fid,)).fetchone()
  if not f or f['status']!='complete':return
  co=c.execute('SELECT * FROM competitions WHERE id=?',(f['competition_id'],)).fetchone();st=c.execute('SELECT * FROM competition_stages WHERE id=?',(f['stage_id'],)).fetchone()
  if st['format']=='single_elimination':_knockout(c,co,st)
  elif co['format']=='groups_knockout':_groups(c,co,st) if st['stage_no']==1 else _knockout(c,co,st)
  elif co['format']=='stepladder':_stepladder(c,co,st,f)
  elif co['format']=='double_elimination':_double(c,co,st,f)
  elif co['format']=='qualifying':
   if st['stage_no']==1:
    if not c.execute("SELECT 1 FROM fixtures WHERE stage_id=? AND status!='complete' LIMIT 1",(st['id'],)).fetchone():
     ids=[x['entrant_id'] for x in standings(co['id'])[:st['qualify_count']]];sid=_stage(c,co['id'],2,'Qualifying Finals','single_elimination');_round(c,co,sid,ids,1)
   else:_knockout(c,co,st)
  elif st['format']=='round_robin' and co['format']=='qualifying':
   if not c.execute("SELECT 1 FROM fixtures WHERE stage_id=? AND status!='complete' LIMIT 1",(st['id'],)).fetchone():
    ids=[x['entrant_id'] for x in standings(co['id'])[:st['qualify_count']]];sid=_stage(c,co['id'],2,'Qualifying Finals','single_elimination');_round(c,co,sid,ids,1)
  elif co['format']=='round_robin' and not c.execute("SELECT 1 FROM fixtures WHERE competition_id=? AND status!='complete' LIMIT 1",(co['id'],)).fetchone():
   ids=[x['entrant_id'] for x in standings(co['id'])]
   if co['playoff_size']>=2:sid=_stage(c,co['id'],2,'Playoffs','single_elimination');_round(c,co,sid,ids[:co['playoff_size']],1)
   elif ids:_finish(c,co,ids[0])

def record_series_game(fid,home_score,away_score,game_id=None):
 with connect() as c:
  f=c.execute('SELECT * FROM fixtures WHERE id=?',(fid,)).fetchone()
  if not f or f['status']=='complete':return False,'Fixture is complete.'
  n=c.execute('SELECT COUNT(*) n FROM fixture_games WHERE fixture_id=?',(fid,)).fetchone()['n']+1;w=f['home_id'] if home_score>away_score else f['away_id'] if away_score>home_score else None
  c.execute('INSERT INTO fixture_games(fixture_id,game_no,game_id,home_score,away_score,winner_id,status) VALUES(?,?,?,?,?,?,"complete")',(fid,n,game_id,home_score,away_score,w))
  wins={x['winner_id']:x['n'] for x in c.execute('SELECT winner_id,COUNT(*) n FROM fixture_games WHERE fixture_id=? AND winner_id IS NOT NULL GROUP BY winner_id',(fid,)).fetchall()};need=f['series_best_of']//2+1;champ=next((e for e,nw in wins.items() if nw>=need),None)
  if champ:
   totals=c.execute('SELECT SUM(home_score) h,SUM(away_score) a FROM fixture_games WHERE fixture_id=?',(fid,)).fetchone();c.execute('UPDATE fixtures SET home_score=?,away_score=?,winner_id=?,status="complete",played_at=CURRENT_TIMESTAMP WHERE id=?',(totals['h'],totals['a'],champ,fid))
 if champ:progress_fixture(fid)
 return True,None

def execute_movements(cid):
 with connect() as c:
  co=c.execute('SELECT * FROM competitions WHERE id=?',(cid,)).fetchone()
  if not co or co['state']!='completed':return []
  rs=standings(cid);out=[]
  for x in rs[:co['promotion_slots']]:c.execute('INSERT OR IGNORE INTO competition_movements(season_id,competition_id,entrant_id,movement,target_template_id) VALUES(?,?,?,"promoted",?)',(co['season_id'],cid,x['entrant_id'],co['template_id']));out.append((x['entrant_id'],'promoted'))
  for x in (rs[-co['relegation_slots']:] if co['relegation_slots'] else []):c.execute('INSERT OR IGNORE INTO competition_movements(season_id,competition_id,entrant_id,movement,target_template_id) VALUES(?,?,?,"relegated",?)',(co['season_id'],cid,x['entrant_id'],co['template_id']));out.append((x['entrant_id'],'relegated'))
  return out


def competition_view(cid):
 with connect() as c:
  co=c.execute('SELECT * FROM competitions WHERE id=?',(cid,)).fetchone()
  if not co:return None
  table='teams' if co['entrant_type']=='team' else 'bowlers'
  stages=c.execute('SELECT * FROM competition_stages WHERE competition_id=? ORDER BY stage_no',(cid,)).fetchall()
  fixtures=c.execute(f'''SELECT f.*,h.name home_name,a.name away_name,w.name winner_name FROM fixtures f
   LEFT JOIN {table} h ON h.id=f.home_id LEFT JOIN {table} a ON a.id=f.away_id LEFT JOIN {table} w ON w.id=f.winner_id
   WHERE f.competition_id=? ORDER BY f.stage_id,f.round_no,f.fixture_no''',(cid,)).fetchall()
  return co,stages,fixtures

def next_fixture(cid):
 with connect() as c:return c.execute("SELECT * FROM fixtures WHERE competition_id=? AND status='scheduled' AND home_id IS NOT NULL AND away_id IS NOT NULL ORDER BY stage_id,round_no,fixture_no LIMIT 1",(cid,)).fetchone()

def entrant_status(cid,entrant_id):
 with connect() as c:
  co=c.execute('SELECT * FROM competitions WHERE id=?',(cid,)).fetchone()
  if not co:return None
  entry=c.execute('SELECT * FROM competition_entries WHERE competition_id=? AND entrant_id=?',(cid,entrant_id)).fetchone()
  if not entry:return None
  rs=standings(cid);place=next((n for n,x in enumerate(rs,1) if x['entrant_id']==entrant_id),None);row=next((x for x in rs if x['entrant_id']==entrant_id),None)
  loss=c.execute('SELECT losses,eliminated FROM competition_losses WHERE competition_id=? AND entrant_id=?',(cid,entrant_id)).fetchone()
  nxt=c.execute("SELECT * FROM fixtures WHERE competition_id=? AND status='scheduled' AND (home_id=? OR away_id=?) ORDER BY stage_id,round_no,fixture_no LIMIT 1",(cid,entrant_id,entrant_id)).fetchone()
  status='Eliminated' if loss and loss['eliminated'] else 'Active'
  if co['state']=='completed':status='Completed'
  return {'competition':co,'entry':entry,'place':place,'standing':row,'losses':loss['losses'] if loss else 0,'status':status,'next':nxt}

def bowler_competitions(owner_id):
 with connect() as c:
  bowlers=c.execute('SELECT id,name FROM bowlers WHERE owner_id=?',(owner_id,)).fetchall();out=[]
  for b in bowlers:
   direct=c.execute("SELECT co.id FROM competitions co JOIN competition_entries e ON e.competition_id=co.id WHERE co.entrant_type='individual' AND e.entrant_id=? AND co.state IN ('registration','locked','active')",(b['id'],)).fetchall()
   team=c.execute("SELECT DISTINCT co.id FROM competitions co JOIN competition_rosters r ON r.competition_id=co.id WHERE co.entrant_type='team' AND r.bowler_id=? AND co.state IN ('locked','active')",(b['id'],)).fetchall()
   for x in direct+team:
    co=c.execute('SELECT entrant_type FROM competitions WHERE id=?',(x['id'],)).fetchone()
    eid=b['id']
    if co['entrant_type']=='team':eid=c.execute('SELECT team_id FROM competition_rosters WHERE competition_id=? AND bowler_id=?',(x['id'],b['id'])).fetchone()['team_id']
    st=entrant_status(x['id'],eid)
    if st:out.append((b,st))
  return out
