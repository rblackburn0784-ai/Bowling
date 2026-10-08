import io
import discord
from PIL import Image,ImageDraw,ImageFont
from storage.database import connect
from services.season_presentation import season_home,week_fixtures,zones,season_award_races,season_records
from services.season_gazette import publish,archive,get_issue
from services.gazette_artwork import render_issue

def _names(cid,ids):
 with connect() as c:
  co=c.execute('SELECT entrant_type FROM competitions WHERE id=?',(cid,)).fetchone()
  if not co:return {}
  table='teams' if co['entrant_type']=='team' else 'bowlers'
  return {r['id']:r['name'] for r in c.execute(f"SELECT id,name FROM {table} WHERE id IN ({','.join('?' for _ in ids)})",tuple(ids))} if ids else {}

def _font(size):
 for path in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'):
  try:return ImageFont.truetype(path,size)
  except OSError:pass
 return ImageFont.load_default()

def season_card(sid):
 data=season_home(sid)
 if not data:return None
 s,comps,fixtures,leaders=data
 im=Image.new('RGB',(1100,580),(13,17,31));d=ImageDraw.Draw(im)
 d.rounded_rectangle((24,24,1076,556),radius=25,outline=(53,193,224),width=3)
 d.text((55,52),'THE GUTTER SAINTS  /  SEASON HUB',font=_font(22),fill=(69,217,237))
 d.text((55,100),s['name'][:35],font=_font(53),fill='white')
 d.text((55,177),f"{s['status'].upper()}  •  {len(comps)} COMPETITIONS  •  {sum(x['status']=='complete' for x in fixtures)} RESULTS",font=_font(21),fill=(196,206,224))
 d.line((55,229,1045,229),fill=(68,83,111),width=2)
 d.text((55,255),'LEAGUE CAMPAIGN',font=_font(24),fill=(69,217,237))
 for n,c in enumerate(comps[:5]):
  d.text((65,302+n*43),f"{c['name'][:30]}  •  {c['state'].title()}",font=_font(21),fill='white')
 d.text((605,255),'SEASON LEADERS',font=_font(24),fill=(69,217,237))
 ranked=sorted((x for x in leaders if x['games']>=3),key=lambda x:x['average'] or 0,reverse=True)
 for n,x in enumerate(ranked[:4]):
  d.text((615,302+n*43),f"{n+1}. {x['name'][:18]}  {x['average']:.1f} avg",font=_font(20),fill='white')
 b=io.BytesIO();im.save(b,format='PNG');b.seek(0);return discord.File(b,filename='gutter_season_hub.png')

def _embed(title,lines):
 return discord.Embed(title=title,description=('\n'.join(lines) or 'No recorded data yet.')[:4000],colour=discord.Colour.teal())

class SeasonSelect(discord.ui.Select):
 def __init__(self,parent):
  self.parent=parent
  with connect() as c:rows=c.execute('SELECT id,name FROM seasons ORDER BY id DESC LIMIT 25').fetchall()
  super().__init__(placeholder='Choose season',options=[discord.SelectOption(label=r['name'][:100],value=str(r['id'])) for r in rows] or [discord.SelectOption(label='No seasons available',value='0')])
 async def callback(self,i):
  self.parent.sid=int(self.values[0]);data=season_home(self.parent.sid)
  await i.response.edit_message(embed=_embed('📅 Season Home',[f"**{data[0]['name']}** — {data[0]['status'].title()}",f"Competitions: {len(data[1])}"] if data else ['No season selected']),view=self.parent)

class CompetitionSelect(discord.ui.Select):
 def __init__(self,parent,sid):
  self.parent=parent
  with connect() as c:rows=c.execute('SELECT id,name FROM competitions WHERE season_id=? ORDER BY id DESC LIMIT 25',(sid,)).fetchall()
  super().__init__(placeholder='Choose season competition',options=[discord.SelectOption(label=r['name'][:100],value=str(r['id'])) for r in rows] or [discord.SelectOption(label='No competitions',value='0')],row=0)
 async def callback(self,i):
  self.parent.cid=int(self.values[0]);await i.response.edit_message(embed=_embed('🏆 Competition selected',[f"Competition #{self.parent.cid}",'Choose Fixtures, Form Table or Zones below.']),view=self.parent)

