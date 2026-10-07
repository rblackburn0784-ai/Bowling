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
class BowlerCreateModal(discord.ui.Modal,title='Create Bowler'):
 name=discord.ui.TextInput(label='Bowler name',max_length=32)
 handedness=discord.ui.TextInput(label='Handedness',placeholder='R or L',default='R',max_length=1)
 stats=discord.ui.TextInput(label='Stats: rank,accuracy,style,flair,consistency,spin,nerves',placeholder='20,20,10,10,20,10,10')
 async def on_submit(self,i):
  from models.bowler import Bowler
  from services.roster import create_bowler,get_bowler_by_owner
  from config import DEFAULT_STAT_BUDGET
  if get_bowler_by_owner(i.user.id):return await i.response.send_message('You already have a linked bowler.',ephemeral=True)
  try:vals=[int(x.strip()) for x in self.stats.value.split(',')]
  except:return await i.response.send_message('Enter seven numbers separated by commas.',ephemeral=True)
  if len(vals)!=7 or any(x<0 or x>50 for x in vals):return await i.response.send_message('Each of the seven stats must be 0–50.',ephemeral=True)
  if sum(vals)>DEFAULT_STAT_BUDGET:return await i.response.send_message(f'Stat total {sum(vals)} exceeds the {DEFAULT_STAT_BUDGET} budget.',ephemeral=True)
  try:create_bowler(Bowler(None,self.name.value,i.user.id,self.handedness.value.upper()[0],*vals))
  except Exception as e:return await i.response.send_message(f'Could not create bowler: {e}',ephemeral=True)
  await i.response.send_message(f'🎳 **{self.name.value}** created.',ephemeral=True)
class BowlerDashboard(AdminHomeView):
 @discord.ui.button(label='➕ Create Bowler',style=discord.ButtonStyle.success)
 async def create(self,i,b):await i.response.send_modal(BowlerCreateModal())
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
  await i.response.send_modal(BowlerCreateModal())
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
