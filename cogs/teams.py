import discord
from discord import app_commands
from discord.ext import commands
from services.roster import create_team,add_team_member,team_roster
class Teams(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.default_permissions(manage_guild=True)
 @app_commands.command(name='team_create')
 async def create(self,i:discord.Interaction,name:str,flair:app_commands.Range[int,0,50]=0):
  try:create_team(name,i.user.id,flair);await i.response.send_message(f'🎳 Team **{name}** created.')
  except Exception as e:await i.response.send_message(f'Could not create team: {e}',ephemeral=True)
 @app_commands.default_permissions(manage_guild=True)
 @app_commands.command(name='team_add')
 async def add(self,i:discord.Interaction,team:str,bowler:str,slot:app_commands.Range[int,1,5]):
  ok=add_team_member(team,bowler,slot);await i.response.send_message('Added.' if ok else 'Team or bowler not found.',ephemeral=not ok)
 @app_commands.default_permissions(manage_guild=True)
 @app_commands.command(name='team_roster')
 async def roster(self,i:discord.Interaction,team:str):
  r=team_roster(team); text=f"**{team}**\n"+'\n'.join(f"{x['slot']}. {x['name']}" for x in r)
  await i.response.send_message(text)
async def setup(bot):await bot.add_cog(Teams(bot))
