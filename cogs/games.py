import asyncio,discord,logging
from discord import app_commands
from discord.ext import commands
from services.roster import team_roster
from models.bowler import Bowler
from services.game_engine import GameSession
from services.state import SESSIONS
from services.media import pick
from services.lane_visual import lane_card,lane_sequence
from services.shot_animation import animated_shot,DISCORD_PLAYBACK_HEADROOM_SECONDS
from services.bowler_sprites import sprite_key,has_sequence,APPROACH_FRAME_SECONDS
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
 b=Bowler(**{k:r[k] for k in ['id','name','owner_id','handedness','rank','accuracy','style','flair','consistency','spin','nerves']})
 b.team_name=team
 b.sprite_key=r['sprite_key'] if 'sprite_key' in r.keys() else None
 if team:
  b.affiliation=team
 else:
  # Solo exhibitions and friendly challenges can show an existing club
  # affiliation without misclassifying the match as team-v-team.
  with connect() as db:
   memberships=db.execute(
    'SELECT t.name FROM teams t JOIN team_members tm ON tm.team_id=t.id '
    'WHERE tm.bowler_id=? ORDER BY t.name COLLATE NOCASE LIMIT 1',(b.id,)
   ).fetchone()
  b.affiliation=memberships['name'] if memberships else None
 return b
LANE_MESSAGES={}
MATCH_BUSY=set()
# Fixed broadcast pacing: frame changes are deliberately slower than
# the typical Discord attachment-edit rate, with a pause between deliveries.
AUTO_BETWEEN_BALLS=0.7
AUTO_FRAME_DELAY=1.0

def can_operate_match(member,session):
 permissions=getattr(member,'guild_permissions',None)
 if permissions and (permissions.administrator or permissions.manage_guild):
  return True
 return getattr(member,'id',None) in {
  getattr(player.bowler,'owner_id',None) for player in session.players
  if getattr(player.bowler,'owner_id',None) not in (None,0)
 }

class LiveMatchControls(discord.ui.View):
 """Buttons belong to the current channel's active match, not a stale view."""
 def __init__(self,channel_id,session):
  super().__init__(timeout=3600)
  self.channel_id=channel_id
  self.session=session

 async def interaction_check(self,i):
  if i.channel_id!=self.channel_id or SESSIONS.get(self.channel_id) is not self.session or self.session.complete:
   await i.response.send_message('This match has finished or its controls are out of date.',ephemeral=True)
   return False
  if not can_operate_match(i.user,self.session):
   await i.response.send_message('Only a competing player or server administrator can bowl this match.',ephemeral=True)
   return False
  return True

 @discord.ui.button(label='🎳 Bowl Next Ball',style=discord.ButtonStyle.primary,custom_id='gutter:manual-bowl')
 async def bowl_next(self,i,b):
  if i.channel_id in MATCH_BUSY:
   return await i.response.send_message('A ball or automatic game is already running.',ephemeral=True)
  await i.response.defer(ephemeral=True)
  cog=i.client.get_cog('Games')
  try:
   if cog and not await cog.play_one(i.channel,self.session):
    await i.followup.send('Match already bowling or the controls are out of date.',ephemeral=True)
  except Exception:
   logging.exception('Manual bowling failed in channel %s',i.channel_id)
   await i.followup.send('⚠️ Match processing failed. The latest ball may already be saved. Ask an administrator to review the game before retrying.',ephemeral=True)

 @discord.ui.button(label='▶ Auto Play',style=discord.ButtonStyle.success,custom_id='gutter:auto-bowl')
 async def auto_play(self,i,b):
  if i.channel_id in MATCH_BUSY:
   return await i.response.send_message('A ball or automatic game is already running.',ephemeral=True)
  await i.response.defer(ephemeral=True)
  cog=i.client.get_cog('Games')
  try:
   if cog and not await cog.play_all(i.channel,self.session):
    await i.followup.send('Match already bowling or the controls are out of date.',ephemeral=True)
  except Exception:
   logging.exception('Auto Play failed in channel %s',i.channel_id)
   await i.followup.send('⚠️ Auto Play stopped during game processing. The latest result may already be recorded. Do not restart or replay this match until an administrator checks its saved results.',ephemeral=True)

