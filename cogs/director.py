import discord
from discord import app_commands
from discord.ext import commands
from services.v25 import tournament_dashboard,backup_database,undo_snapshot,restore_session,export_tournament_xlsx
from services.state import SESSIONS
class DirectorView(discord.ui.View):
 def __init__(self,name):super().__init__(timeout=600);self.name=name
 @discord.ui.button(label='Undo Last Ball',style=discord.ButtonStyle.danger)
 async def undo(self,i,b):
  s=undo_snapshot(i.channel_id)
  if not s:return await i.response.send_message('No earlier snapshot.',ephemeral=True)
  SESSIONS[i.channel_id]=s;await i.response.send_message('↩️ Last ball restored.',ephemeral=True)
 @discord.ui.button(label='Restore Match',style=discord.ButtonStyle.primary)
 async def restore(self,i,b):
  s=restore_session(i.channel_id)
  if not s:return await i.response.send_message('No saved active match.',ephemeral=True)
  SESSIONS[i.channel_id]=s;await i.response.send_message('♻️ Match restored.',ephemeral=True)
 @discord.ui.button(label='Export XLSX',style=discord.ButtonStyle.secondary)
 async def export(self,i,b):
  p=export_tournament_xlsx(self.name)
  if not p:return await i.response.send_message('Nothing to export.',ephemeral=True)
  await i.response.send_message(file=discord.File(p))
class Director(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='director',description='Open Tournament Director')
 @app_commands.default_permissions(manage_guild=True)
 async def director(self,i:discord.Interaction,tournament:str|None=None):
  d=tournament_dashboard(tournament)
  if not d:return await i.response.send_message('No active tournament.',ephemeral=True)
  t,matches,nxt,leaders=d;done=sum(x['status']=='complete' for x in matches);desc=f"Status **{t['status']}** • Completed **{done}/{len(matches)}**\n"
  if nxt:desc+=f"Next: **R{nxt['round_no']} M{nxt['match_no']} — {nxt['team_a']} vs {nxt['team_b']}**\n"
  if leaders:desc+='\n**Leaders**\n'+'\n'.join(f"{x['name']} — {x['avg']:.1f}" for x in leaders)
  await i.response.send_message(embed=discord.Embed(title=f"🏆 Tournament Director — {t['name']}",description=desc),view=DirectorView(t['name']))
async def setup(bot):await bot.add_cog(Director(bot))
