import discord
from discord import app_commands
from discord.ext import commands
from models.bowler import Bowler
from services.roster import create_bowler,get_bowler,list_bowlers
from ui.embeds import bowler_embed
from config import DEFAULT_STAT_BUDGET
class Bowlers(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='bowler_create',description='Create a Gutter Saints bowler')
 async def create(self,interaction:discord.Interaction,name:str,rank:app_commands.Range[int,0,50],accuracy:app_commands.Range[int,0,50],style:app_commands.Range[int,0,50],flair:app_commands.Range[int,0,50],consistency:app_commands.Range[int,0,50],spin:app_commands.Range[int,0,50],nerves:app_commands.Range[int,0,50],handedness:str='R'):
  vals=[rank,accuracy,style,flair,consistency,spin,nerves]
  if sum(vals)>DEFAULT_STAT_BUDGET:return await interaction.response.send_message(f'Stat total is {sum(vals)}; maximum is {DEFAULT_STAT_BUDGET}.',ephemeral=True)
  b=Bowler(None,name,interaction.user.id,handedness.upper()[0],rank,accuracy,style,flair,consistency,spin,nerves)
  try:create_bowler(b)
  except Exception as ex:return await interaction.response.send_message(f'Could not create bowler: {ex}',ephemeral=True)
  await interaction.response.send_message(embed=bowler_embed(get_bowler(name)))
 @app_commands.command(name='bowler_show')
 async def show(self,interaction:discord.Interaction,name:str):
  b=get_bowler(name)
  if not b:return await interaction.response.send_message('Bowler not found.',ephemeral=True)
  await interaction.response.send_message(embed=bowler_embed(b))
 @app_commands.command(name='bowler_list')
 async def ls(self,interaction:discord.Interaction):
  rows=list_bowlers(); text='🎳 **Bowlers**\n'+('\n'.join(f"• {r['name']}" for r in rows) or 'None yet.')
  await interaction.response.send_message(text)
async def setup(bot):await bot.add_cog(Bowlers(bot))
