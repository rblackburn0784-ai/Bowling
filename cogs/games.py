from services.broadcast_studio import BroadcastConfig,replay_reason,shot_identity,mode as broadcast_mode
import asyncio,discord,logging
from discord import app_commands
from discord.ext import commands
from services.roster import team_roster
from models.bowler import Bowler
from services.game_engine import GameSession
from services.state import SESSIONS
from services.media import pick
from services.lane_visual import lane_card,lane_sequence
from services.shot_animation import animated_shot,replay_shot,DISCORD_PLAYBACK_HEADROOM_SECONDS
from services.bowler_sprites import sprite_key,has_sequence,APPROACH_FRAME_SECONDS
from services.audio import play_sound
from services.presentation import classify,AUDIO_MAP,GIF_MAP,layout_policy
from services.commentary import line,streak_call,rivalry_call,contact_call,lane_call
from services.analytics import player_summary
from storage.database import record_completed_session,connect
from services.v25 import save_snapshot,clear_session,prepare_new_session,backup_database,audit
from ui.embeds import scoreboard_embed
from services.v271 import bowler_loadout,tournament_presentation
from services.career import delivery_growth,add_timeline_event
from services.broadcast_director import match_context,persist_story,story_call,match_story_summary
from services.postgame import commit_postgame,finalize_completed_session
from services.victory_presentation import winning_bowler
from services.scene_renderer import render_scene as render_victory_scene
from services.showtime import crowd_cue,group_rosters,is_finals
from services.showtime_graphics import intro_card,final_card

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
STOP_REQUESTS={}  # channel -> (session_uid, cancelling administrator ID)
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

def channel_has_active_match(channel_id):
 """Protect both legacy commands and dashboards, even after bot restart."""
 if channel_id in MATCH_BUSY:return True
 current=SESSIONS.get(channel_id)
 if current is not None:return True
 from services.v25 import restore_session
 stored=restore_session(channel_id)
 return stored is not None

async def recover_completed_match(i, session):
 """Complete an interrupted finish, or safely clear an already committed one."""
 await i.response.defer(ephemeral=True)
 try:
  if not getattr(session,'friendly_challenge',False):
   with connect() as db:
    old=db.execute("SELECT g.id FROM games g JOIN game_finalizations f ON f.game_id=g.id WHERE g.session_uid=?",(session.session_uid,)).fetchone()
   if old:
    clear_session(i.channel_id)
    SESSIONS.pop(i.channel_id,None)
    await i.followup.send('✅ This game and its career/tournament effects were already committed. Stale recovery state was cleared; no awards were duplicated.',ephemeral=True)
    return True
  cog=i.client.get_cog('Games')
  if cog is None:
   await i.followup.send('Game service is not available to finalise this match.',ephemeral=True)
   return False
  SESSIONS[i.channel_id]=session
  await cog.finish(i.channel,session,i.channel_id)
  await i.followup.send('✅ Interrupted game finalisation safely completed.',ephemeral=True)
  return True
 except Exception:
  logging.exception('Interrupted game finalisation failed in channel %s',i.channel_id)
  await i.followup.send('⚠️ Finalisation failed again. The saved result remains recoverable; do not start a replacement match in this channel.',ephemeral=True)
  return False

async def stop_active_match(channel,session,actor_id):
 """Cancel an uncommitted game, including reversible per-ball career changes."""
 key=channel.id
 if SESSIONS.get(key) is not session:
  return False,'This match is no longer active; use the current scoreboard.'
 from services.v25 import cancel_unfinished_session
 uid=session.session_uid
 try:
  ok,detail=cancel_unfinished_session(key,uid,actor_id)
 except Exception as exc:
  logging.exception('Could not safely cancel match in channel %s',key)
  return False,f'Cancellation was refused for safety: {exc}'
 if not ok:
  return False,detail
 STOP_REQUESTS.pop(key,None)
 SESSIONS.pop(key,None)
 previous=LANE_MESSAGES.pop(key,None)
 if previous is not None:
  try:
   await previous.edit(embed=discord.Embed(title='🛑 MATCH CANCELLED',
        description='Unranked/unfinished game discarded — no final score recorded.'),
        attachments=[],view=None)
  except (discord.HTTPException,AttributeError):
   logging.warning('Could not remove stale scoreboard controls for cancelled match')
 try:
  await channel.send(f'🛑 **GAME STOPPED** — {detail}')
 except discord.HTTPException:
  logging.warning('Could not post cancellation announcement in channel %s',key)
 return True,detail