async def post_match_controls(channel,session):
 """Post the one live scoreboard that future ball renders will edit in place."""
 LANE_MESSAGES.pop(channel.id,None)
 msg=await channel.send(embed=scoreboard_embed(session),
                        view=LiveMatchControls(channel.id,session))
 LANE_MESSAGES[channel.id]=msg
 return msg
async def update_lane(channel,session,event,stage='leave',director=None,prior_cards=None,prior_scores=None,sprite_frame=None,ball_frame=0,ball_progress=None):
 card=lane_card(session,event,stage,sprite_frame=sprite_frame,ball_frame=ball_frame,ball_progress=ball_progress)
 # A normal Discord embed stays readable below the image.
 # Never reveal the new ball's result before the final animation stage.
 embed=scoreboard_embed(session,event,director=director,stage=stage,prior_cards=prior_cards,prior_scores=prior_scores)
 previous=LANE_MESSAGES.get(channel.id)
 if previous:
  try:
   await previous.edit(embed=embed,attachments=[discord.File(card,filename='gutter_lane.png')])
   return previous
  except (discord.NotFound,discord.Forbidden):
   LANE_MESSAGES.pop(channel.id,None)
 message=await channel.send(embed=embed,file=discord.File(card,filename='gutter_lane.png'),view=LiveMatchControls(channel.id,session))
 LANE_MESSAGES[channel.id]=message
 return message

async def animate_approach(channel,session,event,prior_cards,prior_scores):
 bowler=next((p.bowler for p in session.players if p.bowler.id==event.get('bowler_id')),None)
 key=sprite_key(bowler) if bowler else None
 if not has_sequence(key):
  await update_lane(channel,session,event,'approach',prior_cards=prior_cards,prior_scores=prior_scores)
  return
 for frame in range(1,6):
  await update_lane(channel,session,event,'approach',prior_cards=prior_cards,prior_scores=prior_scores,sprite_frame=frame)
  await asyncio.sleep(APPROACH_FRAME_SECONDS)

# Continuous percentages along the existing calculated ball path.
# The approach renderer does not touch the path. Ball movement begins
# only after the bowler has finished the fifth release pose.
BALL_STAGE_PROGRESS={
 'path':(.12,.32,.50,.62),
 'breakpoint':(.70,.78,.85),
 'impact':(.92,.98,1.0),
}

