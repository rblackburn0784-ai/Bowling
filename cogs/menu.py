import discord
from discord import app_commands
from discord.ext import commands
from services.roster import get_bowler_by_owner,list_bowlers
from storage.database import connect
from ui.embeds import bowler_embed

def admin_ok(i):return bool(i.user.guild_permissions.administrator or i.user.guild_permissions.manage_guild)
class AdminMenu(discord.ui.View):
 def __init__(self):super().__init__(timeout=300)
 async def gate(self,i):
  if not admin_ok(i):await i.response.send_message('Admin/Manage Server permission required.',ephemeral=True);return False
  return True
 @discord.ui.button(label='🎳 Bowler Management',style=discord.ButtonStyle.primary)
 async def bowlers(self,i,b):
  if not await self.gate(i):return
  with connect() as c:r=c.execute('SELECT name,owner_id FROM bowlers ORDER BY name').fetchall()
  await i.response.send_message('🎳 **Bowler Management**\n'+('\n'.join(f"• {x['name']} — {'Offline' if x['owner_id']==0 else 'Discord linked'}" for x in r) or 'None'),ephemeral=True)
 @discord.ui.button(label='👥 Team Management',style=discord.ButtonStyle.primary)
 async def teams(self,i,b):
  if not await self.gate(i):return
  with connect() as c:r=c.execute('SELECT name FROM teams ORDER BY name').fetchall()
  await i.response.send_message('👥 **Team Management**\n'+('\n'.join('• '+x['name'] for x in r) or 'None')+'\nUse `/team_create`, `/team_add`, `/team_roster`.',ephemeral=True)
 @discord.ui.button(label='🏆 Tournament Control',style=discord.ButtonStyle.primary)
 async def tournaments(self,i,b):
  if not await self.gate(i):return
  await i.response.send_message('🏆 **Tournament Control**\nUse `/director` for the live Tournament Director dashboard.',ephemeral=True)
 @discord.ui.button(label='🎮 Match Control',style=discord.ButtonStyle.success)
 async def match(self,i,b):
  if not await self.gate(i):return
  await i.response.send_message('🎮 **Match Control**\n`/game_start` • `/game_bowl` • `/game_auto` • `/game_scoreboard` • `/lane_view`',ephemeral=True)
 @discord.ui.button(label='📊 Records & Awards',style=discord.ButtonStyle.secondary)
 async def records(self,i,b):
  if not await self.gate(i):return
  await i.response.send_message('📊 `/leaderboard` • `/career` • `/tournament_leaders` • `/hall_of_fame` • `/awards`',ephemeral=True)
 @discord.ui.button(label='⚙️ Bot Settings',style=discord.ButtonStyle.secondary)
 async def settings(self,i,b):
  if not await self.gate(i):return
  await i.response.send_message('⚙️ **Bot Settings**\nBroadcast media: `assets/media.json`\nAudio: `assets/audio.json`\nVoice: `/audio_join` / `/audio_leave`',ephemeral=True)
class PublicMenu(discord.ui.View):
 def __init__(self):super().__init__(timeout=None)
 @discord.ui.button(label='My Bowler',emoji='🎳',style=discord.ButtonStyle.primary,custom_id='gs:mybowler')
 async def mine(self,i,b):
  x=get_bowler_by_owner(i.user.id);await i.response.send_message(embed=bowler_embed(x) if x else None,content=None if x else 'You do not have a linked bowler yet. Use `/bowler_create`.',ephemeral=True)
 @discord.ui.button(label='My Stats',emoji='📊',style=discord.ButtonStyle.secondary,custom_id='gs:mystats')
 async def stats(self,i,b):
  x=get_bowler_by_owner(i.user.id)
  if not x:return await i.response.send_message('Create a bowler first.',ephemeral=True)
  with connect() as c:s=c.execute('SELECT * FROM bowler_stats WHERE bowler_id=?',(x.id,)).fetchone()
  await i.response.send_message(f"📊 **{x.name}** — Games {s['games'] if s else 0} • High {s['high_game'] if s else 0}",ephemeral=True)
 @discord.ui.button(label='Achievements',emoji='🏅',style=discord.ButtonStyle.secondary,custom_id='gs:achievements')
 async def achievements(self,i,b):
  x=get_bowler_by_owner(i.user.id)
  if not x:return await i.response.send_message('Create a bowler first.',ephemeral=True)
  with connect() as c:r=c.execute('SELECT title FROM achievements WHERE bowler_id=? ORDER BY earned_at',(x.id,)).fetchall()
  await i.response.send_message('🏅 **Achievements**\n'+('\n'.join('• '+a['title'] for a in r) or 'None yet.'),ephemeral=True)
 @discord.ui.button(label='Browse Bowlers',emoji='👀',style=discord.ButtonStyle.secondary,custom_id='gs:browse')
 async def browse(self,i,b):await i.response.send_message('🎳 **Bowlers**\n'+('\n'.join('• '+x['name'] for x in list_bowlers()) or 'None'),ephemeral=True)
 @discord.ui.button(label='Admin Control',emoji='🛠️',style=discord.ButtonStyle.danger,custom_id='gs:admin')
 async def admin(self,i,b):
  if not admin_ok(i):return await i.response.send_message('Admin/Manage Server permission required.',ephemeral=True)
  await i.response.send_message('🛠️ **Gutter Saints Admin Control**',view=AdminMenu(),ephemeral=True)
class Menu(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='menu',description='Open the Gutter Saints main menu')
 async def menu(self,i:discord.Interaction):await i.response.send_message('🎳 **THE GUTTER SAINTS**\nBowling, careers, achievements and tournament control.',view=PublicMenu(),ephemeral=True)
async def setup(bot):await bot.add_cog(Menu(bot))