class StopMatchConfirm(discord.ui.View):
 """Two-click admin-only stop; applies even if Auto Play is underway."""
 def __init__(self,channel_id,session):
  super().__init__(timeout=60)
  self.channel_id=channel_id;self.session=session
 async def interaction_check(self,i):
  permissions=getattr(i.user,'guild_permissions',None)
  if (i.channel_id!=self.channel_id or
      not permissions or not (permissions.administrator or permissions.manage_guild)):
   await i.response.send_message('Only a server administrator can stop a match.',ephemeral=True)
   return False
  if SESSIONS.get(self.channel_id) is not self.session:
   await i.response.send_message('Match controls are stale.',ephemeral=True)
   return False
  return True
 @discord.ui.button(label='🛑 Confirm Stop',style=discord.ButtonStyle.danger)
 async def confirm(self,i,b):
  await i.response.defer(ephemeral=True)
  if self.channel_id in MATCH_BUSY:
   STOP_REQUESTS[self.channel_id]=(self.session.session_uid,i.user.id)
   await i.followup.send('🛑 Stop requested. The current delivery will finish its visual playback, then the game will be cancelled without a final result.',ephemeral=True)
  else:
   ok,message=await stop_active_match(i.channel,self.session,i.user.id)
   await i.followup.send(('✅ ' if ok else '⚠️ ')+message,ephemeral=True)
  self.stop()
 @discord.ui.button(label='Keep Playing',style=discord.ButtonStyle.secondary)
 async def keep(self,i,b):
  self.stop()
  await i.response.edit_message(content='Match continues.',view=None)


async def prompt_stop_match(i,session):
 permissions=getattr(i.user,'guild_permissions',None)
 if not permissions or not (permissions.administrator or permissions.manage_guild):
  return await i.response.send_message('Manage Server permission required to stop games.',ephemeral=True)
 if session is None:
  from services.v25 import restore_session
  session=restore_session(i.channel_id)
  if session is not None:
   SESSIONS[i.channel_id]=session
 if not session or SESSIONS.get(i.channel_id) is not session:
  return await i.response.send_message('No current or recoverable match to stop.',ephemeral=True)
 await i.response.send_message('⚠️ **Stop this game?** This discards its unfinished score, '
   'reverts its own career changes, and releases the channel. Completed results are never erased.',
   view=StopMatchConfirm(i.channel_id,session),ephemeral=True)


class LiveMatchControls(discord.ui.View):
 """Buttons belong to the current channel's active match, not a stale view."""
 def __init__(self,channel_id,session):
  super().__init__(timeout=3600)
  self.channel_id=channel_id
  self.session=session

 async def interaction_check(self,i):
  stop_button=(getattr(i,'data',None) or {}).get('custom_id')=='gutter:stop-match'
  if i.channel_id!=self.channel_id or SESSIONS.get(self.channel_id) is not self.session or (self.session.complete and not stop_button):
   await i.response.send_message('This match has finished or its controls are out of date.',ephemeral=True)
   return False
  if not can_operate_match(i.user,self.session):
   await i.response.send_message('Only a competing player or server administrator can bowl this match.',ephemeral=True)
   return False
  return True

 @discord.ui.button(label='🛑 Stop Game',style=discord.ButtonStyle.danger,custom_id='gutter:stop-match')
 async def stop_game(self,i,b):
  await prompt_stop_match(i,self.session)

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

async def publish_match_intro(channel,session):
 """One pre-match intro per explicitly new session, never on Undo/Restore."""
 if getattr(session,'_showtime_intro_sent',False):return False
 session._showtime_intro_sent=True
 groups=group_rosters(session)
 lineup=' vs '.join(groups) if len(groups)>1 else ', '.join(p.bowler.name for p in session.players[:6])
 kind='🏆 CHAMPIONSHIP NIGHT' if is_finals(session) else '🎙️ TONIGHT ON GUTTER SAINTS'
 try:
  safe=discord.utils.escape_mentions(discord.utils.escape_markdown(lineup[:250]))
  await channel.send(f'{kind} — **{safe}**',
                     file=discord.File(intro_card(session),filename=f'gs_intro_{session.seed}.png'))
  if is_finals(session):await play_sound(channel,'entrance')
  return True
 except Exception:
  logging.exception('Match introduction presentation unavailable; match still playable')
  return False

