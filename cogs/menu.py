import discord
from discord import app_commands
from discord.ext import commands
from services.roster import get_bowler_by_owner,list_bowlers
from storage.database import connect
from ui.embeds import bowler_embed
from services.equipment import BALLS
from services.v271 import bowler_loadout,set_bowler_ball

def admin_ok(i):return bool(i.user.guild_permissions.administrator or i.user.guild_permissions.manage_guild)
async def swap(i,title,view,body='Choose an option below.'):
 await i.response.edit_message(content=f'{title}\n{body}',embed=None,view=view)
class HomeView(discord.ui.View):
 def __init__(self):super().__init__(timeout=300)
 @discord.ui.button(label='🏠 Main Menu',style=discord.ButtonStyle.secondary)
 async def home(self,i,b):await swap(i,'🎳 **THE GUTTER SAINTS**',PublicMenu(),'Bowling, careers, achievements and tournament control.')
class AdminHomeView(HomeView):
 @discord.ui.button(label='🛠️ Admin Home',style=discord.ButtonStyle.secondary)
 async def adminhome(self,i,b):await swap(i,'🛠️ **Gutter Saints Admin Control**',AdminMenu())
class BowlerIdentityModal(discord.ui.Modal,title='Create Bowler'):
 name=discord.ui.TextInput(label='Bowler name',max_length=32)
 handedness=discord.ui.TextInput(label='Handedness',placeholder='R or L',default='R',max_length=1)
 async def on_submit(self,i):
  if get_bowler_by_owner(i.user.id):return await i.response.send_message('You already have a linked bowler.',ephemeral=True)
  hand=self.handedness.value.strip().upper()
  if hand not in ('R','L'):return await i.response.send_message('Handedness must be R or L.',ephemeral=True)
  state=BowlerBuildState(self.name.value.strip(),hand)
  await i.response.send_message(embed=builder_embed(state,1),view=StatPageOne(state),ephemeral=True)
class BowlerBuildState:
 def __init__(self,name,hand):
  self.name=name;self.hand=hand;self.stats={'accuracy':0,'style':0,'flair':0,'consistency':0,'spin':0,'nerves':0}
 @property
 def used(self):return sum(self.stats.values())
 @property
 def remaining(self):
  from config import DEFAULT_STAT_BUDGET
  return DEFAULT_STAT_BUDGET-self.used
def builder_embed(state,page):
 from config import DEFAULT_STAT_BUDGET
 labels={'accuracy':'Accuracy','style':'Style','flair':'Flair','consistency':'Consistency','spin':'Spin','nerves':'Nerves'}
 lines=[f"**{labels[k]}:** {v}" for k,v in state.stats.items()]
 colour=discord.Color.green() if state.remaining>=0 else discord.Color.red()
 e=discord.Embed(title=f'🎳 Build {state.name}',description='\n'.join(lines),colour=colour)
 e.add_field(name='Career Rank',value='**Rookie — Rank 1** (earned through play)',inline=False)\n e.add_field(name='Points',value=f'**Used:** {state.used} / {DEFAULT_STAT_BUDGET}\n**Remaining:** {state.remaining}',inline=False)
 e.set_footer(text=f'Stat Builder • Page {page}/2 • Each stat 0–50')
 return e
class StatSelect(discord.ui.Select):
 def __init__(self,state,key,label,row):
  self.state=state;self.key=key
  options=[discord.SelectOption(label=str(v),value=str(v),default=state.stats[key]==v) for v in range(0,51,2)]
  super().__init__(placeholder=f'{label}: {state.stats[key]}',options=options,row=row)
 async def callback(self,i):
  self.state.stats[self.key]=int(self.values[0])
  page=1 if self.key in ('accuracy','style','flair') else 2
  view=StatPageOne(self.state) if page==1 else StatPageTwo(self.state)
  await i.response.edit_message(embed=builder_embed(self.state,page),view=view)