async def animate_delivery(channel,session,event,prior_cards,prior_scores,delay):
 # Build the moving picture off-thread, then upload just ONE animated GIF.
 # This removes Discord's per-frame upload latency / slideshow effect.
 try:
  gif,duration=await asyncio.to_thread(animated_shot,session,event)
 except Exception:
  logging.exception('Animated lane render failed; using still-image fallback')
  gif,duration=None,0
 if gif is not None:
  embed=scoreboard_embed(session,event,stage='approach',
                         prior_cards=prior_cards,prior_scores=prior_scores)
  previous=LANE_MESSAGES.get(channel.id)
  # A unique filename per ball avoids client/CDN recycling of a prior
  # single-play GIF (particularly the second ball of the same frame).
  sequence=getattr(session,'ball_count',0)
  picture=discord.File(gif,filename=f'gutter_motion_{session.seed}_{sequence}.gif')
  if previous:
   try:
    await previous.edit(embed=embed,attachments=[picture])
   except (discord.NotFound,discord.Forbidden):
    LANE_MESSAGES.pop(channel.id,None)
    previous=None
  if previous is None:
   msg=await channel.send(embed=embed,file=picture,
                          view=LiveMatchControls(channel.id,session))
   LANE_MESSAGES[channel.id]=msg
  # The Discord API acknowledges the attachment before each client's
  # renderer actually starts playing it. Allow time for slow attachment
  # loading instead of replacing the animation midway through pinfall.
  # GIF contains only presentation frames; score stays pre-delivery here.
  await asyncio.sleep(duration+DISCORD_PLAYBACK_HEADROOM_SECONDS)
  return

 # Graceful legacy fallback if art, GIF support or an asset is missing.
 await animate_approach(channel,session,event,prior_cards,prior_scores)
 frame_delay=max(.16,min(.32,delay*.30))
 for stage,positions in BALL_STAGE_PROGRESS.items():
  for index,progress in enumerate(positions):
   await update_lane(channel,session,event,stage,
      prior_cards=prior_cards,prior_scores=prior_scores,
      ball_frame=index+1,ball_progress=progress)
   await asyncio.sleep(frame_delay)

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
  await post_match_controls(i.channel,s)
 @app_commands.command(name='bowler_sprite',description='Set the character sprite for a registered bowler')
 @app_commands.default_permissions(manage_guild=True)
 @app_commands.choices(character=[app_commands.Choice(name='The Dude',value='the_dude'),app_commands.Choice(name='Jesus',value='jesus'),app_commands.Choice(name='No Sprite',value='none')])
 async def bowler_sprite(self,i:discord.Interaction,bowler:str,character:app_commands.Choice[str]):
  if not i.guild or not i.user.guild_permissions.manage_guild:
   return await i.response.send_message('Manage Server permission required.',ephemeral=True)
  key=character.value
  with connect() as db:
   cur=db.execute('UPDATE bowlers SET sprite_key=? WHERE name=? COLLATE NOCASE',(key,bowler))
  if not cur.rowcount:
   return await i.response.send_message('Bowler not found.',ephemeral=True)
  await i.response.send_message(f"🎳 **{bowler}** sprite: **{character.name}**. Applies to newly started or restored matches.",ephemeral=True)

 @app_commands.command(name='game_shot',description='Choose the next tactical shot intent')
 @app_commands.choices(intent=[app_commands.Choice(name=x.title(),value=x) for x in ['normal','safe','aggressive','recovery','spare','auto']])
 async def shot(self,i:discord.Interaction,intent:app_commands.Choice[str]):
  s=SESSIONS.get(i.channel_id)
  if not s or s.complete:return await i.response.send_message('No active playable game.',ephemeral=True)
  p=s.current()
  if p.standing!=set(__import__('services.pin_engine',fromlist=['ALL']).ALL) and intent.value!='spare':return await i.response.send_message('A leave is standing — Spare intent is automatic.',ephemeral=True)
  p.next_intent=intent.value
  await i.response.send_message(f"🎯 **{p.bowler.name}** next shot: **{intent.name}**.",ephemeral=True)
 async def _deliver(self,ch,s):
  key=ch.id
  save_snapshot(key,s,'pre_ball')
  prior_cards=s.card();prior_scores=s.scores()
  ev=s.bowl()
  ev['attribute_changes']=[] if getattr(s,'friendly_challenge',False) else delivery_growth(ev,s.rng)
  s.last_attribute_changes=ev['attribute_changes'];s.last_attribute_bowler_id=ev['bowler_id']
  save_snapshot(key,s,'post_ball')
  await animate_delivery(ch,s,ev,prior_cards,prior_scores,AUTO_FRAME_DELAY)
  director=await self.reaction(ch,s,ev)
  await update_lane(ch,s,ev,'leave',director=director)
  if s.complete:
   await self.finish(ch,s,key)

 async def play_one(self,ch,s):
  key=ch.id
  if key in MATCH_BUSY or s.complete or SESSIONS.get(key) is not s:
   return False
  MATCH_BUSY.add(key)
  try:
   await self._deliver(ch,s)
   return True
  finally:
   MATCH_BUSY.discard(key)

 async def play_all(self,ch,s):
  key=ch.id
  if key in MATCH_BUSY or s.complete or SESSIONS.get(key) is not s:
   return False
  MATCH_BUSY.add(key)
  try:
   while not s.complete and SESSIONS.get(key) is s:
    await self._deliver(ch,s)
    if not s.complete:await asyncio.sleep(AUTO_BETWEEN_BALLS)
   return True
  finally:
   MATCH_BUSY.discard(key)

 @app_commands.command(name='game_bowl',description='Bowl the next delivery manually')
 async def bowl(self,i:discord.Interaction):
  s=SESSIONS.get(i.channel_id)
  if not s or s.complete:return await i.response.send_message('No active playable game.',ephemeral=True)
  if not can_operate_match(i.user,s):
   return await i.response.send_message('Only a competing bowler or server administrator can control this match.',ephemeral=True)
  if i.channel_id in MATCH_BUSY:return await i.response.send_message('Match already bowling.',ephemeral=True)
  await i.response.defer(ephemeral=True)
  if not await self.play_one(i.channel,s):
   await i.followup.send('Match already bowling or no longer active.',ephemeral=True)

 @app_commands.command(name='game_auto',description='Run the active match automatically at the standard broadcast pace')
 async def auto(self,i:discord.Interaction):
  s=SESSIONS.get(i.channel_id)
  if not s or s.complete:return await i.response.send_message('No active playable game.',ephemeral=True)
  if not can_operate_match(i.user,s):
   return await i.response.send_message('Only a competing bowler or server administrator can control this match.',ephemeral=True)
  if i.channel_id in MATCH_BUSY:return await i.response.send_message('Match already bowling.',ephemeral=True)
  await i.response.defer(ephemeral=True)
  if not await self.play_all(i.channel,s):
   await i.followup.send('Match already bowling or no longer active.',ephemeral=True)

 @app_commands.command(name='game_scoreboard')
 async def board(self,i:discord.Interaction):
  s=SESSIONS.get(i.channel_id);await i.response.send_message(embed=scoreboard_embed(s) if s else None,content=None if s else 'No active game.',ephemeral=not bool(s))
 async def reaction(self,ch,s,ev):
  """One editorial call per delivery; never repeat the graphic's play-by-play."""
  event_kind=classify(ev)
  policy=layout_policy(s.layout,event_kind)
  kind=GIF_MAP.get(event_kind,event_kind)
  # The scoreboard embed owns ordinary shot-by-shot commentary.
  # Return one milestone to the same embed, never a competing channel post.
  stories=match_context(s,ev)
  fresh=[]
  for story_kind,icon,headline,detail in stories:
   key=f'{story_kind}:{headline}'
   if key not in s.story_seen:
    s.story_seen.add(key)
    fresh.append((story_kind,icon,headline,detail))
    persist_story(s,story_kind,headline,detail)
  milestone=streak_call(ev)
  # A milestone is more important than a lead-change or a generic comeback.
  # The other context is still recorded for end-of-match summaries.
  if milestone:
   announcement=milestone
  else:
   priority={'lead_change':5,'comeback':4,'clutch':3,'pb_watch':3,'tournament_pressure':2,'perfect_watch':2,'rivalry':1,'lane_read':0}
   candidates=[story for story in fresh if priority.get(story[0],0)>=2]
   if candidates:
    top=max(candidates,key=lambda story:priority.get(story[0],0))
    announcement=f'{top[1]} **{top[2]}** — {top[3]}'
   else:
    announcement=None
  if policy['audio']:
   await play_sound(ch,AUDIO_MAP.get(event_kind,'pins'))
  # Optional media is theatrical, but don't send duplicate crowd hype/groan
  # for the same delivery, and don't flood normal broadcasts with GIFs.
  if policy['media'] and kind!='delivery' and s.layout in ('finals','chaos'):
   await send_media(ch,kind)
  # Attribute changes are gameplay notifications, not duplicate shot calls.
  if not getattr(s,'friendly_challenge',False):
   for stat,delta,new,reason in ev.get('attribute_changes',[]):
    await ch.send(f"📈 **{ev['bowler']}** {stat.title()} {'+' if delta>0 else ''}{delta} → **{new}** ({reason})")
  return announcement
 async def finish(self,ch,s,key):
  LANE_MESSAGES.pop(key,None)
  if getattr(s,'friendly_challenge',False):
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
  # Calculate all bowler summaries *before* recording the result so a
  # formatting/analytics error cannot leave a half-finalised persisted game.
  summaries=sorted(((p,player_summary(p)) for p in s.players),
                   key=lambda pair:pair[1]['score'],reverse=True)
  if not summaries:
   raise ValueError('Cannot finalise a game without bowlers')
  gid=record_completed_session(s,key)
  if gid is None:
   raise RuntimeError('Completed game id could not be resolved; refusing duplicate post-game awards')
  totals=s.team_totals()
  winner=max(totals,key=totals.get) if len(totals)>1 and len(set(totals.values()))>1 else None
  high=summaries[0]
  awards=[f"👑 **High Game:** {high[0].bowler.name} — {high[1]['score']}"]
  await ch.send('🏁 **GAME COMPLETE!**',embed=scoreboard_embed(s))
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
  # Commit game history/season stats before running career helpers.
  # Those helpers open their own SQLite connections: invoking them within
  # an uncommitted write transaction causes "database is locked".
  achievement_cards=[]
  newly_recorded=[]
  with connect() as c:
   season=c.execute("SELECT id FROM seasons WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
   season_id=season['id'] if season else None
   for p,sm in summaries:
    # If recovering after a partially completed postgame, do not write the
    # same player's history or increment season totals twice.
    existing=c.execute('SELECT 1 FROM game_history WHERE game_id=? AND bowler_id=? LIMIT 1',
                       (gid,p.bowler.id)).fetchone()
    if existing:
     logging.warning('Skipping duplicate history for game=%s bowler=%s',gid,p.bowler.id)
     continue
    team_name=getattr(p.bowler,'team_name',None)
    tr=c.execute('SELECT id FROM teams WHERE name=? COLLATE NOCASE',(team_name,)).fetchone() if team_name else None
    tid=tr['id'] if tr else None
    c.execute('INSERT INTO game_history(game_id,bowler_id,season_id,tournament_id,team_id,score,strikes,spares,splits,split_conversions,longest_streak,clean,form) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
              (gid,p.bowler.id,season_id,s.tournament_id,tid,sm['score'],sm['strikes'],sm['spares'],sm['splits'],sm['split_conversions'],sm['longest_streak'],sm['clean'],getattr(p,'form',0)))
    effective_season=getattr(s,'season_id',None) or season_id
    if effective_season:
     c.execute('INSERT OR IGNORE INTO season_bowler_stats(season_id,bowler_id) VALUES(?,?)',(effective_season,p.bowler.id))
     c.execute('UPDATE season_bowler_stats SET games=games+1,total_pins=total_pins+?,high_game=MAX(high_game,?),strikes=strikes+?,spares=spares+?,split_conversions=split_conversions+? WHERE season_id=? AND bowler_id=?',
               (sm['score'],sm['score'],sm['strikes'],sm['spares'],sm['split_conversions'],effective_season,p.bowler.id))
    newly_recorded.append((p,sm))
  for p,sm in newly_recorded:
   team_name=getattr(p.bowler,'team_name',None)
   award_progression(p.bowler.id,sm['score'],bool(s.tournament_id),winner==team_name)
   if sm['clean']:add_tendency(p.bowler.id,'consistency',2.2,'Repeated clean-game execution','game')
   if sm['longest_streak']>=6:add_tendency(p.bowler.id,'flair',1.8,'Produced a six-pack strike run','game')
   if sm['score']<120 and sm.get('opens',0)>=5:add_tendency(p.bowler.id,'consistency',-2.0,'Repeated game collapse with open frames','game')
   if sm['score']>=250:add_tendency(p.bowler.id,'nerves',1.5,'Delivered a 250+ pressure game','game')
   seven_ten='7–10 Split' in getattr(p,'special_conversions',set())
   for title,detail in unlock_achievements(p.bowler.id,sm,{'seven_ten':seven_ten}):
    achievement_cards.append((p.bowler.name,title,detail))
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
