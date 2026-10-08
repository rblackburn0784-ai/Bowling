import discord
from storage.database import connect
from services.league_engine import competition_view,standings,next_fixture,fixture_roster,set_substitute,bowler_competitions
from services.state import SESSIONS
from services.game_engine import GameSession
from services.v271 import bowler_loadout

def _rows(sql,args=()):
 with connect() as c:return c.execute(sql,args).fetchall()
def _opts(rows):
 return [discord.SelectOption(label=x['name'][:100],value=str(x['id'])) for x in rows[:25]]

def competition_embed(cid):
 data=competition_view(cid)
 if not data:return discord.Embed(title='Competition unavailable')
 co,stages,fixtures=data;e=discord.Embed(title=f"🏆 {co['name']}",description=f"**{co['format'].replace('_',' ').title()}** • {co['entrant_type'].title()}\nState **{co['state'].title()}** • Oil **{co['lane_condition'].title()}**")
 nxt=next_fixture(cid)
 if nxt:e.add_field(name='🎮 Next Fixture',value=f"Stage {nxt['stage_id']} • Round {nxt['round_no']} • Fixture #{nxt['id']}",inline=False)
 e.add_field(name='📚 Stages',value='\n'.join(f"{s['stage_no']}. **{s['name']}** — {s['format'].replace('_',' ').title()}" for s in stages) or 'Not generated',inline=False)
 return e

def fixtures_embed(cid):
 co,stages,fs=competition_view(cid);lines=[]
 for f in fs[-20:]:
  score='' if f['home_score'] is None else f" — **{f['home_score']}–{f['away_score']}**"
  lines.append(f"{'✅' if f['status']=='complete' else '🎳' if f['status']=='playing' else '⏳'} R{f['round_no']} • {f['home_name'] or 'BYE'} vs {f['away_name'] or 'BYE'}{score}")
 return discord.Embed(title=f"📅 {co['name']} — Fixtures & Results",description='\n'.join(lines) or 'No fixtures.')

def table_embed(cid):
 co=competition_view(cid)[0];rs=standings(cid);lines=[f"**{n}. {r['name']}** — {r['points']} pts • {r['wins']}-{r['draws']}-{r['losses']} • Δ {r['differential']:+}" for n,r in enumerate(rs,1)]
 return discord.Embed(title=f"📊 {co['name']} — Table",description='\n'.join(lines) or 'No standings.')

def bracket_embed(cid):
 co,stages,fs=competition_view(cid);sections={}
 for f in fs:
  label={'winners':'Winners Bracket','losers':'Losers Bracket','grand_final':'Grand Final / Reset','main':'Bracket'}.get(f['bracket'],f['bracket'].title())
  sections.setdefault(label,[]).append(f)
 e=discord.Embed(title=f"🧩 {co['name']} — Bracket / Stages")
 for label,items in sections.items():
  text='\n'.join(f"R{x['round_no']} #{x['fixture_no']} • **{x['home_name'] or 'BYE'}** vs **{x['away_name'] or 'BYE'}**"+(f" → {x['winner_name']}" if x['winner_name'] else '') for x in items[-12:])
  e.add_field(name=label,value=text[:1024] or 'Pending',inline=False)
 return e

def playoff_embed(cid):
 co=competition_view(cid)[0];rs=standings(cid);cut=co['playoff_size'] or 0;lines=[]
 for n,r in enumerate(rs,1):
  tag='🟢' if cut and n<=cut else '⚪'
  lines.append(f"{tag} **{n}. {r['name']}** — {r['points']} pts")
 return discord.Embed(title=f"🔥 {co['name']} — Playoff Picture",description='\n'.join(lines) or 'No standings.',footer='Green = currently inside playoff cut' if cut else 'No playoff cut configured.')

async def launch_fixture(i,cid):
 from cogs.menu import admin_ok
 if not admin_ok(i):return await i.response.send_message('Admin permission required.',ephemeral=True)
 f=next_fixture(cid)
 if not f:return await i.response.send_message('No scheduled playable fixture remains.',ephemeral=True)
 co=competition_view(cid)[0];home=fixture_roster(f['id'],f['home_id']);away=fixture_roster(f['id'],f['away_id'])
 if not home or not away:return await i.response.send_message('The next fixture has an incomplete locked roster.',ephemeral=True)
 from cogs.games import rb
 names={}
 with connect() as c:
  table='teams' if co['entrant_type']=='team' else 'bowlers'
  for eid in (f['home_id'],f['away_id']):names[eid]=c.execute(f'SELECT name FROM {table} WHERE id=?',(eid,)).fetchone()['name']
 bowlers=[]
 for n in range(max(len(home),len(away))):
  if n<len(home):bowlers.append(rb(home[n],names[f['home_id']]))
  if n<len(away):bowlers.append(rb(away[n],names[f['away_id']]))
 s=GameSession(bowlers,lane=co['lane_condition'],season_id=co['season_id'],competition_id=cid,fixture_id=f['id']);SESSIONS[i.channel_id]=s
 for p in s.players:p.ball_key=bowler_loadout(p.bowler.id).get('primary_ball','hybrid')
 with connect() as c:c.execute("UPDATE fixtures SET status='playing' WHERE id=?",(f['id'],))
 await i.response.send_message(f"🎳 **{co['name']}**\nFixture #{f['id']} is live — **{names[f['home_id']]} vs {names[f['away_id']]}**.")

class CompetitionPick(discord.ui.Select):
 def __init__(self,parent):
  self.parent=parent;rs=_rows("SELECT id,name FROM competitions WHERE state IN ('registration','locked','active','completed') ORDER BY id DESC")
  super().__init__(placeholder='Select competition',options=_opts(rs) or [discord.SelectOption(label='No competitions',value='0')],row=0)
 async def callback(self,i):self.parent.cid=int(self.values[0]);await i.response.edit_message(embed=competition_embed(self.parent.cid),view=self.parent)


