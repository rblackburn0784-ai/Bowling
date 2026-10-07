from storage.database import connect
from services.scoring import score_game

def _pace(player):
 frames=player.frames
 if not frames:return 0
 try:return score_game(frames+[[] for _ in range(max(0,10-len(frames)))])
 except Exception:return sum(sum(f) for f in frames)*10/max(1,len(frames))

def _career_pb(bid):
 with connect() as c:
  r=c.execute('SELECT high_game FROM bowler_stats WHERE bowler_id=?',(bid,)).fetchone()
 return r['high_game'] if r else 0

def _team_live(session):
 out={}
 for p in session.players:
  team=getattr(p.bowler,'team_name',None)
  if team:out[team]=out.get(team,0)+_pace(p)
 return out

def match_context(session,event):
 stories=[];live=_team_live(session);previous=getattr(session,'story_leader',None)
 if len(live)>=2:
  ordered=sorted(live.items(),key=lambda x:x[1],reverse=True);leader,lead=ordered[0];gap=lead-ordered[1][1]
  if previous and previous!=leader and gap>=5:stories.append(('lead_change','🔄',f'{leader} takes the lead',f'{leader} has moved ahead by roughly {gap} pins.'))
  session.story_leader=leader
  if event.get('frame',0)>=8 and gap<=15:stories.append(('clutch','🚨','Match on a knife-edge',f'Only about {gap} pins separate the teams late.'))
  low=getattr(session,'story_low',{});team=getattr(next((p.bowler for p in session.players if p.bowler.id==event.get('bowler_id')),None),'team_name',None)
  if team:
   low[team]=min(low.get(team,live[team]),live[team]);session.story_low=low
   if leader==team and live[team]-low[team]>=25:stories.append(('comeback','📈',f'{team} completes the swing',f'A comeback of roughly {live[team]-low[team]} pins has put them in front.'))
 p=next((x for x in session.players if x.bowler.id==event.get('bowler_id')),None)
 if p:
  pb=_career_pb(p.bowler.id);pace=_pace(p)
  if event.get('frame',0)>=7 and pb and pace>pb and not p.complete:stories.append(('pb_watch','⭐',f'{p.bowler.name} is on PB pace',f'Projected around {pace:.0f}; career best is {pb}.'))
  if event.get('strike_streak',0)>=6:stories.append(('perfect_watch','🤫',f'{p.bowler.name}: perfection watch',f"{event.get('strike_streak')} consecutive strikes and the pressure is building."))
 if event.get('rivalry'):
  a,b=event['rivalry'];stories.append(('rivalry','⚔️',f'{a} answers {b}',f'The head-to-head battle has another response.'))
 if event.get('adaptation'):
  a=event['adaptation'];stories.append(('lane_read','🧠',f"{event['bowler']} makes a lane move",f"{a['from_ball'].title()} → {a['to_ball'].title()} • {a['reason']}."))
 return stories

def persist_story(session,kind,headline,detail):
 if not session.tournament_id:return
 with connect() as c:c.execute('INSERT INTO tournament_stories(tournament_id,match_id,kind,headline,detail) VALUES(?,?,?,?,?)',(session.tournament_id,session.match_id,kind,headline,detail))

def story_call(stories):
 return '\n'.join(f"{icon} **{headline}** — {detail}" for _,icon,headline,detail in stories)

def match_story_summary(session):
 with connect() as c:
  if session.tournament_id and session.match_id:
   return c.execute('SELECT kind,headline,detail FROM tournament_stories WHERE tournament_id=? AND match_id=? ORDER BY id',(session.tournament_id,session.match_id)).fetchall()
 return []
