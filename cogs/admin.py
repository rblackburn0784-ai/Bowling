import statistics,discord
from discord import app_commands
from discord.ext import commands
from services.roster import get_bowler
from services.game_engine import GameSession
class Admin(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='rngtest',description='Admin simulation test for a bowler')
 @app_commands.checks.has_permissions(administrator=True)
 async def rngtest(self,i:discord.Interaction,bowler:str,games:app_commands.Range[int,10,2000]=200):
  await i.response.defer(ephemeral=True);b=get_bowler(bowler)
  if not b:return await i.followup.send('Bowler not found.',ephemeral=True)
  scores=[]
  for x in range(games):
   s=GameSession([b],seed=x+10001)
   while not s.complete:s.bowl()
   scores.append(s.scores()[b.name])
  text=(f'🎲 **{bowler} RNG test** ({games} games)\nMean: **{statistics.mean(scores):.1f}**\nMedian: **{statistics.median(scores):.1f}**\nLow/High: **{min(scores)} / {max(scores)}**\nSD: **{statistics.pstdev(scores):.1f}**')
  await i.followup.send(text,ephemeral=True)
async def setup(bot):await bot.add_cog(Admin(bot))
