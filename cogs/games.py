import asyncio,discord
from discord import app_commands
from discord.ext import commands
from services.roster import team_roster
from models.bowler import Bowler
from services.game_engine import GameSession
from services.state import SESSIONS
from services.media import pick
from services.lane_visual import lane_card,lane_sequence
from services.match_broadcast import broadcast_card
from services.audio import play_sound
from services.presentation import classify,AUDIO_MAP,GIF_MAP,layout_policy
from services.commentary import line,streak_call,rivalry_call,contact_call,lane_call
from services.analytics import player_summary
from storage.database import record_completed_session,connect
from services.v25 import save_snapshot,clear_session,unlock_achievements,award_progression,backup_database,audit
from ui.embeds import scoreboard_embed
from services.v271 import bowler_loadout,tournament_presentation
from services.career import delivery_growth,add_tendency,add_timeline_event
from services.broadcast_director import match_context,persist_story,story_call,match_story_summary

def rb(r,team=None):
 b=Bowler(**{k:r[k] for k in ['id','name','owner_id','handedness','rank','accuracy','style','flair','consistency','spin','nerves']});b.team_name=team;return b
LANE_MESSAGES={}
async def update_lane(channel,session,event,stage='leave'):
 card=broadcast_card(session,event,stage)
 previous=LANE_MESSAGES.get(channel.id)
 if previous:
  try:
   await previous.edit(embed=None,attachments=[discord.File(card,filename='gutter_broadcast.png')])
   return previous
  except (discord.NotFound,discord.Forbidden):LANE_MESSAGES.pop(channel.id,None)
 message=await channel.send(file=discord.File(card,filename='gutter_broadcast.png'))
 LANE_MESSAGES[channel.id]=message
 return message

async def send_media(channel,kind):
 url=pick(kind)
 if url:await channel.send(url)