class StatPageOne(discord.ui.View):
 def __init__(self,state):
  super().__init__(timeout=600);self.state=state
  for row,(key,label) in enumerate((('accuracy','Accuracy'),('style','Style'),('flair','Flair'))):self.add_item(StatSelect(state,key,label,row))
 @discord.ui.button(label='Next: More Stats',emoji='➡️',style=discord.ButtonStyle.primary,row=4)
 async def nxt(self,i,b):await i.response.edit_message(embed=builder_embed(self.state,2),view=StatPageTwo(self.state))
 @discord.ui.button(label='Cancel',style=discord.ButtonStyle.secondary,row=4)
 async def cancel(self,i,b):await i.response.edit_message(content='Bowler creation cancelled.',embed=None,view=HomeView())
class StatPageTwo(discord.ui.View):
 def __init__(self,state):
  super().__init__(timeout=600);self.state=state
  for row,(key,label) in enumerate((('consistency','Consistency'),('spin','Spin'),('nerves','Nerves'))):self.add_item(StatSelect(state,key,label,row))
  self.create.disabled=state.remaining<0 or state.used==0
 @discord.ui.button(label='Back',emoji='⬅️',style=discord.ButtonStyle.secondary,row=3)
 async def back(self,i,b):await i.response.edit_message(embed=builder_embed(self.state,1),view=StatPageOne(self.state))
 @discord.ui.button(label='Create Bowler',emoji='✅',style=discord.ButtonStyle.success,row=3)
 async def create(self,i,b):
  from models.bowler import Bowler
  from services.roster import create_bowler
  from config import DEFAULT_STAT_BUDGET
  if self.state.used>DEFAULT_STAT_BUDGET:return await i.response.send_message('Stat budget exceeded.',ephemeral=True)
  if get_bowler_by_owner(i.user.id):return await i.response.send_message('You already have a linked bowler.',ephemeral=True)
  v=self.state.stats
  try:create_bowler(Bowler(None,self.state.name,i.user.id,self.state.hand,1,v['accuracy'],v['style'],v['flair'],v['consistency'],v['spin'],v['nerves']))
  except Exception as e:return await i.response.send_message(f'Could not create bowler: {e}',ephemeral=True)
  await i.response.edit_message(content=f"🎳 **{self.state.name}** created with **{self.state.used}/{DEFAULT_STAT_BUDGET}** points.",embed=None,view=HomeView())
 @discord.ui.button(label='Cancel',style=discord.ButtonStyle.danger,row=3)
 async def cancel(self,i,b):await i.response.edit_message(content='Bowler creation cancelled.',embed=None,view=HomeView())
class BowlerDashboard(AdminHomeView):
 @discord.ui.button(label='➕ Create Bowler',style=discord.ButtonStyle.success)
 async def create(self,i,b):await i.response.send_modal(BowlerIdentityModal())
 @discord.ui.button(label='📋 Bowler List',style=discord.ButtonStyle.primary)
 async def listing(self,i,b):
  with connect() as c:r=c.execute('SELECT name,owner_id FROM bowlers ORDER BY name').fetchall()
  await i.response.send_message('🎳 **Bowlers**\n'+('\n'.join(f"• {x['name']} — {'Offline' if x['owner_id']==0 else 'Discord linked'}" for x in r) or 'None'),ephemeral=True)
class TeamDashboard(AdminHomeView):
 @discord.ui.button(label='➕ Create Team',style=discord.ButtonStyle.success)
 async def create(self,i,b):await i.response.send_message('Use **/team_create** to create the team; this action will become a modal in the next form pass.',ephemeral=True)
 @discord.ui.button(label='👥 Rosters',style=discord.ButtonStyle.primary)
 async def rosters(self,i,b):
  with connect() as c:r=c.execute('SELECT name FROM teams ORDER BY name').fetchall()
  await i.response.send_message('👥 **Teams**\n'+('\n'.join('• '+x['name'] for x in r) or 'None'),ephemeral=True)
class TournamentDashboard(AdminHomeView):
 @discord.ui.button(label='🏆 Tournament Director',style=discord.ButtonStyle.success)
 async def director(self,i,b):await i.response.send_message('Use **/director** to select/open the live tournament dashboard.',ephemeral=True)
 @discord.ui.button(label='📋 Tournament List',style=discord.ButtonStyle.primary)
 async def listing(self,i,b):
  with connect() as c:r=c.execute('SELECT name,status FROM tournaments ORDER BY id DESC LIMIT 20').fetchall()
  await i.response.send_message('🏆 **Tournaments**\n'+('\n'.join(f"• {x['name']} — {x['status']}" for x in r) or 'None'),ephemeral=True)
