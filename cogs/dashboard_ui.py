import asyncio, discord
from storage.database import connect
from services.roster import create_team,add_team_member,team_roster
from services.competition import create_tournament,add_entry,start_tournament,bracket
from services.state import SESSIONS
from services.lane_visual import lane_card
from services.audio import join_user_voice
from services.v25 import tournament_dashboard,undo_snapshot,restore_session
from services.career import rollback_delivery_changes
from ui.embeds import bracket_embed

def rows(sql,args=()):
 with connect() as c:return c.execute(sql,args).fetchall()
def opts(items,label='name'):
 return [discord.SelectOption(label=str(x[label])[:100],value=str(x['id'])) for x in items[:25]]
async def nav(i,title,view,body='Choose an option below.'):await i.response.edit_message(content=f'{title}\n{body}',embed=None,attachments=[],view=view)

class Nav(discord.ui.View):
 def __init__(self):super().__init__(timeout=600)
 @discord.ui.button(label='🛠️ Admin Home',style=discord.ButtonStyle.secondary,row=4)
 async def admin(self,i,b):
  from cogs.menu import AdminMenu
  await nav(i,'🛠️ **Gutter Saints Admin Control**',AdminMenu())
 @discord.ui.button(label='🏠 Main Menu',style=discord.ButtonStyle.secondary,row=4)
 async def home(self,i,b):
  from cogs.menu import PublicMenu
  await nav(i,'🎳 **THE GUTTER SAINTS**',PublicMenu(),'Bowling, careers, achievements and tournament control.')

class TeamCreateModal(discord.ui.Modal,title='Create Team'):
 name=discord.ui.TextInput(label='Team name',max_length=40)
 flair=discord.ui.TextInput(label='Team flair (0-50)',default='0',max_length=2)
 async def on_submit(self,i):
  try:f=int(self.flair.value)
  except:return await i.response.send_message('Flair must be 0–50.',ephemeral=True)
  if not 0<=f<=50:return await i.response.send_message('Flair must be 0–50.',ephemeral=True)
  try:create_team(self.name.value.strip(),i.user.id,f)
  except Exception as e:return await i.response.send_message(f'Could not create team: {e}',ephemeral=True)
  await i.response.send_message(f'🎳 Team **{self.name.value.strip()}** created.',ephemeral=True)

class TeamMemberView(Nav):
 def __init__(self):
  super().__init__();teams=rows('SELECT id,name FROM teams ORDER BY name');bowlers=rows('SELECT id,name FROM bowlers ORDER BY name')
  self.team=self.bowler=None;self.slot=1
  if teams:self.add_item(Pick(self,'team','Team',opts(teams),0))
  if bowlers:self.add_item(Pick(self,'bowler','Bowler',opts(bowlers),1))
  self.add_item(Pick(self,'slot','Roster slot',[discord.SelectOption(label=str(x),value=str(x)) for x in range(1,6)],2))
 @discord.ui.button(label='Add / Move Bowler',style=discord.ButtonStyle.success,row=3)
 async def add(self,i,b):
  if not self.team or not self.bowler:return await i.response.send_message('Choose a team and bowler first.',ephemeral=True)
  t=rows('SELECT name FROM teams WHERE id=?',(self.team,));p=rows('SELECT name FROM bowlers WHERE id=?',(self.bowler,))
  if not t or not p:return await i.response.send_message('Selection no longer exists.',ephemeral=True)
  ok=add_team_member(t[0]['name'],p[0]['name'],self.slot)
  await i.response.send_message(f"✅ {p[0]['name']} assigned to **{t[0]['name']}**, slot {self.slot}." if ok else 'Could not update roster.',ephemeral=True)

class Pick(discord.ui.Select):
 def __init__(self,parent,key,placeholder,options,row):
  self.parent=parent;self.key=key;super().__init__(placeholder=placeholder,options=options,row=row)
 async def callback(self,i):
  v=self.values[0];setattr(self.parent,self.key,int(v) if v.isdigit() else v);await i.response.defer()

