from storage.database import connect
from services.career import add_timeline_event

def _honour(bowler_id,tournament_id,code,title,detail,placing=None,icon='🏆'):
 with connect() as c:
  cur=c.execute('INSERT OR IGNORE INTO career_honours(bowler_id,tournament_id,code,title,detail,placing) VALUES(?,?,?,?,?,?)',(bowler_id,tournament_id,code,title,detail,placing))
  if not cur.rowcount:return False
  c.execute('UPDATE bowler_stats SET awards=awards+1 WHERE bowler_id=?',(bowler_id,))
 add_timeline_event(bowler_id,'honour',title,detail,icon,'tournament')
 return True

def finalize_tournament_honours(tournament_id):
 with connect() as c:
  t=c.execute('SELECT * FROM tournaments WHERE id=?',(tournament_id,)).fetchone()
  if not t or t['status']!='complete':return None
  final=c.execute('SELECT * FROM tournament_matches WHERE tournament_id=? ORDER BY round_no DESC,match_no LIMIT 1',(tournament_id,)).fetchone()
  if not final or not final['winner_id']:return None
  champion=final['winner_id'];runner=final['team_b_id'] if champion==final['team_a_id'] else final['team_a_id']
  champ_name=c.execute('SELECT name FROM teams WHERE id=?',(champion,)).fetchone()['name']
  runner_name=c.execute('SELECT name FROM teams WHERE id=?',(runner,)).fetchone()['name'] if runner else None
  champs=c.execute('SELECT b.id,b.name FROM team_members tm JOIN bowlers b ON b.id=tm.bowler_id WHERE tm.team_id=?',(champion,)).fetchall()
  runners=c.execute('SELECT b.id,b.name FROM team_members tm JOIN bowlers b ON b.id=tm.bowler_id WHERE tm.team_id=?',(runner,)).fetchall() if runner else []
  leaders=c.execute('SELECT s.*,b.name FROM tournament_bowler_stats s JOIN bowlers b ON b.id=s.bowler_id WHERE s.tournament_id=?',(tournament_id,)).fetchall()
  c.execute('INSERT OR IGNORE INTO team_history(team_id) VALUES(?)',(champion,));c.execute('UPDATE team_history SET championships=championships+1,finals=finals+1 WHERE team_id=? AND NOT EXISTS(SELECT 1 FROM career_honours WHERE tournament_id=? AND code="champion")',(champion,tournament_id))
  if runner:c.execute('INSERT OR IGNORE INTO team_history(team_id) VALUES(?)',(runner,))
 name=t['name'];new=[]
 for b in champs:
  if _honour(b['id'],tournament_id,'champion',f'🏆 {name} Champion',f'Won {name} with {champ_name}.',1):new.append((b['name'],'Champion'))
 for b in runners:
  if _honour(b['id'],tournament_id,'runner_up',f'🥈 {name} Runner-up',f'Reached the final with {runner_name}.',2,'🥈'):new.append((b['name'],'Runner-up'))
 if leaders:
  top_avg=max(leaders,key=lambda x:x['total_pins']/max(1,x['games']));avg=top_avg['total_pins']/max(1,top_avg['games'])
  high=max(leaders,key=lambda x:x['high_game'])
  strike=max(leaders,key=lambda x:x['strikes'])
  split=max(leaders,key=lambda x:x['split_conversions'])
  specs=[(top_avg,'high_average','🎯',f'{name} High Average',f'{avg:.1f} tournament average.'),(high,'high_game','🔥',f'{name} High Game',f"High game of {high['high_game']}."),(strike,'strike_leader','⚡',f'{name} Strike Leader',f"{strike['strikes']} strikes."),(split,'split_slayer','🪓',f'{name} Split Slayer',f"{split['split_conversions']} split conversions.")]
  for row,code,icon,title,detail in specs:
   if _honour(row['bowler_id'],tournament_id,code,title,detail,None,icon):new.append((row['name'],title))
 return {'tournament':name,'champion':champ_name,'runner_up':runner_name,'new':new}

def honours_for_bowler(bowler_id):
 with connect() as c:return c.execute('SELECT * FROM career_honours WHERE bowler_id=? ORDER BY id DESC',(bowler_id,)).fetchall()
