import discord
from discord import app_commands
from discord.ext import commands
from services.competition import create_series
from storage.database import connect

class Series(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='series_create',description='Create a best-of team series')
 async def create(self,i:discord.Interaction,name:str,team_a:str,team_b:str,best_of:app_commands.Range[int,1,9]=3):
  if best_of%2==0:return await i.response.send_message('Best-of must be an odd number.',ephemeral=True)
  try:sid=create_series(name,team_a,team_b,best_of)
  except Exception as e:return await i.response.send_message(f'Could not create series: {e}',ephemeral=True)
  await i.response.send_message(f'🎳 **{name}** — {team_a} vs {team_b}, best of {best_of}.') if sid else await i.response.send_message('Team not found.',ephemeral=True)
 @app_commands.command(name='series_result',description='Add one game result to a series')
 async def result(self,i:discord.Interaction,name:str,team_a_score:int,team_b_score:int):
  if team_a_score==team_b_score:return await i.response.send_message('Series games cannot end tied.',ephemeral=True)
  with connect() as c:
   s=c.execute('''SELECT s.*,a.name a,b.name b FROM series s JOIN teams a ON a.id=s.team_a_id JOIN teams b ON b.id=s.team_b_id WHERE s.name=? COLLATE NOCASE AND s.status='active' ORDER BY s.id DESC LIMIT 1''',(name,)).fetchone()
   if not s:return await i.response.send_message('Active series not found.',ephemeral=True)
   aw=s['team_a_wins']+(team_a_score>team_b_score);bw=s['team_b_wins']+(team_b_score>team_a_score);need=s['best_of']//2+1;done=aw>=need or bw>=need
   c.execute("UPDATE series SET team_a_wins=?,team_b_wins=?,status=?,finished_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE finished_at END WHERE id=?",(aw,bw,'complete' if done else 'active',done,s['id']))
  text=f"📊 **{name}: {s['a']} {aw}–{bw} {s['b']}**"
  if done:text+=f"\n🏆 **{s['a'] if aw>bw else s['b']} wins the series!**"
  await i.response.send_message(text)
async def setup(bot):await bot.add_cog(Series(bot))