class TeamRosterSelect(discord.ui.Select):
 def __init__(self):
  teams=rows('SELECT id,name FROM teams ORDER BY name');super().__init__(placeholder='Choose team',options=opts(teams) or [discord.SelectOption(label='No teams',value='0')])
 async def callback(self,i):
  r=team_roster(next((x['name'] for x in rows('SELECT id,name FROM teams') if x['id']==int(self.values[0])),''))
  await i.response.send_message('👥 **Roster**\n'+('\n'.join(f"{x['slot']}. {x['name']}" for x in r) or 'No bowlers assigned.'),ephemeral=True)
class RosterView(Nav):
 def __init__(self):super().__init__();self.add_item(TeamRosterSelect())

class TeamDashboard(Nav):
 @discord.ui.button(label='➕ Create Team',style=discord.ButtonStyle.success)
 async def create(self,i,b):await i.response.send_modal(TeamCreateModal())
 @discord.ui.button(label='➕ Add / Move Bowler',style=discord.ButtonStyle.primary)
 async def member(self,i,b):await nav(i,'👥 **Roster Manager**',TeamMemberView())
 @discord.ui.button(label='👥 View Roster',style=discord.ButtonStyle.primary)
 async def roster(self,i,b):await nav(i,'👥 **Team Rosters**',RosterView())

class TournamentCreateModal(discord.ui.Modal,title='Create Tournament'):
 name=discord.ui.TextInput(label='Tournament name',max_length=50)
 lane=discord.ui.TextInput(label='Oil pattern',default='house',placeholder='house / fresh / dry / oily / transition')
 async def on_submit(self,i):
  ln=self.lane.value.lower().strip()
  if ln not in ('house','fresh','dry','oily','transition'):return await i.response.send_message('Invalid oil pattern.',ephemeral=True)
  try:create_tournament(self.name.value.strip(),ln)
  except Exception as e:return await i.response.send_message(f'Could not create tournament: {e}',ephemeral=True)
  await i.response.send_message(f'🏆 **{self.name.value.strip()}** created. Registration is open.',ephemeral=True)

class TournamentManageView(Nav):
 def __init__(self):
  super().__init__();ts=rows("SELECT id,name FROM tournaments WHERE status IN ('registration','active') ORDER BY id DESC");teams=rows('SELECT id,name FROM teams ORDER BY name')
  self.tournament=self.team=None
  if ts:self.add_item(Pick(self,'tournament','Tournament',opts(ts),0))
  if teams:self.add_item(Pick(self,'team','Team',opts(teams),1))
 @discord.ui.button(label='Enter Team',style=discord.ButtonStyle.success,row=2)
 async def enter(self,i,b):
  if not self.tournament or not self.team:return await i.response.send_message('Choose tournament and team.',ephemeral=True)
  t=rows('SELECT name FROM tournaments WHERE id=?',(self.tournament,));tm=rows('SELECT name FROM teams WHERE id=?',(self.team,))
  ok=bool(t and tm and add_entry(t[0]['name'],tm[0]['name']))
  await i.response.send_message('✅ Team entered.' if ok else 'Could not enter team; registration may be closed.',ephemeral=True)
 @discord.ui.button(label='Start Tournament',style=discord.ButtonStyle.danger,row=2)
 async def start(self,i,b):
  if not self.tournament:return await i.response.send_message('Choose a tournament.',ephemeral=True)
  t=rows('SELECT name FROM tournaments WHERE id=?',(self.tournament,))
  if not t:return await i.response.send_message('Tournament no longer exists.',ephemeral=True)
  _,err=start_tournament(t[0]['name'])
  if err:return await i.response.send_message(err,ephemeral=True)
  tr,br=bracket(t[0]['name']);await i.response.send_message('📣 **THE BRACKET IS SET!**',embed=bracket_embed(tr,br),ephemeral=True)
 @discord.ui.button(label='Show Bracket',style=discord.ButtonStyle.primary,row=2)
 async def show(self,i,b):
  if not self.tournament:return await i.response.send_message('Choose a tournament.',ephemeral=True)
  t=rows('SELECT name FROM tournaments WHERE id=?',(self.tournament,));tr,br=bracket(t[0]['name']) if t else (None,[])
  if not tr:return await i.response.send_message('Tournament not found.',ephemeral=True)
  await i.response.send_message(embed=bracket_embed(tr,br),ephemeral=True)
 @discord.ui.button(label='Open Director',style=discord.ButtonStyle.success,row=3)
 async def director(self,i,b):
  if not self.tournament:return await i.response.send_message('Choose a tournament.',ephemeral=True)
  t=rows('SELECT name FROM tournaments WHERE id=?',(self.tournament,))
  if not t:return await i.response.send_message('Tournament not found.',ephemeral=True)
  from cogs.director import DirectorView
  d=tournament_dashboard(t[0]['name'])
  if not d:return await i.response.send_message('Tournament has no dashboard data.',ephemeral=True)
  tr,matches,nxt,leaders=d;desc=f"Status **{tr['status']}** • Completed **{sum(x['status']=='complete' for x in matches)}/{len(matches)}**"
  if nxt:desc+=f"\nNext: **R{nxt['round_no']} M{nxt['match_no']} — {nxt['team_a']} vs {nxt['team_b']}**"
  await i.response.edit_message(content=None,embed=discord.Embed(title=f"🏆 Tournament Director — {tr['name']}",description=desc),view=DirectorView(tr['name']))