class MatchDashboard(AdminHomeView):
 @discord.ui.button(label='🎳 Start Match',style=discord.ButtonStyle.success)
 async def start(self,i,b):await i.response.send_message('Use **/game_start** for an exhibition, or **Tournament Director** for tournament matches.',ephemeral=True)
 @discord.ui.button(label='📺 Lane View',style=discord.ButtonStyle.primary)
 async def lane(self,i,b):await i.response.send_message('Use **/lane_view** for the current live lane.',ephemeral=True)
 @discord.ui.button(label='↩️ Undo / Restore',style=discord.ButtonStyle.danger)
 async def recovery(self,i,b):await i.response.send_message('Undo and Restore are available inside **Tournament Director**.',ephemeral=True)
class RecordsDashboard(AdminHomeView):
 @discord.ui.button(label='🏛️ Hall of Fame',style=discord.ButtonStyle.primary)
 async def hof(self,i,b):await i.response.send_message('Use **/hall_of_fame**.',ephemeral=True)
 @discord.ui.button(label='🏅 Awards',style=discord.ButtonStyle.primary)
 async def awards(self,i,b):await i.response.send_message('Use **/awards** or **/award_give**.',ephemeral=True)
 @discord.ui.button(label='🧠 Simulation Lab',style=discord.ButtonStyle.success)
 async def sim(self,i,b):await i.response.send_message('Use **/simulation_lab** for 1,000–100,000-game balance tests.',ephemeral=True)
class SettingsDashboard(AdminHomeView):
 @discord.ui.button(label='🔊 Join Voice',style=discord.ButtonStyle.primary)
 async def voice(self,i,b):await i.response.send_message('Use **/audio_join** to connect to your voice channel.',ephemeral=True)
 @discord.ui.button(label='🎥 Media Setup',style=discord.ButtonStyle.primary)
 async def media(self,i,b):await i.response.send_message('GIFs: **assets/media.json**\nAudio: **assets/audio.json**',ephemeral=True)
class AdminMenu(HomeView):
 def __init__(self):super().__init__()
 async def gate(self,i):
  if not admin_ok(i):await i.response.send_message('Admin/Manage Server permission required.',ephemeral=True);return False
  return True
 @discord.ui.button(label='🎳 Bowler Management',style=discord.ButtonStyle.primary)
 async def bowlers(self,i,b):
  if await self.gate(i):await swap(i,'🎳 **Bowler Management**',BowlerDashboard())
 @discord.ui.button(label='👥 Team Management',style=discord.ButtonStyle.primary)
 async def teams(self,i,b):
  if await self.gate(i):await swap(i,'👥 **Team Management**',TeamDashboard())
 @discord.ui.button(label='🏆 Tournament Control',style=discord.ButtonStyle.primary)
 async def tournaments(self,i,b):
  if await self.gate(i):await swap(i,'🏆 **Tournament Control**',TournamentDashboard())
 @discord.ui.button(label='🎮 Match Control',style=discord.ButtonStyle.success)
 async def match(self,i,b):
  if await self.gate(i):await swap(i,'🎮 **Match Control**',MatchDashboard())
 @discord.ui.button(label='📊 Records & Awards',style=discord.ButtonStyle.secondary)
 async def records(self,i,b):
  if await self.gate(i):await swap(i,'📊 **Records & Awards**',RecordsDashboard())
 @discord.ui.button(label='⚙️ Bot Settings',style=discord.ButtonStyle.secondary)
 async def settings(self,i,b):
  if await self.gate(i):await swap(i,'⚙️ **Bot Settings**',SettingsDashboard())
class BallSelect(discord.ui.Select):
 def __init__(self,bowler_id):
  self.bowler_id=bowler_id;super().__init__(placeholder='Choose primary strike ball',options=[discord.SelectOption(label=v.name,value=k,description=f'Hook {v.hook:.2f} • Length {v.length:.2f} • Control {v.control:.2f}') for k,v in BALLS.items()])
 async def callback(self,i):set_bowler_ball(self.bowler_id,self.values[0]);await i.response.send_message(f'🎳 Primary ball set to **{BALLS[self.values[0]].name}**. Spares use Plastic automatically.',ephemeral=True)