class LeagueWeekView(discord.ui.View):
 def __init__(self,sid):
  super().__init__(timeout=600);self.sid=sid;self.cid=None;self.add_item(CompetitionSelect(self,sid))
 async def need(self,i):
  if not self.cid:await i.response.send_message('Select a competition first.',ephemeral=True);return False
  return True
 @discord.ui.button(label='Fixture Week',style=discord.ButtonStyle.primary,row=1)
 async def week(self,i,b):
  if not await self.need(i):return
  round_no,fs=week_fixtures(self.cid);names=_names(self.cid,{x['home_id'] for x in fs if x['home_id']}|{x['away_id'] for x in fs if x['away_id']})
  lines=[f"**{names.get(f['home_id'],'BYE')}** vs **{names.get(f['away_id'],'BYE')}** • {f['status'].title()}"+(f" • {f['home_score']}–{f['away_score']}" if f['home_score'] is not None else '') for f in fs]
  await i.response.send_message(embed=_embed(f'📅 Fixture Week • Round {round_no}',lines),ephemeral=True)
 @discord.ui.button(label='Form Table',style=discord.ButtonStyle.primary,row=1)
 async def form(self,i,b):
  if not await self.need(i):return
  await i.response.send_message(embed=_embed('📈 League Form',[f"**{n}. {r['name']}** • {r['points']} pts • {form}" for n,r,zone,form in zones(self.cid)]),ephemeral=True)
 @discord.ui.button(label='Promotion / Playoffs',style=discord.ButtonStyle.secondary,row=1)
 async def zone(self,i,b):
  if not await self.need(i):return
  symbols={'promotion':'⬆️','playoff':'🏆','relegation':'⬇️','safe':'•'}
  await i.response.send_message(embed=_embed('🔥 Promotion, Playoffs & Relegation',[f"{symbols[z]} **{n}. {r['name']}** — {r['points']} pts • {form}" for n,r,z,form in zones(self.cid)]),ephemeral=True)

class SeasonExperience(discord.ui.View):
 def __init__(self,sid=None):super().__init__(timeout=900);self.sid=sid;self.add_item(SeasonSelect(self))
 async def need(self,i):
  if not self.sid:await i.response.send_message('Choose a season first.',ephemeral=True);return False
  return True
 @discord.ui.button(label='Graphical Season Hub',style=discord.ButtonStyle.success,row=1)
 async def hub(self,i,b):
  if await self.need(i):await i.response.send_message(file=season_card(self.sid),ephemeral=True)
 @discord.ui.button(label='Fixtures & League',style=discord.ButtonStyle.primary,row=1)
 async def fixtures(self,i,b):
  if await self.need(i):await i.response.send_message(embed=_embed('📅 League Match Centre',['Select a competition below.']),view=LeagueWeekView(self.sid),ephemeral=True)
 @discord.ui.button(label='Season Awards',style=discord.ButtonStyle.primary,row=1)
 async def awards(self,i,b):
  if not await self.need(i):return
  races=season_award_races(self.sid);lines=[]
  for title,leaders in races.items():
   lines.append(f"**{title}**")
   lines.extend(f"• {r['name']} — {r['average']:.1f}" if title.startswith('Average') else f"• {r['name']} — {r[{'High Game':'high_game','Strikes':'strikes','Splits Converted':'split_conversions','Games Played':'games'}[title]]}" for r in leaders[:3])
  await i.response.send_message(embed=_embed('🏅 Season Award Races',lines),ephemeral=True)
 @discord.ui.button(label='League Records',style=discord.ButtonStyle.secondary,row=2)
 async def records(self,i,b):
  if await self.need(i):await i.response.send_message(embed=_embed('🏛️ Season High Games',[f"{n}. **{r['name']}** — {r['score']}" for n,r in enumerate(season_records(self.sid),1)]),ephemeral=True)
 @discord.ui.button(label='Gazette Archive',style=discord.ButtonStyle.secondary,row=2)
 async def gazette(self,i,b):
  if not await self.need(i):return
  issues=archive(self.sid)
  if not issues:return await i.response.send_message('No published weekly editions yet.',ephemeral=True)
  await i.response.send_message(embed=_embed('Newspaper Archive',[f"**Issue #{x['issue_no']}** • {x['week_start']} to {x['week_end']} — {x['headline']}" for x in issues]),view=GazetteArchive(self.sid),ephemeral=True)
 @discord.ui.button(label='Publish Weekly Issue',style=discord.ButtonStyle.success,row=3)
 async def publish_week(self,i,b):
  if not await self.need(i):return
  if not i.user.guild_permissions.manage_guild:return await i.response.send_message('Manage Server permission required.',ephemeral=True)
  try:issue,created=publish(self.sid)
  except Exception as exc:return await i.response.send_message(f'Unable to publish: {type(exc).__name__}',ephemeral=True)
  await i.response.send_message(embed=issue_embed(issue),file=discord.File(render_issue(issue),filename='gutter_gazette.png'),content='New edition published.' if created else 'This week already has an archived issue.',ephemeral=True)

def issue_embed(x):
 return _embed(f"📰 Gazette • Issue #{x['issue_no']} • {x['week_start']}",[f"**{x['headline']}**",x['body']])

class GazetteIssuePick(discord.ui.Select):
 def __init__(self,view):
  self.parent=view
  issues=archive(view.sid)
  super().__init__(placeholder='Open archived issue',options=[discord.SelectOption(label=f"Issue #{x['issue_no']} — {x['week_start']}",value=str(x['issue_no'])) for x in issues] or [discord.SelectOption(label='No issues',value='0')])
 async def callback(self,i):
  x=get_issue(self.parent.sid,int(self.values[0]))
  if not x:return await i.response.send_message('Issue unavailable.',ephemeral=True)
  await i.response.send_message(embed=issue_embed(x),file=discord.File(render_issue(x),filename='gutter_gazette.png'),ephemeral=True)

class GazetteArchive(discord.ui.View):
 def __init__(self,sid):
  super().__init__(timeout=900);self.sid=sid;self.add_item(GazetteIssuePick(self))