class SubPick(discord.ui.Select):
 def __init__(self,parent):
  self.parent=parent;rs=_rows('''SELECT r.bowler_id id,t.name||' — '||b.name name FROM competition_rosters r JOIN teams t ON t.id=r.team_id JOIN bowlers b ON b.id=r.bowler_id WHERE r.competition_id=? ORDER BY t.name,r.slot''',(parent.cid,))
  super().__init__(placeholder='Choose locked-roster bowler',options=_opts(rs) or [discord.SelectOption(label='No roster',value='0')])
 async def callback(self,i):self.parent.bid=int(self.values[0]);await i.response.defer()

class SubstituteManager(discord.ui.View):
 async def interaction_check(self,i):
  from cogs.menu import admin_ok
  if not admin_ok(i):
   await i.response.send_message('Admin permission required.',ephemeral=True)
   return False
  return True
 def __init__(self,cid):
  super().__init__(timeout=600);self.cid=cid;self.bid=None;self.add_item(SubPick(self))
 async def apply(self,i,value):
  if not self.bid:return await i.response.send_message('Choose a bowler.',ephemeral=True)
  r=_rows('SELECT team_id FROM competition_rosters WHERE competition_id=? AND bowler_id=?',(self.cid,self.bid))
  ok=bool(r and set_substitute(self.cid,r[0]['team_id'],self.bid,value));await i.response.send_message('✅ Substitute status updated.' if ok else 'Could not update substitute.',ephemeral=True)
 @discord.ui.button(label='Set Substitute',style=discord.ButtonStyle.primary,row=1)
 async def sub(self,i,b):await self.apply(i,True)
 @discord.ui.button(label='Set Starter',style=discord.ButtonStyle.success,row=1)
 async def starter(self,i,b):await self.apply(i,False)

class CompetitionDirector(discord.ui.View):
 async def interaction_check(self,i):
  from cogs.menu import admin_ok
  if not admin_ok(i):
   await i.response.send_message('Admin permission required.',ephemeral=True)
   return False
  return True
 def __init__(self,cid=None):super().__init__(timeout=900);self.cid=cid;self.add_item(CompetitionPick(self))
 async def need(self,i):
  if not self.cid:await i.response.send_message('Choose a competition first.',ephemeral=True);return False
  return True
 @discord.ui.button(label='Fixtures / Results',emoji='📅',style=discord.ButtonStyle.primary,row=1)
 async def fixtures(self,i,b):
  if await self.need(i):await i.response.send_message(embed=fixtures_embed(self.cid),ephemeral=True)
 @discord.ui.button(label='Table',emoji='📊',style=discord.ButtonStyle.primary,row=1)
 async def table(self,i,b):
  if await self.need(i):await i.response.send_message(embed=table_embed(self.cid),ephemeral=True)
 @discord.ui.button(label='Bracket / Stages',emoji='🧩',style=discord.ButtonStyle.primary,row=1)
 async def bracket(self,i,b):
  if await self.need(i):await i.response.send_message(embed=bracket_embed(self.cid),ephemeral=True)
 @discord.ui.button(label='Playoff Picture',emoji='🔥',style=discord.ButtonStyle.secondary,row=2)
 async def playoffs(self,i,b):
  if await self.need(i):await i.response.send_message(embed=playoff_embed(self.cid),ephemeral=True)
 @discord.ui.button(label='Roster / Subs',emoji='👥',style=discord.ButtonStyle.secondary,row=2)
 async def roster(self,i,b):
  if not await self.need(i):return
  co=competition_view(self.cid)[0]
  if co['entrant_type']=='individual':return await i.response.send_message('Individual competition: each entrant is their own locked roster.',ephemeral=True)
  rs=_rows('''SELECT t.name team,b.name,r.slot,r.is_substitute FROM competition_rosters r JOIN teams t ON t.id=r.team_id JOIN bowlers b ON b.id=r.bowler_id WHERE r.competition_id=? ORDER BY t.name,r.is_substitute,r.slot''',(self.cid,))
  await i.response.send_message('👥 **Locked Competition Rosters**\n'+('\n'.join(f"• **{x['team']}** — {x['name']} {'(SUB)' if x['is_substitute'] else ''}" for x in rs) or 'No locked roster.'),view=SubstituteManager(self.cid),ephemeral=True)
 @discord.ui.button(label='Start Next Fixture',emoji='🎳',style=discord.ButtonStyle.success,row=2)
 async def start(self,i,b):
  if await self.need(i):await launch_fixture(i,self.cid)
 @discord.ui.button(label='Refresh',emoji='🔄',style=discord.ButtonStyle.secondary,row=3)
 async def refresh(self,i,b):
  if await self.need(i):await i.response.edit_message(embed=competition_embed(self.cid),view=self)

def my_competitions_embed(owner):
 items=bowler_competitions(owner)
 e=discord.Embed(title='🎳 My Competitions')
 if not items:e.description='You have no current locked/active competitions.';return e
 for bowler,s in items[:10]:
  co=s['competition'];row=s['standing'];place=f"#{s['place']}" if s['place'] else '—';record=f"{row['wins']}-{row['draws']}-{row['losses']}" if row else 'No games yet'
  nxt=f"Fixture #{s['next']['id']} • Round {s['next']['round_no']}" if s['next'] else 'No fixture currently scheduled'
  extra=f" • Losses {s['losses']}/2" if co['format']=='double_elimination' else ''
  e.add_field(name=f"{bowler['name']} — {co['name']}",value=f"**{s['status']}** • Placement **{place}**{extra}\nRecord **{record}**\nNext: {nxt}",inline=False)
 return e
