import discord
from discord import app_commands
from discord.ext import commands
from storage.database import connect
from services.league_engine import create_season,create_competition,transition,register,generate_schedule,standings,season_leaders,competition,fixture_roster,set_substitute,execute_movements

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

 @app_commands.default_permissions(manage_guild=True)
 @app_commands.command(name='fixture_start',description='Launch a scheduled competition fixture as a live bowling match')
 async def fixture_start(self,i:discord.Interaction,fixture_id:int):
  with connect() as c:f=c.execute('SELECT f.*,co.season_id,co.entrant_type,co.lane_condition,co.state FROM fixtures f JOIN competitions co ON co.id=f.competition_id WHERE f.id=?',(fixture_id,)).fetchone()
  if not f or f['state']!='active' or f['status']!='scheduled':return await i.response.send_message('Fixture is not currently playable.',ephemeral=True)
  home=fixture_roster(fixture_id,f['home_id']);away=fixture_roster(fixture_id,f['away_id'])
  if not home or not away:return await i.response.send_message('Fixture roster is incomplete.',ephemeral=True)
  from cogs.games import rb
  from services.game_engine import GameSession
  from services.state import SESSIONS
  from services.v271 import bowler_loadout
  bowlers=[]
  hn='Home' if f['entrant_type']=='individual' else None;an='Away' if f['entrant_type']=='individual' else None
  if f['entrant_type']=='team':
   with connect() as c2:
    hn=c2.execute('SELECT name FROM teams WHERE id=?',(f['home_id'],)).fetchone()['name'];an=c2.execute('SELECT name FROM teams WHERE id=?',(f['away_id'],)).fetchone()['name']
  for n in range(max(len(home),len(away))):
   if n<len(home):bowlers.append(rb(home[n],hn))
   if n<len(away):bowlers.append(rb(away[n],an))
  s=GameSession(bowlers,lane=f['lane_condition'],season_id=f['season_id'],competition_id=f['competition_id'],fixture_id=fixture_id);SESSIONS[i.channel_id]=s
  for p in s.players:p.ball_key=bowler_loadout(p.bowler.id).get('primary_ball','hybrid')
  with connect() as c:c.execute("UPDATE fixtures SET status='playing' WHERE id=?",(fixture_id,))
  await i.response.send_message(f'🎳 Fixture **#{fixture_id}** is live — **{hn} vs {an}**.')

 @app_commands.default_permissions(manage_guild=True)
 @app_commands.command(name='competition_substitute',description='Mark or unmark a locked team-roster substitute')
 async def substitute(self,i:discord.Interaction,name:str,team_id:int,bowler_id:int,substitute:bool=True):
  x=competition(name);ok=bool(x and set_substitute(x['id'],team_id,bowler_id,substitute));await i.response.send_message('✅ Competition roster updated.' if ok else 'Could not update substitute.',ephemeral=not ok)

 @app_commands.default_permissions(manage_guild=True)
 @app_commands.command(name='competition_movements',description='Execute configured promotion and relegation from final standings')
 async def movements(self,i:discord.Interaction,name:str):
  x=competition(name)
  if not x:return await i.response.send_message('Competition not found.',ephemeral=True)
  moves=execute_movements(x['id']);await i.response.send_message('🔁 **Promotion / Relegation**\n'+('\n'.join(f'• Entrant {eid}: **{move}**' for eid,move in moves) or 'No configured movements.'))

async def setup(bot):await bot.add_cog(League(bot))
