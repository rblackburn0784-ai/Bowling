import discord
from discord import app_commands
from discord.ext import commands
from storage.database import connect
from services.v25 import archetype,head_to_head
from services.roster import get_bowler
class Features(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='progression',description='Show bowler XP and upgrade credits')
 async def progression(self,i:discord.Interaction,bowler:str):
  b=get_bowler(bowler)
  if not b:return await i.response.send_message('Bowler not found.',ephemeral=True)
  with connect() as c:r=c.execute('SELECT * FROM bowler_progression WHERE bowler_id=?',(b.id,)).fetchone()
  await i.response.send_message(f"🎳 **{b.name}** — {archetype(b)}\nXP **{r['xp'] if r else 0}** • Credits **{r['credits'] if r else 0}**")
 @app_commands.command(name='hall_of_fame',description='Show career records')
 async def hof(self,i:discord.Interaction):
  with connect() as c:r=c.execute('SELECT b.name,s.games,s.total_pins,s.high_game,s.perfect_games FROM bowler_stats s JOIN bowlers b ON b.id=s.bowler_id WHERE s.games>0 ORDER BY s.high_game DESC LIMIT 10').fetchall()
  await i.response.send_message('🏛️ **Hall of Fame**\n'+('\n'.join(f"• {x['name']} — HG {x['high_game']} • 300s {x['perfect_games']}" for x in r) or 'No records yet.'))
 @app_commands.command(name='head_to_head',description='Show team rivalry history')
 async def h2h(self,i:discord.Interaction,team_a:str,team_b:str):
  r=head_to_head(team_a,team_b)
  await i.response.send_message(f'⚔️ **{team_a} vs {team_b}** — {len(r) if r else 0} recorded meetings.')
async def setup(bot):await bot.add_cog(Features(bot))
