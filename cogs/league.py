import discord
from discord import app_commands
from discord.ext import commands
from storage.database import connect
from services.league_engine import create_season,create_competition,transition,register,generate_schedule,standings,season_leaders,competition

FORMATS=[app_commands.Choice(name=n,value=v) for n,v in [('Single Elimination','single_elimination'),('Double Elimination','double_elimination'),('Round Robin','round_robin'),('Groups to Knockout','groups_knockout'),('Stepladder','stepladder'),('Best-of-X','best_of'),('Qualifying','qualifying')]]
class League(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.default_permissions(manage_guild=True)
 @app_commands.command(name='season_create_v2',description='Create a persistent Gutter Saints season')
 async def season_create(self,i:discord.Interaction,name:str):
  try:sid=create_season(name);await i.response.send_message(f'📅 **{name}** created in **Draft** state. Season ID {sid}.')
  except Exception as e:await i.response.send_message(f'Could not create season: {e}',ephemeral=True)
 @app_commands.default_permissions(manage_guild=True)
 @app_commands.command(name='competition_create',description='Create a league, tournament or championship')
 @app_commands.choices(format=FORMATS,entrant_type=[app_commands.Choice(name='Teams',value='team'),app_commands.Choice(name='Individuals',value='individual')])
 async def competition_create(self,i:discord.Interaction,name:str,format:app_commands.Choice[str],entrant_type:app_commands.Choice[str],season_id:int|None=None):
  try:create_competition(name,season_id,'league' if format.value=='round_robin' else 'tournament',format.value,entrant_type.value);await i.response.send_message(f'🏆 **{name}** created • {format.name} • {entrant_type.name} • **Draft**.')
  except Exception as e:await i.response.send_message(f'Could not create competition: {e}',ephemeral=True)
 @app_commands.default_permissions(manage_guild=True)
 @app_commands.command(name='competition_state',description='Advance a competition to its next controlled state')
 @app_commands.choices(state=[app_commands.Choice(name=x.title(),value=x) for x in ('registration','locked','active','completed','archived')])
 async def state(self,i:discord.Interaction,name:str,state:app_commands.Choice[str]):
  x=competition(name)
  if not x:return await i.response.send_message('Competition not found.',ephemeral=True)
  ok,err=transition(x['id'],state.value)
  if ok and state.value=='locked':ok,err=generate_schedule(x['id'])
  await i.response.send_message(f"✅ **{name}** → **{state.name}**." if ok else f'❌ {err}',ephemeral=not ok)
 @app_commands.default_permissions(manage_guild=True)
 @app_commands.command(name='competition_enter',description='Register a team or bowler by database ID')
 async def enter(self,i:discord.Interaction,name:str,entrant_id:int,seed:int|None=None,group:str|None=None):
  x=competition(name);ok=bool(x and register(x['id'],entrant_id,seed,group));await i.response.send_message('✅ Entrant registered.' if ok else 'Registration failed; competition must be in Registration state.',ephemeral=not ok)
 @app_commands.command(name='league_table',description='Show current competition standings')
 async def table(self,i:discord.Interaction,name:str):
  x=competition(name)
  if not x:return await i.response.send_message('Competition not found.',ephemeral=True)
  rs=standings(x['id']);lines=[f"**{n}. {r['name']}** — {r['points']} pts • {r['wins']}-{r['draws']}-{r['losses']} • Δ {r['differential']:+}" for n,r in enumerate(rs,1)]
  await i.response.send_message(embed=discord.Embed(title=f"📊 {x['name']} — Standings",description='\n'.join(lines) or 'No standings yet.'))
 @app_commands.command(name='season_dashboard',description='Show a persistent season dashboard')
 async def dashboard(self,i:discord.Interaction,season_id:int):
  with connect() as c:
   s=c.execute('SELECT * FROM seasons WHERE id=?',(season_id,)).fetchone();comps=c.execute('SELECT * FROM competitions WHERE season_id=? ORDER BY id',(season_id,)).fetchall()
   nxt=c.execute("""SELECT f.*,co.name competition,a.name home,b.name away FROM fixtures f JOIN competitions co ON co.id=f.competition_id LEFT JOIN teams a ON a.id=f.home_id LEFT JOIN teams b ON b.id=f.away_id WHERE co.season_id=? AND f.status='scheduled' ORDER BY f.id LIMIT 4""",(season_id,)).fetchall()
  if not s:return await i.response.send_message('Season not found.',ephemeral=True)
  leaders=season_leaders(season_id);desc=f"State **{s['status'].title()}**\nCompetitions: **{len(comps)}**"
  if nxt:desc+='\n\n**Next Fixtures**\n'+'\n'.join(f"{r['home'] or 'TBD'} vs {r['away'] or 'TBD'} — {r['competition']}" for r in nxt)
  if leaders:
   avg=max(leaders,key=lambda r:r['average'] or 0);hg=max(leaders,key=lambda r:r['high_game']);st=max(leaders,key=lambda r:r['strikes']);sp=max(leaders,key=lambda r:r['split_conversions'])
   desc+=f"\n\n**Season Leaders**\nAverage — {avg['name']} {avg['average']:.1f}\nHigh Game — {hg['name']} {hg['high_game']}\nStrikes — {st['name']} {st['strikes']}\nSplits Converted — {sp['name']} {sp['split_conversions']}"
  await i.response.send_message(embed=discord.Embed(title=f"🎳 Gutter Saints — {s['name']}",description=desc))
async def setup(bot):await bot.add_cog(League(bot))