class ArsenalView(HomeView):
 def __init__(self,bowler_id):super().__init__();self.add_item(BallSelect(bowler_id))
class PublicMenu(discord.ui.View):
 def __init__(self):super().__init__(timeout=None)
 @discord.ui.button(label='Create Bowler',emoji='➕',style=discord.ButtonStyle.success,custom_id='gs:create')
 async def create(self,i,b):
  if get_bowler_by_owner(i.user.id):return await i.response.send_message('You already have a linked bowler.',ephemeral=True)
  await i.response.send_modal(BowlerIdentityModal())
 @discord.ui.button(label='My Bowler',emoji='🎳',style=discord.ButtonStyle.primary,custom_id='gs:mybowler')
 async def mine(self,i,b):
  x=get_bowler_by_owner(i.user.id)
  if not x:return await i.response.send_message('You do not have a linked bowler yet — use **Create Bowler**.',ephemeral=True)
  await i.response.send_message(embed=bowler_embed(x),view=HomeView(),ephemeral=True)
 @discord.ui.button(label='My Stats',emoji='📊',style=discord.ButtonStyle.secondary,custom_id='gs:mystats')
 async def stats(self,i,b):
  x=get_bowler_by_owner(i.user.id)
  if not x:return await i.response.send_message('Create a bowler first.',ephemeral=True)
  with connect() as c:s=c.execute('SELECT * FROM bowler_stats WHERE bowler_id=?',(x.id,)).fetchone()
  await i.response.send_message(f"📊 **{x.name}** — Games {s['games'] if s else 0} • High {s['high_game'] if s else 0}",view=HomeView(),ephemeral=True)
 @discord.ui.button(label='Achievements',emoji='🏅',style=discord.ButtonStyle.secondary,custom_id='gs:achievements')
 async def achievements(self,i,b):
  x=get_bowler_by_owner(i.user.id)
  if not x:return await i.response.send_message('Create a bowler first.',ephemeral=True)
  with connect() as c:r=c.execute('SELECT title FROM achievements WHERE bowler_id=? ORDER BY earned_at',(x.id,)).fetchall()
  await i.response.send_message('🏅 **Achievements**\n'+('\n'.join('• '+a['title'] for a in r) or 'None yet.'),view=HomeView(),ephemeral=True)
 @discord.ui.button(label='My Arsenal',emoji='🎯',style=discord.ButtonStyle.secondary,custom_id='gs:arsenal')
 async def arsenal(self,i,b):
  x=get_bowler_by_owner(i.user.id)
  if not x:return await i.response.send_message('Create a bowler first.',ephemeral=True)
  load=bowler_loadout(x.id);await i.response.send_message(f"🎯 **{x.name}'s Arsenal**\nPrimary: **{BALLS[load.get('primary_ball','hybrid')].name}**",view=ArsenalView(x.id),ephemeral=True)
 @discord.ui.button(label='Browse Bowlers',emoji='👀',style=discord.ButtonStyle.secondary,custom_id='gs:browse')
 async def browse(self,i,b):await i.response.send_message('🎳 **Bowlers**\n'+('\n'.join('• '+x['name'] for x in list_bowlers()) or 'None'),view=HomeView(),ephemeral=True)
 @discord.ui.button(label='Admin Control',emoji='🛠️',style=discord.ButtonStyle.danger,custom_id='gs:admin')
 async def admin(self,i,b):
  if not admin_ok(i):return await i.response.send_message('Admin/Manage Server permission required.',ephemeral=True)
  await swap(i,'🛠️ **Gutter Saints Admin Control**',AdminMenu())
class Menu(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='menu',description='Open the Gutter Saints main menu')
 async def menu(self,i:discord.Interaction):await i.response.send_message('🎳 **THE GUTTER SAINTS**\nBowling, careers, achievements and tournament control.',view=PublicMenu(),ephemeral=True)
async def setup(bot):await bot.add_cog(Menu(bot))
