import discord
from discord import app_commands
from discord.ext import commands
from storage.database import connect,career_row,tournament_leaders,ensure_v22_schema
class Stats(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='leaderboard',description='Career average leaderboard')
 async def leaderboard(self,i:discord.Interaction):
  ensure_v22_schema()
  with connect() as c:r=c.execute("SELECT b.name,s.* FROM bowler_stats s JOIN bowlers b ON b.id=s.bowler_id WHERE games>0 ORDER BY total_pins*1.0/games DESC LIMIT 20").fetchall()
  lines=[f"**{n}. {x['name']}** — Avg {x['total_pins']/x['games']:.1f} • HG {x['high_game']} • 300s {x['perfect_games']}" for n,x in enumerate(r,1)];await i.response.send_message('🏆 **Career Leaderboard**\n'+('\n'.join(lines) or 'No completed games yet.'))
 @app_commands.command(name='career',description='Show a bowler’s full career card')
 async def career(self,i:discord.Interaction,bowler:str):
  x=career_row(bowler)
  if not x or x['games'] is None:return await i.response.send_message('No career stats found.',ephemeral=True)
  e=discord.Embed(title=f"🎳 Career — {x['name']}",description=f"**{x['games']} games • {x['avg']:.2f} average • {x['high_game']} high game**");e.add_field(name='Scoring',value=f"Strikes **{x['strikes']}**\nSpares **{x['spares']}**\nTurkeys **{x['turkeys']}**\nClean games **{x['clean_games']}**");e.add_field(name='Milestones',value=f"200+ **{x['games_200']}**\n250+ **{x['games_250']}**\n300 **{x['perfect_games']}**\nAwards **{x['awards']}**");await i.response.send_message(embed=e)
 @app_commands.command(name='tournament_leaders',description='Tournament MVP/high-game table')
 async def tleaders(self,i:discord.Interaction,tournament:str):
  t,rows=tournament_leaders(tournament)
  if not t:return await i.response.send_message('Tournament not found.',ephemeral=True)
  lines=[f"**{n}. {x['name']}** — Avg {x['avg']:.1f} • HG {x['high_game']}" for n,x in enumerate(rows[:15],1)];await i.response.send_message(f"🏆 **{t['name']} — Tournament Leaders**\n"+('\n'.join(lines) or 'No recorded games yet.'))
async def setup(bot):await bot.add_cog(Stats(bot))