class CompetitionDashboard(Nav):
 @discord.ui.button(label='🏆 Competition Director',style=discord.ButtonStyle.success)
 async def director(self,i,b):
  from cogs.competition_ui import CompetitionDirector
  await i.response.edit_message(content='🏆 **Competition Director**\nSelect a competition, then manage the season without IDs or slash commands.',embed=None,view=CompetitionDirector())
 @discord.ui.button(label='📅 Active Competitions',style=discord.ButtonStyle.primary)
 async def active(self,i,b):
  from cogs.competition_ui import competition_embed
  rs=rows("SELECT id,name FROM competitions WHERE state IN ('registration','locked','active') ORDER BY id DESC")
  if not rs:return await i.response.send_message('No active competitions.',ephemeral=True)
  await i.response.send_message('\n'.join(f"• **{x['name']}**" for x in rs),ephemeral=True)

class TournamentDashboard(Nav):
 @discord.ui.button(label='➕ Create Tournament',style=discord.ButtonStyle.success)
 async def create(self,i,b):await i.response.send_modal(TournamentCreateModal())
 @discord.ui.button(label='🏆 Manage Tournament',style=discord.ButtonStyle.primary)
 async def manage(self,i,b):await nav(i,'🏆 **Tournament Manager**',TournamentManageView())
 @discord.ui.button(label='📋 Tournament List',style=discord.ButtonStyle.secondary)
 async def listing(self,i,b):
  r=rows('SELECT name,status FROM tournaments ORDER BY id DESC LIMIT 20');await i.response.send_message('🏆 **Tournaments**\n'+('\n'.join(f"• {x['name']} — {x['status']}" for x in r) or 'None'),ephemeral=True)

class MatchSetupView(Nav):
 def __init__(self):
  super().__init__();teams=rows('SELECT id,name FROM teams ORDER BY name');self.team=self.opponent=None;self.lane='house'
  if teams:
   self.add_item(Pick(self,'team','Team A',opts(teams),0))
   op=[discord.SelectOption(label='Solo team game',value='none')]+opts(teams)[:24];self.add_item(Pick(self,'opponent','Opponent',op,1))
  self.add_item(Pick(self,'lane','Oil pattern',[discord.SelectOption(label=x.title(),value=x) for x in ('house','fresh','dry','oily','transition')],2))
 @discord.ui.button(label='Start Match',style=discord.ButtonStyle.success,row=3)
 async def start(self,i,b):
  if not self.team:return await i.response.send_message('Choose Team A.',ephemeral=True)
  ta=rows('SELECT name FROM teams WHERE id=?',(self.team,));opp=None if self.opponent in (None,'none') else rows('SELECT name FROM teams WHERE id=?',(self.opponent,))
  if not ta:return await i.response.send_message('Team no longer exists.',ephemeral=True)
  if opp and opp[0]['name']==ta[0]['name']:return await i.response.send_message('Choose a different opponent.',ephemeral=True)
  cog=i.client.get_cog('Games')
  if not cog:return await i.response.send_message('Games system is unavailable.',ephemeral=True)
  from discord import app_commands
  lane=app_commands.Choice(name=self.lane.title(),value=self.lane)
  await cog.start.callback(cog,i,ta[0]['name'],opp[0]['name'] if opp else None,lane,None)