async def publish_match_final(channel,session,winner):
 """Display the closing scorecard after all completed matches; visual only."""
 try:
  label='🏆 CHAMPIONSHIP RESULT' if is_finals(session) else '🏁 MATCH COMPLETE'
  await channel.send(label,file=discord.File(final_card(session,winner),
                     filename=f'gs_final_{session.seed}.png'))
  if is_finals(session):await play_sound(channel,'champion')
  return True
 except Exception:
  logging.exception('Final presentation card unavailable; completed result remains valid')
  return False

async def post_match_controls(channel,session,introduce=False):
 """Live controls. Intro runs for new starts only; Undo/Restore never re-announces."""
 if introduce:await publish_match_intro(channel,session)
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


async def broadcast_replay(channel,session,event):
 """Read-only slow-motion replay of an already-delivered shot."""
 reason=replay_reason(event,session)
 if not reason or not BroadcastConfig().replay:return False
 try:
  clip,duration=await asyncio.to_thread(replay_shot,session,event,BroadcastConfig().slow_motion)
  if clip is None:return False
  current=LANE_MESSAGES.get(channel.id)
  if current is None:return False
  shot=getattr(session,'ball_count',0)
  picture=discord.File(clip,filename=f'gs_replay_{session.seed}_{shot}.gif')
  embed=scoreboard_embed(session,event,stage='impact')
  embed.set_footer(text=f'🎥 {reason} • Recorded delivery replay — no extra shot')
  await current.edit(embed=embed,attachments=[picture])
  await asyncio.sleep(duration+DISCORD_PLAYBACK_HEADROOM_SECONDS)
  await update_lane(channel,session,event,'leave')
  return True
 except Exception:
  logging.exception('Broadcast replay failed; game result remains untouched')
  try:await update_lane(channel,session,event,'leave')
  except Exception:logging.exception('Could not restore lane after replay')
  return False

async def publish_victory(channel,session,last_event=None):
 """Edit the one live graphic to the champion's optional cheer.png pose.

 Never risk losing the game result because Discord uploads or local
 artwork fail. Both pin cameras remain unchanged from the last delivery.
 """
 champion=winning_bowler(session)
 if champion is None:
  return False
 try:
  event=dict(last_event or {'before':[],'down':[],'after':[]},
             bowler_id=champion.bowler.id)
  picture=render_victory_scene(session,event,'victory',
                                victor_id=champion.bowler.id)
  if picture is None:
   return False
  embed=scoreboard_embed(session)
  embed.add_field(name='🏆 Match Winner',
                  value=f'**{champion.bowler.name}** — Victory celebration',
                  inline=False)
  file=discord.File(picture,filename=f'gutter_victory_{session.seed}.png')
  previous=LANE_MESSAGES.get(channel.id)
  if previous:
   try:
    await previous.edit(embed=embed,attachments=[file],view=None)
    return True
   except (discord.NotFound,discord.Forbidden):
    LANE_MESSAGES.pop(channel.id,None)
  await channel.send(embed=embed,file=file)
  return True
 except Exception:
  logging.exception('Could not publish victory sprite in channel %s',channel.id)
  return False


async def send_media(channel,kind):
 url=pick(kind)
 if url:await channel.send(url)
