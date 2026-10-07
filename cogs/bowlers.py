import discord
from discord import app_commands
from discord.ext import commands
from services.roster import get_bowler,list_bowlers
from ui.embeds import bowler_embed

class Bowlers(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='bowler_create',description='Open the guided rookie bowler builder')
 async def create(self,interaction:discord.Interaction):
  from services.roster import get_bowler_by_owner
  from cogs.menu import BowlerIdentityModal
  if get_bowler_by_owner(interaction.user.id):return await interaction.response.send_message('You already have a linked bowler.',ephemeral=True)
  await interaction.response.send_modal(BowlerIdentityModal())
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