class RecoveryView(Nav):
 @discord.ui.button(label='Undo Last Ball',style=discord.ButtonStyle.danger)
 async def undo(self,i,b):
  cur=SESSIONS.get(i.channel_id);changes=getattr(cur,'last_attribute_changes',[]) if cur else [];bid=getattr(cur,'last_attribute_bowler_id',None) if cur else None;s=undo_snapshot(i.channel_id)
  if not s:return await i.response.send_message('No earlier snapshot.',ephemeral=True)
  rollback_delivery_changes(bid,changes);SESSIONS[i.channel_id]=s;await i.response.send_message('↩️ Last ball restored.',ephemeral=True)
 @discord.ui.button(label='Restore Match',style=discord.ButtonStyle.primary)
 async def restore(self,i,b):
  s=restore_session(i.channel_id)
  if not s:return await i.response.send_message('No saved active match.',ephemeral=True)
  SESSIONS[i.channel_id]=s;await i.response.send_message('♻️ Match restored.',ephemeral=True)

class MatchDashboard(Nav):
 @discord.ui.button(label='🎳 Start Match',style=discord.ButtonStyle.success)
 async def start(self,i,b):await nav(i,'🎳 **Exhibition Match Setup**',MatchSetupView())
 @discord.ui.button(label='📺 Lane View',style=discord.ButtonStyle.primary)
 async def lane(self,i,b):
  s=SESSIONS.get(i.channel_id)
  if not s:return await i.response.send_message('No active game in this channel.',ephemeral=True)
  await i.response.send_message(file=discord.File(lane_card(s),filename='gutter_lane.png'),ephemeral=True)
 @discord.ui.button(label='↩️ Undo / Restore',style=discord.ButtonStyle.danger)
 async def recovery(self,i,b):await nav(i,'↩️ **Match Recovery**',RecoveryView())

class AwardSelect(discord.ui.Select):
 def __init__(self,parent):
  self.parent=parent;b=rows('SELECT id,name FROM bowlers ORDER BY name');super().__init__(placeholder='Choose bowler',options=opts(b) or [discord.SelectOption(label='No bowlers',value='0')])
 async def callback(self,i):self.parent.bowler=int(self.values[0]);await i.response.defer()
class AwardModal(discord.ui.Modal,title='Give Award'):
 title_in=discord.ui.TextInput(label='Award title',max_length=60)
 detail=discord.ui.TextInput(label='Detail',required=False,max_length=200)
 def __init__(self,bid):super().__init__();self.bid=bid
 async def on_submit(self,i):
  b=rows('SELECT name FROM bowlers WHERE id=?',(self.bid,))
  if not b:return await i.response.send_message('Bowler not found.',ephemeral=True)
  with connect() as c:
   c.execute('INSERT OR IGNORE INTO bowler_stats(bowler_id) VALUES(?)',(self.bid,));c.execute('INSERT INTO awards(bowler_id,title,detail) VALUES(?,?,?)',(self.bid,self.title_in.value,self.detail.value));c.execute('UPDATE bowler_stats SET awards=awards+1 WHERE bowler_id=?',(self.bid,))
  await i.response.send_message(f"🏅 **{self.title_in.value}** awarded to **{b[0]['name']}**.",ephemeral=True)
class AwardsView(Nav):
 def __init__(self):super().__init__();self.bowler=None;self.add_item(AwardSelect(self))
 @discord.ui.button(label='View Awards',style=discord.ButtonStyle.primary,row=1)
 async def view(self,i,b):
  if not self.bowler:return await i.response.send_message('Choose a bowler.',ephemeral=True)
  p=rows('SELECT name FROM bowlers WHERE id=?',(self.bowler,));a=rows('SELECT title,detail FROM awards WHERE bowler_id=? ORDER BY id DESC',(self.bowler,))
  await i.response.send_message(f"🏅 **{p[0]['name']} — Awards**\n"+('\n'.join(f"• **{x['title']}**"+(f" — {x['detail']}" if x['detail'] else '') for x in a) or 'No awards yet.'),ephemeral=True)
 @discord.ui.button(label='Give Award',style=discord.ButtonStyle.success,row=1)
 async def give(self,i,b):
  if not self.bowler:return await i.response.send_message('Choose a bowler.',ephemeral=True)
  await i.response.send_modal(AwardModal(self.bowler))