class Games(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='game_start',description='Start an unranked team exhibition (no career, ranking or achievements)')
 @app_commands.choices(lane=[app_commands.Choice(name=x.title(),value=x) for x in ['house','fresh','dry','oily','transition']],
                        layout=[app_commands.Choice(name=x.title(),value=x) for x in ['standard','broadcast','finals','chaos']])
 async def start(self,i:discord.Interaction,team:str,opponent:str|None=None,lane:app_commands.Choice[str]|None=None,seed:int|None=None,layout:app_commands.Choice[str]|None=None):
  if channel_has_active_match(i.channel_id):
   return await i.response.send_message("A match is already active or recoverable in this channel. Finish or restore it first.",ephemeral=True)
  ra=team_roster(team);rr=team_roster(opponent) if opponent else []
  if not ra:return await i.response.send_message('No roster found for the first team.',ephemeral=True)
  if opponent and not rr:return await i.response.send_message('No roster found for the opponent.',ephemeral=True)
  bowlers=[]
  if opponent:
   for n in range(max(len(ra),len(rr))):
    if n<len(ra):bowlers.append(rb(ra[n],team))
    if n<len(rr):bowlers.append(rb(rr[n],opponent))
  else:bowlers=[rb(x,team) for x in ra]
  s=GameSession(bowlers,seed,lane.value if lane else 'house',
                layout=layout.value if layout else 'broadcast')
  s.friendly_challenge=True; s.practice_no_rewards=True  # Unsanctioned /game_start is an exhibition.
  prepare_new_session(i.channel_id);SESSIONS[i.channel_id]=s
  for p in s.players:p.ball_key=bowler_loadout(p.bowler.id).get('primary_ball','hybrid')
  save_snapshot(i.channel_id,s,'start')
  await i.response.send_message(f"🤝 **UNRANKED EXHIBITION — NO CAREER REWARDS**\n**{team}**"+(f' vs **{opponent}**' if opponent else ''))
  await post_match_controls(i.channel,s,introduce=True)
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
  if not can_operate_match(i.user,s):return await i.response.send_message('Only a competing bowler or server administrator may change this shot.',ephemeral=True)
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
  if key in STOP_REQUESTS and STOP_REQUESTS[key][0]==getattr(s,'session_uid',None):
   stopped,reason=await stop_active_match(ch,s,STOP_REQUESTS[key][1])
   if not stopped:raise RuntimeError('Game stop blocked: '+reason)
   return
  director=await self.reaction(ch,s,ev)
  if key in STOP_REQUESTS and STOP_REQUESTS[key][0]==getattr(s,'session_uid',None):
   stopped,reason=await stop_active_match(ch,s,STOP_REQUESTS[key][1])
   if not stopped:raise RuntimeError('Game stop blocked: '+reason)
   return
  await update_lane(ch,s,ev,'leave',director=director)
  if not getattr(s,'broadcast_replay_off',False):
   await broadcast_replay(ch,s,ev)
  if key in STOP_REQUESTS and STOP_REQUESTS[key][0]==getattr(s,'session_uid',None):
   stopped,reason=await stop_active_match(ch,s,STOP_REQUESTS[key][1])
   if not stopped:raise RuntimeError('Game stop blocked: '+reason)
   return
  if s.complete:
   await self.finish(ch,s,key,ev)

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
    if key in STOP_REQUESTS and STOP_REQUESTS[key][0]==getattr(s,'session_uid',None):
     stopped,reason=await stop_active_match(ch,s,STOP_REQUESTS[key][1])
     if not stopped:raise RuntimeError('Game stop blocked: '+reason)
     break
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

 @app_commands.command(name='game_stop',description='Administrator: safely cancel the current unfinished match')
 @app_commands.default_permissions(manage_guild=True)
 async def game_stop(self,i:discord.Interaction):
  await prompt_stop_match(i,SESSIONS.get(i.channel_id))

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
  audience=crowd_cue(s,ev)
  if audience:announcement=(announcement+'\n' if announcement else '')+audience
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
 async def finish(self,ch,s,key,last_event=None):
  if getattr(s,'friendly_challenge',False):
   with connect() as db:
    db.execute('CREATE TABLE IF NOT EXISTS friendly_xp_daily(bowler_id INTEGER NOT NULL,day TEXT NOT NULL,PRIMARY KEY(bowler_id,day))')
    for p in s.players:
     if getattr(s,'practice_no_rewards',False):continue
     granted=db.execute("INSERT OR IGNORE INTO friendly_xp_daily(bowler_id,day) VALUES(?,date('now'))",(p.bowler.id,)).rowcount
     if granted:
      # Exhibition rewards are recorded separately and cannot trigger rank XP.
      db.execute('INSERT OR IGNORE INTO exhibition_rewards(bowler_id) VALUES(?)',(p.bowler.id,))
      db.execute('UPDATE exhibition_rewards SET cosmetic_xp=cosmetic_xp+1 WHERE bowler_id=?',(p.bowler.id,))
   await ch.send('🤝 **UNRANKED EXHIBITION COMPLETE** — No standings, rank, career attributes, achievements or history.' if getattr(s,'practice_no_rewards',False) else '🤝 **FRIENDLY EXHIBITION COMPLETE** — No league points, rank changes, career attribute growth or achievements. Each bowler can earn at most **1 non-ranking XP per UTC day** from friendly challenges.')
   await ch.send(embed=scoreboard_embed(s))
   s.persisted=True
   await publish_victory(ch,s,last_event)
   friendly_winner=winning_bowler(s)
   await publish_match_final(ch,s,friendly_winner.bowler.name if friendly_winner else None)
   LANE_MESSAGES.pop(key,None)
   SESSIONS.pop(key,None)
   clear_session(key)
   return
  # Calculate all bowler summaries *before* recording the result so a
  # formatting/analytics error cannot leave a half-finalised persisted game.
  summaries=sorted(((p,player_summary(p)) for p in s.players),
                   key=lambda pair:pair[1]['score'],reverse=True)
  if not summaries:
   raise ValueError('Cannot finalise a game without bowlers')
  totals=s.team_totals()
  winner=max(totals,key=totals.get) if len(totals)>1 and len(set(totals.values()))>1 else None
  if (s.tournament_id and s.match_id) or getattr(s,'fixture_id',None):
   backup_database('auto_competition_result')
  # Single SQLite transaction: game row, career XP, tournament bracket,
  # league fixture, series, standings and finalisation idempotency marker.
  gid,achievement_cards,winner,rolloff,newly_committed=finalize_completed_session(
   s,key,summaries,winner,totals)
  high=summaries[0]
  awards=[f"👑 **High Game:** {high[0].bowler.name} — {high[1]['score']}"]
  clean=[p.bowler.name for p,x in summaries if x['clean']]
  if clean:awards.append('✨ **Clean Game:** '+', '.join(clean))
  best_streak=max(summaries,key=lambda x:x[1]['longest_streak'])
  if best_streak[1]['longest_streak']>=3:awards.append(f"🔥 **Strike Run:** {best_streak[0].bowler.name} — {best_streak[1]['longest_streak']} straight")
  split=max(summaries,key=lambda x:x[1]['split_conversions'])
  if split[1]['split_conversions']:awards.append(f"🪓 **Split Slayer:** {split[0].bowler.name} — {split[1]['split_conversions']} converted")
  if winner:awards.insert(0,f'🏆 **Team Winner: {winner}** — {totals[winner]}'+(' (sudden-death roll-off)' if rolloff else ''))
  await ch.send('🏁 **GAME COMPLETE!**',embed=scoreboard_embed(s))
  await ch.send('🎖️ **POST-GAME HONOURS**\n'+'\n'.join(awards))
  stories=match_story_summary(s)
  if stories:
   priority={'comeback':6,'lead_change':5,'clutch':4,'pb_watch':3,'perfect_watch':7,'rivalry':3,'lane_read':1}
   top=sorted(stories,key=lambda r:priority.get(r['kind'],0),reverse=True)[:4]
   await ch.send('📰 **MATCH STORY**\n'+'\n'.join(f"• **{r['headline']}** — {r['detail']}" for r in top))
  for name,title,detail in achievement_cards:
   e=discord.Embed(title=f'🏅 ACHIEVEMENT UNLOCKED — {title}',description=f'**{name}**\n{detail}',colour=discord.Colour.gold())
   await ch.send(embed=e);await send_media(ch,'award')
  if (s.tournament_id and s.match_id or getattr(s,'fixture_id',None)) and len(totals)==2:
   if rolloff:
    names=sorted(totals)
    display=' | '.join(f"R{x['round']}: {x['pins'][names[0]]}-{x['pins'][names[1]]}" for x in rolloff)
    await ch.send(f'🎳 **SUDDEN-DEATH ROLL-OFF:** {names[0]} vs {names[1]} — {display}\n🏆 **{winner}** takes the tied match.')
   if s.tournament_id and s.match_id:
    await ch.send(f'🏆 **TOURNAMENT UPDATE:** {winner} advances automatically.')
   elif getattr(s,'fixture_id',None):
    with connect() as db:
     fx=db.execute('SELECT status FROM fixtures WHERE id=?',(s.fixture_id,)).fetchone()
    if fx:await ch.send(f'📊 **COMPETITION FIXTURE #{s.fixture_id}:** {fx["status"].title()} — result safely recorded.')
   if newly_committed and s.tournament_id and s.match_id:
    from services.gazette import build_gazette,format_gazette
    g=build_gazette(s.tournament_id)
    if g:await ch.send(format_gazette(g))
  await publish_victory(ch,s,last_event)
  champion=winning_bowler(s)
  await publish_match_final(ch,s,winner or (champion.bowler.name if champion else None))
  LANE_MESSAGES.pop(key,None)
  clear_session(key)
  SESSIONS.pop(key,None)
async def setup(bot):await bot.add_cog(Games(bot))