class Games(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='game_start',description='Start a team or team-v-team bowling game')
 @app_commands.choices(lane=[app_commands.Choice(name=x.title(),value=x) for x in ['house','fresh','dry','oily','transition']])
 async def start(self,i:discord.Interaction,team:str,opponent:str|None=None,lane:app_commands.Choice[str]|None=None,seed:int|None=None):
  ra=team_roster(team);rr=team_roster(opponent) if opponent else []
  if not ra:return await i.response.send_message('No roster found for the first team.',ephemeral=True)
  if opponent and not rr:return await i.response.send_message('No roster found for the opponent.',ephemeral=True)
  bowlers=[]
  if opponent:
   for n in range(max(len(ra),len(rr))):
    if n<len(ra):bowlers.append(rb(ra[n],team))
    if n<len(rr):bowlers.append(rb(rr[n],opponent))
  else:bowlers=[rb(x,team) for x in ra]
  s=GameSession(bowlers,seed,lane.value if lane else 'house');SESSIONS[i.channel_id]=s
  for p in s.players:p.ball_key=bowler_loadout(p.bowler.id).get('primary_ball','hybrid')
  await i.response.send_message(f"🎤 **WELCOME TO THE GUTTER SAINTS LANES!**\n**{team}**"+(f' vs **{opponent}**' if opponent else ''))
  for b in bowlers:await i.channel.send(line('entrance',name=b.name));await send_media(i.channel,'entrance')
  await i.channel.send(embed=scoreboard_embed(s))
 @app_commands.command(name='game_shot',description='Choose the next tactical shot intent')
 @app_commands.choices(intent=[app_commands.Choice(name=x.title(),value=x) for x in ['normal','safe','aggressive','recovery','spare','auto']])
 async def shot(self,i:discord.Interaction,intent:app_commands.Choice[str]):
  s=SESSIONS.get(i.channel_id)
  if not s or s.complete:return await i.response.send_message('No active playable game.',ephemeral=True)
  p=s.current()
  if p.standing!=set(__import__('services.pin_engine',fromlist=['ALL']).ALL) and intent.value!='spare':return await i.response.send_message('A leave is standing — Spare intent is automatic.',ephemeral=True)
  p.next_intent=intent.value
  await i.response.send_message(f"🎯 **{p.bowler.name}** next shot: **{intent.name}**.",ephemeral=True)
 @app_commands.command(name='game_bowl',description='Bowl the next delivery')
 async def bowl(self,i:discord.Interaction):
  s=SESSIONS.get(i.channel_id)
  if not s:return await i.response.send_message('No active game in this channel.',ephemeral=True)
  if s.complete:return await i.response.send_message('Game already complete.',ephemeral=True)
  await i.response.defer(ephemeral=True)
  save_snapshot(i.channel_id,s,'pre_ball')
  ev=s.bowl()
  ev['attribute_changes']=[] if getattr(s,'friendly_challenge',False) else delivery_growth(ev,s.rng)
  s.last_attribute_changes=ev['attribute_changes'];s.last_attribute_bowler_id=ev['bowler_id']
  save_snapshot(i.channel_id,s,'post_ball')
  await update_lane(i.channel,s,ev)
  await self.reaction(i.channel,s,ev)
  if s.complete:await self.finish(i.channel,s,i.channel_id)
 @app_commands.command(name='game_auto',description='Run the active game live with commentary and reactions')
 async def auto(self,i:discord.Interaction,delay:app_commands.Range[float,0.0,5.0]=0.7):
  s=SESSIONS.get(i.channel_id)
  if not s:return await i.response.send_message('No active game.',ephemeral=True)
  await i.response.defer(ephemeral=True)
  while not s.complete:
   save_snapshot(i.channel_id,s,'pre_ball')
   ev=s.bowl()
   ev['attribute_changes']=[] if getattr(s,'friendly_challenge',False) else delivery_growth(ev,s.rng)
   s.last_attribute_changes=ev['attribute_changes'];s.last_attribute_bowler_id=ev['bowler_id']
   save_snapshot(i.channel_id,s,'post_ball')
   if s.layout in ('broadcast','finals','chaos'):
    for stage in ('approach','path','breakpoint','impact','leave'):
     await update_lane(i.channel,s,ev,stage)
     await asyncio.sleep(max(.12,min(.45,delay*.35)))
   else:await update_lane(i.channel,s,ev)
   await self.reaction(i.channel,s,ev)
   await asyncio.sleep(delay)
  await self.finish(i.channel,s,i.channel_id)
 @app_commands.command(name='game_scoreboard')
 async def board(self,i:discord.Interaction):
  s=SESSIONS.get(i.channel_id);await i.response.send_message(embed=scoreboard_embed(s) if s else None,content=None if s else 'No active game.',ephemeral=not bool(s))
 async def reaction(self,ch,s,ev):
  event_kind=classify(ev);policy=layout_policy(s.layout,event_kind);kind=GIF_MAP.get(event_kind,event_kind)
  if policy['media'] and kind!='delivery':
   await send_media(ch,kind)
   if event_kind in ('strike','spare','turkey','six_pack','front_nine','perfect_watch','perfect_300','split_conversion','seven_ten_conversion'):await send_media(ch,'crowd_hype')
   elif event_kind in ('split','seven_ten','gutter'):await send_media(ch,'crowd_groan')
  if policy['audio']:await play_sound(ch,AUDIO_MAP.get(event_kind,'pins'))
  lane_note=lane_call(ev)
  if lane_note and getattr(s,'layout','broadcast')=='chaos':await ch.send(lane_note)
  stories=match_context(s,ev);fresh=[]
  for kind,icon,headline,detail in stories:
   key=f'{kind}:{headline}'
   if key not in s.story_seen:s.story_seen.add(key);fresh.append((kind,icon,headline,detail));persist_story(s,kind,headline,detail)
  if fresh and getattr(s,'layout','broadcast') in ('finals','chaos'):await ch.send('🎙️ **BROADCAST DIRECTOR**\n'+story_call(fresh))
  contact=contact_call(ev)
  if contact and getattr(s,'layout','broadcast')=='chaos':await ch.send(contact)
  call=streak_call(ev)
  if call and getattr(s,'layout','broadcast') in ('finals','chaos'):await ch.send(call)
  for stat,delta,new,reason in ev.get('attribute_changes',[]):await ch.send(f"📈 **{ev['bowler']}** {stat.title()} {'+' if delta>0 else ''}{delta} → **{new}** ({reason})")
  rival=rivalry_call(ev)
  if rival:await ch.send(rival)
 async def finish(self,ch,s,key):
  LANE_MESSAGES.pop(key,None)
  if getattr(s,'friendly_challenge',False):
   from services.analytics import player_summary
   with connect() as db:
    db.execute('CREATE TABLE IF NOT EXISTS friendly_xp_daily(bowler_id INTEGER NOT NULL,day TEXT NOT NULL,PRIMARY KEY(bowler_id,day))')
    for p in s.players:
     granted=db.execute("INSERT OR IGNORE INTO friendly_xp_daily(bowler_id,day) VALUES(?,date('now'))",(p.bowler.id,)).rowcount
     if granted:
      db.execute('INSERT OR IGNORE INTO bowler_progression(bowler_id) VALUES(?)',(p.bowler.id,))
      db.execute('UPDATE bowler_progression SET xp=xp+1 WHERE bowler_id=?',(p.bowler.id,))
   await ch.send('🤝 **FRIENDLY EXHIBITION COMPLETE** — No league points, rank changes, career attribute growth or achievements. Each bowler can earn at most **1 non-ranking XP per UTC day** from friendly challenges.')
   await ch.send(embed=scoreboard_embed(s))
   s.persisted=True
   SESSIONS.pop(key,None)
   return
  gid=record_completed_session(s,key);totals=s.team_totals(); winner=max(totals,key=totals.get) if len(totals)>1 and len(set(totals.values()))>1 else None
  await ch.send('🏁 **GAME COMPLETE!**',embed=scoreboard_embed(s));summaries=sorted(((p,player_summary(p)) for p in s.players),key=lambda x:x[1]['score'],reverse=True);high=summaries[0];awards=[f"👑 **High Game:** {high[0].bowler.name} — {high[1]['score']}"]
  clean=[p.bowler.name for p,x in summaries if x['clean']]
  if clean:awards.append('✨ **Clean Game:** '+', '.join(clean))
  best_streak=max(summaries,key=lambda x:x[1]['longest_streak'])
  if best_streak[1]['longest_streak']>=3:awards.append(f"🔥 **Strike Run:** {best_streak[0].bowler.name} — {best_streak[1]['longest_streak']} straight")
  split=max(summaries,key=lambda x:x[1]['split_conversions'])
  if split[1]['split_conversions']:awards.append(f"🪓 **Split Slayer:** {split[0].bowler.name} — {split[1]['split_conversions']} converted")
  if winner:awards.insert(0,f'🏆 **Team Winner: {winner}** — {totals[winner]}')
  await ch.send('🎖️ **POST-GAME HONOURS**\n'+'\n'.join(awards))
  stories=match_story_summary(s)
  if stories:
   priority={'comeback':6,'lead_change':5,'clutch':4,'pb_watch':3,'perfect_watch':7,'rivalry':3,'lane_read':1}
   top=sorted(stories,key=lambda r:priority.get(r['kind'],0),reverse=True)[:4]
   await ch.send('📰 **MATCH STORY**\n'+'\n'.join(f"• **{r['headline']}** — {r['detail']}" for r in top))
  achievement_cards=[]
  with connect() as c:
   season=c.execute("SELECT id FROM seasons WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone(); season_id=season['id'] if season else None
   for p,sm in summaries:
    team_name=getattr(p.bowler,'team_name',None);tr=c.execute('SELECT id FROM teams WHERE name=? COLLATE NOCASE',(team_name,)).fetchone() if team_name else None;tid=tr['id'] if tr else None
    c.execute('INSERT INTO game_history(game_id,bowler_id,season_id,tournament_id,team_id,score,strikes,spares,splits,split_conversions,longest_streak,clean,form) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(gid,p.bowler.id,season_id,s.tournament_id,tid,sm['score'],sm['strikes'],sm['spares'],sm['splits'],sm['split_conversions'],sm['longest_streak'],sm['clean'],getattr(p,'form',0)))
    effective_season=getattr(s,'season_id',None) or season_id
    if effective_season:
     c.execute('INSERT OR IGNORE INTO season_bowler_stats(season_id,bowler_id) VALUES(?,?)',(effective_season,p.bowler.id))
     c.execute('UPDATE season_bowler_stats SET games=games+1,total_pins=total_pins+?,high_game=MAX(high_game,?),strikes=strikes+?,spares=spares+?,split_conversions=split_conversions+? WHERE season_id=? AND bowler_id=?',(sm['score'],sm['score'],sm['strikes'],sm['spares'],sm['split_conversions'],effective_season,p.bowler.id))
    award_progression(p.bowler.id,sm['score'],bool(s.tournament_id),winner==team_name)
    if sm['clean']:add_tendency(p.bowler.id,'consistency',2.2,'Repeated clean-game execution','game')
    if sm['longest_streak']>=6:add_tendency(p.bowler.id,'flair',1.8,'Produced a six-pack strike run','game')
    if sm['score']<120 and sm.get('opens',0)>=5:add_tendency(p.bowler.id,'consistency',-2.0,'Repeated game collapse with open frames','game')
    if sm['score']>=250:add_tendency(p.bowler.id,'nerves',1.5,'Delivered a 250+ pressure game','game')
    seven_ten='7–10 Split' in getattr(p,'special_conversions',set())
    for title,detail in unlock_achievements(p.bowler.id,sm,{'seven_ten':seven_ten}):achievement_cards.append((p.bowler.name,title,detail))
  for name,title,detail in achievement_cards:
   e=discord.Embed(title=f'🏅 ACHIEVEMENT UNLOCKED — {title}',description=f'**{name}**\n{detail}',colour=discord.Colour.gold());await ch.send(embed=e);await send_media(ch,'award')
  if s.tournament_id and s.match_id and len(totals)==2 and winner:
   backup_database('auto_tournament_result')
   with connect() as c:
    m=c.execute('SELECT * FROM tournament_matches WHERE id=?',(s.match_id,)).fetchone();ta=c.execute('SELECT name FROM teams WHERE id=?',(m['team_a_id'],)).fetchone()['name'];tb=c.execute('SELECT name FROM teams WHERE id=?',(m['team_b_id'],)).fetchone()['name'];sa=totals.get(ta,0);sb=totals.get(tb,0);wid=m['team_a_id'] if sa>sb else m['team_b_id']
    c.execute('UPDATE tournament_matches SET score_a=?,score_b=?,winner_id=?,status="complete" WHERE id=?',(sa,sb,wid,m['id']));c.execute('INSERT INTO head_to_head(team_a_id,team_b_id,winner_id,score_a,score_b,tournament_id,match_id) VALUES(?,?,?,?,?,?,?)',(m['team_a_id'],m['team_b_id'],wid,sa,sb,s.tournament_id,m['id']))
    for team_id,won,score in [(m['team_a_id'],wid==m['team_a_id'],sa),(m['team_b_id'],wid==m['team_b_id'],sb)]:c.execute('INSERT OR IGNORE INTO team_history(team_id) VALUES(?)',(team_id,));c.execute('UPDATE team_history SET wins=wins+?,losses=losses+?,high_game=MAX(high_game,?) WHERE team_id=?',(int(won),int(not won),score,team_id))
    c.execute('INSERT INTO tournament_stories(tournament_id,match_id,kind,headline,detail) VALUES(?,?,?,?,?)',(s.tournament_id,s.match_id,'result','Match decided',f'{winner} defeated its opponent {max(totals.values())}-{min(totals.values())}.'))
   from services.competition import _advance_byes
   with connect() as c:_advance_byes(c,s.tournament_id)
   await ch.send(f'🏆 **TOURNAMENT UPDATE:** {winner} advances automatically.')
   # Publish a fresh issue after tournament matches; the Gazette becomes the persistent session recap.
   from services.gazette import build_gazette,format_gazette
   g=build_gazette(s.tournament_id)
   if g:await ch.send(format_gazette(g))
  clear_session(key)
async def setup(bot):await bot.add_cog(Games(bot))