class SimModal(discord.ui.Modal,title='Simulation Lab'):
 bowler=discord.ui.TextInput(label='Bowler name',max_length=32)
 games=discord.ui.TextInput(label='Games (1,000–100,000)',default='10000')
 test=discord.ui.TextInput(label='Test',default='accuracy_spin',placeholder='rank / accuracy_spin / handedness / nerves')
 lane=discord.ui.TextInput(label='Lane',default='house',placeholder='house / fresh / oily / dry / transition')
 burn=discord.ui.TextInput(label='Burn %',default='0',placeholder='0–100')
 async def on_submit(self,i):
  try:n=int(self.games.value);bn=int(self.burn.value)
  except:return await i.response.send_message('Games and burn must be numbers.',ephemeral=True)
  if not 1000<=n<=100000 or not 0<=bn<=100:return await i.response.send_message('Games 1,000–100,000; burn 0–100.',ephemeral=True)
  kind=self.test.value.strip().lower();ln=self.lane.value.strip().lower()
  if kind not in ('rank','accuracy_spin','handedness','nerves') or ln not in ('house','fresh','oily','dry','transition'):return await i.response.send_message('Invalid test or lane.',ephemeral=True)
  from cogs.simulation_lab import profiles
  from services.simulation_lab import compare,dominance_flags
  from models.bowler import Bowler
  r=rows('SELECT * FROM bowlers WHERE name=? COLLATE NOCASE',(self.bowler.value.strip(),))
  if not r:return await i.response.send_message('Bowler not found.',ephemeral=True)
  x=r[0];bo=Bowler(**{k:x[k] for k in ['id','name','owner_id','handedness','rank','accuracy','style','flair','consistency','spin','nerves']})
  await i.response.defer(ephemeral=True,thinking=True);res=await asyncio.to_thread(compare,profiles(kind,bo),n,ln,bn/100,7275)
  lines=[f"**{x['name']}** — Avg {x['avg']:.1f} • Strike {x['strike_pct']:.1f}% • Spare {x['spare_pct']:.1f}% • 200+ {x['p200']:.1f}%" for x in res];flags=dominance_flags(res)
  await i.followup.send('🧠 **SIMULATION LAB**\n'+'\n'.join(lines)+(('\n⚠️ '+'; '.join(flags)) if flags else '\n✅ No dominance threshold triggered.'),ephemeral=True)

class RecordsDashboard(Nav):
 @discord.ui.button(label='🏛️ Hall of Fame',style=discord.ButtonStyle.primary)
 async def hof(self,i,b):
  r=rows('SELECT b.name,s.high_game,s.perfect_games FROM bowler_stats s JOIN bowlers b ON b.id=s.bowler_id WHERE s.games>0 ORDER BY s.high_game DESC LIMIT 10')
  await i.response.send_message('🏛️ **Hall of Fame**\n'+('\n'.join(f"• {x['name']} — HG {x['high_game']} • 300s {x['perfect_games']}" for x in r) or 'No records yet.'),ephemeral=True)
 @discord.ui.button(label='🏅 Awards',style=discord.ButtonStyle.primary)
 async def awards(self,i,b):await nav(i,'🏅 **Awards**',AwardsView())
 @discord.ui.button(label='🧠 Simulation Lab',style=discord.ButtonStyle.success)
 async def sim(self,i,b):await i.response.send_modal(SimModal())

class SettingsDashboard(Nav):
 @discord.ui.button(label='🔊 Join / Move Voice',style=discord.ButtonStyle.primary)
 async def voice(self,i,b):
  ok,msg=await join_user_voice(i);await i.response.send_message(msg,ephemeral=True)
 @discord.ui.button(label='🔇 Leave Voice',style=discord.ButtonStyle.secondary)
 async def leave(self,i,b):
  vc=i.guild.voice_client if i.guild else None
  if vc:await vc.disconnect();await i.response.send_message('🔇 Presentation audio disconnected.',ephemeral=True)
  else:await i.response.send_message('I am not connected to voice.',ephemeral=True)
 @discord.ui.button(label='🎥 Media Setup',style=discord.ButtonStyle.primary)
 async def media(self,i,b):await i.response.send_message('GIFs: **assets/media.json**\nAudio: **assets/audio.json**\nUse the manifests to add or replace presentation assets.',ephemeral=True)
