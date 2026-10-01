import discord
from discord import app_commands
from discord.ext import commands
from services.competition import create_tournament,add_entry,start_tournament,report_match,bracket
from services.media import pick
from ui.embeds import bracket_embed

class Tournaments(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.default_permissions(manage_guild=True)
 @app_commands.command(name='tournament_create',description='Create a single-elimination tournament')
 @app_commands.choices(lane=[app_commands.Choice(name=x.title(),value=x) for x in ['house','fresh','dry','oily','transition']])
 async def create(self,i:discord.Interaction,name:str,lane:app_commands.Choice[str]|None=None):
  try:create_tournament(name,lane.value if lane else 'house');await i.response.send_message(f'🏆 **{name}** created. Registration is open.')
  except Exception as e:await i.response.send_message(f'Could not create tournament: {e}',ephemeral=True)
 @app_commands.default_permissions(manage_guild=True)
 @app_commands.command(name='tournament_enter',description='Enter a team')
 async def enter(self,i:discord.Interaction,tournament:str,team:str,seed:int|None=None):
  ok=add_entry(tournament,team,seed);await i.response.send_message(f'✅ **{team}** entered **{tournament}**.' if ok else 'Tournament/team not found or registration is closed.',ephemeral=not ok)
 @app_commands.default_permissions(manage_guild=True)
 @app_commands.command(name='tournament_start',description='Close registration and build the bracket')
 async def start(self,i:discord.Interaction,tournament:str):
  tid,err=start_tournament(tournament)
  if err:return await i.response.send_message(err,ephemeral=True)
  t,rows=bracket(tournament);await i.response.send_message('📣 **THE BRACKET IS SET!**',embed=bracket_embed(t,rows));u=pick('tournament');
  if u:await i.channel.send(u)
 @app_commands.default_permissions(manage_guild=True)
 @app_commands.command(name='tournament_bracket',description='Show the live tournament bracket')
 async def show(self,i:discord.Interaction,tournament:str):
  t,rows=bracket(tournament)
  if not t:return await i.response.send_message('Tournament not found.',ephemeral=True)
  await i.response.send_message(embed=bracket_embed(t,rows))
 @app_commands.default_permissions(manage_guild=True)
 @app_commands.command(name='tournament_result',description='Report a completed team match and advance the winner')
 async def result(self,i:discord.Interaction,tournament:str,round_no:int,match_no:int,team_a_score:int,team_b_score:int):
  ok,err=report_match(tournament,round_no,match_no,team_a_score,team_b_score)
  if not ok:return await i.response.send_message(err,ephemeral=True)
  t,rows=bracket(tournament);await i.response.send_message('📣 **RESULT CONFIRMED — THE BRACKET MOVES ON!**',embed=bracket_embed(t,rows))
async def setup(bot):await bot.add_cog(Tournaments(bot))
