import asyncio,discord
from discord import app_commands
from discord.ext import commands
from storage.database import connect
from models.bowler import Bowler
from services.simulation_lab import SimProfile,compare,dominance_flags,export_csv
def profiles(kind,b):
 if kind=='rank':return [SimProfile('Rank 20',20,b.accuracy,b.style,b.flair,b.consistency,b.spin,b.nerves,b.handedness),SimProfile('Rank 30',30,b.accuracy,b.style,b.flair,b.consistency,b.spin,b.nerves,b.handedness)]
 if kind=='accuracy_spin':return [SimProfile('Accuracy Build',b.rank,40,b.style,b.flair,b.consistency,10,b.nerves,b.handedness),SimProfile('Spin Build',b.rank,10,b.style,b.flair,b.consistency,40,b.nerves,b.handedness)]
 if kind=='handedness':return [SimProfile('Right Hand',b.rank,b.accuracy,b.style,b.flair,b.consistency,b.spin,b.nerves,'R'),SimProfile('Left Hand',b.rank,b.accuracy,b.style,b.flair,b.consistency,b.spin,b.nerves,'L')]
 return [SimProfile('Low Nerves',b.rank,b.accuracy,b.style,b.flair,b.consistency,b.spin,5,b.handedness),SimProfile('High Nerves',b.rank,b.accuracy,b.style,b.flair,b.consistency,b.spin,45,b.handedness)]
class SimulationLab(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='simulation_lab',description='Run headless bowling balance simulations')
 @app_commands.default_permissions(manage_guild=True)
 @app_commands.choices(test=[app_commands.Choice(name='Rank 20 vs 30',value='rank'),app_commands.Choice(name='Accuracy vs Spin',value='accuracy_spin'),app_commands.Choice(name='Right vs Left Handed',value='handedness'),app_commands.Choice(name='Low vs High Nerves',value='nerves')],lane=[app_commands.Choice(name=x.title(),value=x) for x in ['house','fresh','oily','dry','transition']],burn=[app_commands.Choice(name='Fresh',value=0),app_commands.Choice(name='Transitioned',value=35),app_commands.Choice(name='Burnt',value=70)])
 async def lab(self,i:discord.Interaction,bowler:str,games:app_commands.Range[int,1000,100000]=10000,test:app_commands.Choice[str]|None=None,lane:app_commands.Choice[str]|None=None,burn:app_commands.Choice[int]|None=None,export:bool=False):
  with connect() as c:r=c.execute('SELECT * FROM bowlers WHERE name=? COLLATE NOCASE',(bowler,)).fetchone()
  if not r:return await i.response.send_message('Bowler not found.',ephemeral=True)
  b=Bowler(**{k:r[k] for k in ['id','name','owner_id','handedness','rank','accuracy','style','flair','consistency','spin','nerves']});kind=test.value if test else 'rank';ln=lane.value if lane else 'house';bn=(burn.value if burn else 0)/100
  await i.response.defer(ephemeral=True,thinking=True);rows=await asyncio.to_thread(compare,profiles(kind,b),games,ln,bn,7275)
  lines=['```','Bowler             Avg   +/-95 Strike Spare  200+  250+    300']
  for x in rows:lines.append(f"{x['name'][:17]:17} {x['avg']:5.1f} {x['ci95']:5.2f} {x['strike_pct']:5.1f}% {x['spare_pct']:5.1f}% {x['p200']:5.1f}% {x['p250']:5.1f}% {x['p300']:6.3f}%")
  lines.append('```');flags=dominance_flags(rows);content=f"🧠 **SIMULATION LAB** — {games:,} games/build • {ln.title()} • burn {int(bn*100)}%\n"+'\n'.join(lines)+'\n'+(('⚠️ '+'\n⚠️ '.join(flags)) if flags else '✅ No automatic dominance thresholds triggered.')
  file=discord.File(export_csv(rows,f'{kind}_{ln}')) if export else None;await i.followup.send(content,file=file,ephemeral=True)
async def setup(bot):await bot.add_cog(SimulationLab(bot))
