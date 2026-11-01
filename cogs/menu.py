import discord
from services.menu_navigation import edit_panel, menu_home, modal_panel
from discord import app_commands
from discord.ext import commands
from services.roster import get_bowler_by_owner,list_bowlers,update_owned_sprite
from storage.database import connect
from ui.embeds import bowler_embed
from services.equipment import BALLS
from services.v271 import bowler_loadout,set_bowler_ball
from services.bowler_sprites import installed_sprites,sprite_label
from services.sprite_preview import render_sprite_preview,PREVIEW_FILENAME


def bowler_art_file(key):
 return discord.File(render_sprite_preview(key),filename=PREVIEW_FILENAME)

def art_embed(title,key,description):
 e=discord.Embed(title=title,description=description,colour=discord.Color.from_rgb(44,167,219))
 e.add_field(name='🎭 Selected Sprite',value=f'**{sprite_label(key)}** • {len(installed_sprites())}/20 installed',inline=False)
 e.set_image(url=f'attachment://{PREVIEW_FILENAME}')
 return e

class OwnedView(discord.ui.View):
 def __init__(self,owner_id,timeout=600):
  super().__init__(timeout=timeout);self.owner_id=owner_id
 async def interaction_check(self,i):
  if i.user.id != self.owner_id:
   await i.response.send_message('Only the bowler owner can change this selection.',ephemeral=True)
   return False
  return True

class SpriteChoiceSelect(discord.ui.Select):
 def __init__(self,state):
  self.state=state
  keys=installed_sprites()
  super().__init__(placeholder='Select your bowling character',row=0,
      options=[discord.SelectOption(label=sprite_label(key),value=key,
          default=key==state.sprite,description='Five-frame bowling animation') for key in keys])
 async def callback(self,i):
  key=self.values[0]
  if key not in installed_sprites():
   return await i.response.send_message('That sprite is currently unavailable.',ephemeral=True)
  self.state.sprite=key
  is_new=isinstance(self.state,BowlerBuildState)
  view=CreateSpriteView(self.state) if is_new else EditSpriteView(self.state)
  embed=art_embed(f'🎳 Create {self.state.name} — Choose Character' if is_new else f'🎭 Edit {self.state.name}',
       key,'Select your animated bowler, then continue.' if is_new else 'Choose a sprite and press **Save Sprite**. Rank and attributes are unchanged.')
  await i.response.edit_message(embed=embed,view=view,attachments=[bowler_art_file(key)])

class CreateSpriteView(OwnedView):
 def __init__(self,state):
  super().__init__(state.owner_id);self.state=state
  if installed_sprites():self.add_item(SpriteChoiceSelect(state))
  else:self.next.disabled=True
 @discord.ui.button(label='Next: Build Stats',style=discord.ButtonStyle.success,row=2)
 async def next(self,i,b):
  if self.state.sprite not in installed_sprites():
   return await i.response.send_message('Choose an installed sprite first.',ephemeral=True)
  await i.response.edit_message(embed=builder_embed(self.state,1),view=StatPageOne(self.state))
 @discord.ui.button(label='Cancel',style=discord.ButtonStyle.secondary,row=2)
 async def cancel(self,i,b):await i.response.edit_message(content='Bowler creation cancelled.',embed=None,view=HomeView(),attachments=[])

class EditSpriteState:
 def __init__(self,bowler,owner_id):
  self.name=bowler.name;self.owner_id=owner_id
  keys=installed_sprites();preferred=bowler.sprite_key
  self.sprite=preferred if preferred in keys else (keys[0] if keys else None)

class EditSpriteView(OwnedView):
 def __init__(self,state):
  super().__init__(state.owner_id);self.state=state
  if installed_sprites():self.add_item(SpriteChoiceSelect(state))
  else:self.save.disabled=True
 @discord.ui.button(label='Save Sprite',style=discord.ButtonStyle.success,row=2)
 async def save(self,i,b):
  result,error=update_owned_sprite(i.user.id,self.state.sprite)
  if not result:return await i.response.send_message(error,ephemeral=True)
  bowler=get_bowler_by_owner(i.user.id)
  embed=bowler_embed(bowler);embed.set_image(url=f'attachment://{PREVIEW_FILENAME}')
  await i.response.edit_message(embed=embed,view=CareerView(bowler.id),attachments=[bowler_art_file(self.state.sprite)])
 @discord.ui.button(label='Cancel',style=discord.ButtonStyle.secondary,row=2)
 async def cancel(self,i,b):
  bowler=get_bowler_by_owner(i.user.id)
  if bowler:
   embed=bowler_embed(bowler);embed.set_image(url=f'attachment://{PREVIEW_FILENAME}')
   await i.response.edit_message(embed=embed,view=CareerView(bowler.id),attachments=[bowler_art_file(bowler.sprite_key)])
  else:await i.response.edit_message(content='No bowler linked.',embed=None,view=HomeView(),attachments=[])

async def open_sprite_editor(i,bowler):
 keys=installed_sprites()
 if not keys:
  return await edit_panel(i, content='No complete character animation packs installed. Each character needs 1.png–5.png in assets/sprites/<key>/.')
 state=EditSpriteState(bowler,i.user.id)
 await edit_panel(i, embed=art_embed(f'🎭 Edit {state.name}',state.sprite,
     'Choose a sprite and press **Save Sprite**. Rank and attributes are unchanged.'), view=EditSpriteView(state), file=bowler_art_file(state.sprite))

def admin_ok(i):return bool(i.user.guild_permissions.administrator or i.user.guild_permissions.manage_guild)
async def swap(i,title,view,body='Choose an option below.'):
 await edit_panel(i, content=f'{title}\n{body}', embed=None, view=view)
class HomeView(discord.ui.View):
 def __init__(self):super().__init__(timeout=300)
 @discord.ui.button(label='🏠 Main Menu',style=discord.ButtonStyle.secondary)
 async def home(self,i,b):await edit_panel(i, content='🎳 **THE GUTTER SAINTS**', view=PublicMenu(admin=admin_ok(i)))
class AdminHomeView(HomeView):
 async def interaction_check(self,i):
  if not admin_ok(i):
   await i.response.send_message('Admin permission required.',ephemeral=True)
   return False
  return True
 @discord.ui.button(label='🛠️ Admin Home',style=discord.ButtonStyle.secondary)
 async def adminhome(self,i,b):await edit_panel(i, content='🛠️ **Gutter Saints Admin Control**', view=AdminMenu())
class BowlerIdentityModal(discord.ui.Modal,title='Create Bowler'):
 name=discord.ui.TextInput(label='Bowler name',max_length=32)
 handedness=discord.ui.TextInput(label='Handedness',placeholder='R or L',default='R',max_length=1)
 async def on_submit(self,i):
  if get_bowler_by_owner(i.user.id):return await i.response.send_message('You already have a linked bowler.',ephemeral=True)
  hand=self.handedness.value.strip().upper()
  if hand not in ('R','L'):return await i.response.send_message('Handedness must be R or L.',ephemeral=True)
  if not self.name.value.strip():return await i.response.send_message('Enter a bowler name.',ephemeral=True)
  keys=installed_sprites()
  if not keys:return await i.response.send_message('No complete bowler animation packs installed.',ephemeral=True)
  state=BowlerBuildState(self.name.value.strip(),hand,i.user.id)
  state.sprite=keys[0]
  await modal_panel(i, embed=art_embed(f'🎳 Create {state.name} — Choose Character',state.sprite,
      'Select your character below. You can change it later from **Edit Bowler**.'), view=CreateSpriteView(state), file=bowler_art_file(state.sprite))
class BowlerBuildState:
 def __init__(self,name,hand,owner_id=None):
  self.name=name;self.hand=hand;self.owner_id=owner_id;self.sprite=None;self.stats={'accuracy':5,'style':5,'flair':5,'consistency':5,'spin':5,'nerves':5}
 @property
 def used(self):return sum(self.stats.values())
 @property
 def remaining(self):
  from config import DEFAULT_STAT_BUDGET
  return DEFAULT_STAT_BUDGET-self.used
def builder_embed(state,page):
 from config import DEFAULT_STAT_BUDGET
 labels={'accuracy':'Accuracy','style':'Style','flair':'Flair','consistency':'Consistency','spin':'Spin','nerves':'Nerves'}
 lines=[f"**{labels[k]}:** {v}" for k,v in state.stats.items()]
 colour=discord.Color.green() if state.remaining>=0 else discord.Color.red()
 e=discord.Embed(title=f'🎳 Build {state.name}',description='\n'.join(lines),colour=colour)
 e.add_field(name='Career Rank',value='**Rookie — Rank 1** (earned through play)',inline=False)
 e.add_field(name='🎭 Your Sprite',value=f'**{sprite_label(state.sprite)}**',inline=False)
 e.set_image(url=f'attachment://{PREVIEW_FILENAME}')
 e.add_field(name='Points',value=f'**Used:** {state.used} / {DEFAULT_STAT_BUDGET}\n**Remaining:** {state.remaining}',inline=False)
 e.set_footer(text=f'Stat Builder • Page {page}/2 • Creation range 5–25 • Career range 1–50')
 return e
class StatSelect(discord.ui.Select):
 def __init__(self,state,key,label,row):
  self.state=state;self.key=key
  options=[discord.SelectOption(label=str(v),value=str(v),default=state.stats[key]==v) for v in range(5,26)]
  super().__init__(placeholder=f'{label}: {state.stats[key]}',options=options,row=row)
 async def callback(self,i):
  self.state.stats[self.key]=int(self.values[0])
  page=1 if self.key in ('accuracy','style','flair') else 2
  view=StatPageOne(self.state) if page==1 else StatPageTwo(self.state)
  await i.response.edit_message(embed=builder_embed(self.state,page),view=view)
class StatPageOne(OwnedView):
 def __init__(self,state):
  super().__init__(state.owner_id);self.state=state
  for row,(key,label) in enumerate((('accuracy','Accuracy'),('style','Style'),('flair','Flair'))):self.add_item(StatSelect(state,key,label,row))
 @discord.ui.button(label='Next: More Stats',emoji='➡️',style=discord.ButtonStyle.primary,row=4)
 async def nxt(self,i,b):await i.response.edit_message(embed=builder_embed(self.state,2),view=StatPageTwo(self.state))
 @discord.ui.button(label='Cancel',style=discord.ButtonStyle.secondary,row=4)
 async def cancel(self,i,b):await i.response.edit_message(content='Bowler creation cancelled.',embed=None,view=HomeView())
class StatPageTwo(OwnedView):
 def __init__(self,state):
  super().__init__(state.owner_id);self.state=state
  for row,(key,label) in enumerate((('consistency','Consistency'),('spin','Spin'),('nerves','Nerves'))):self.add_item(StatSelect(state,key,label,row))
  self.create.disabled=state.remaining!=0
 @discord.ui.button(label='Back',emoji='⬅️',style=discord.ButtonStyle.secondary,row=3)
 async def back(self,i,b):await i.response.edit_message(embed=builder_embed(self.state,1),view=StatPageOne(self.state))
 @discord.ui.button(label='Create Bowler',emoji='✅',style=discord.ButtonStyle.success,row=3)
 async def create(self,i,b):
  from models.bowler import Bowler
  from services.roster import create_bowler
  from config import DEFAULT_STAT_BUDGET
  from config import CREATION_MIN_STAT,CREATION_MAX_STAT
  if self.state.used!=DEFAULT_STAT_BUDGET:return await i.response.send_message(f'You must spend exactly {DEFAULT_STAT_BUDGET} points before creating your bowler.',ephemeral=True)
  if any(x<CREATION_MIN_STAT or x>CREATION_MAX_STAT for x in self.state.stats.values()):return await i.response.send_message(f'Every starting stat must be between {CREATION_MIN_STAT} and {CREATION_MAX_STAT}.',ephemeral=True)
  if get_bowler_by_owner(i.user.id):return await i.response.send_message('You already have a linked bowler.',ephemeral=True)
  v=self.state.stats
  if self.state.sprite not in installed_sprites():return await i.response.send_message('Character artwork is unavailable.',ephemeral=True)
  character=Bowler(None,self.state.name,i.user.id,self.state.hand,1,v['accuracy'],v['style'],v['flair'],v['consistency'],v['spin'],v['nerves'])
  character.sprite_key=self.state.sprite
  try:create_bowler(character)
  except Exception as e:return await i.response.send_message(f'Could not create bowler: {e}',ephemeral=True)
  await i.response.edit_message(content=f"🎳 **{self.state.name}** created with **{self.state.used}/{DEFAULT_STAT_BUDGET}** points.",embed=None,view=HomeView())
 @discord.ui.button(label='Cancel',style=discord.ButtonStyle.danger,row=3)
 async def cancel(self,i,b):await i.response.edit_message(content='Bowler creation cancelled.',embed=None,view=HomeView())
class BowlerDashboard(AdminHomeView):
 @discord.ui.button(label='➕ Create Bowler',style=discord.ButtonStyle.success)
 async def create(self,i,b):await i.response.send_modal(BowlerIdentityModal())
 @discord.ui.button(label='📋 Bowler List',style=discord.ButtonStyle.primary)
 async def listing(self,i,b):
  with connect() as c:r=c.execute('SELECT name,owner_id FROM bowlers ORDER BY name').fetchall()
  await i.response.send_message('🎳 **Bowlers**\n'+('\n'.join(f"• {x['name']} — {'Offline' if x['owner_id']==0 else 'Discord linked'}" for x in r) or 'None'),ephemeral=True)
from cogs.dashboard_ui import TeamDashboard,TournamentDashboard,CompetitionDashboard,MatchDashboard,RecordsDashboard,SettingsDashboard
class AdminMenu(HomeView):
 def __init__(self):super().__init__()
 async def interaction_check(self,i):
  if not admin_ok(i):
   await i.response.send_message('Admin permission required.',ephemeral=True)
   return False
  return True
 async def gate(self,i):
  if not admin_ok(i):await i.response.send_message('Admin/Manage Server permission required.',ephemeral=True);return False
  return True
 @discord.ui.button(label='🎳 Bowler Management',style=discord.ButtonStyle.primary)
 async def bowlers(self,i,b):
  if await self.gate(i):await swap(i,'🎳 **Bowler Management**',BowlerDashboard())
 @discord.ui.button(label='👥 Team Management',style=discord.ButtonStyle.primary)
 async def teams(self,i,b):
  if await self.gate(i):await swap(i,'👥 **Team Management**',TeamDashboard())
 @discord.ui.button(label='🏆 Competition Director',style=discord.ButtonStyle.primary)
 async def tournaments(self,i,b):
  if await self.gate(i):
   from cogs.dashboard_ui import CompetitionDashboard
   await swap(i,'🏆 **Competition Director**',CompetitionDashboard())
 @discord.ui.button(label='🎮 Match Control',style=discord.ButtonStyle.success)
 async def match(self,i,b):
  if await self.gate(i):await swap(i,'🎮 **Match Control**',MatchDashboard())
 @discord.ui.button(label='📊 Records & Awards',style=discord.ButtonStyle.secondary)
 async def records(self,i,b):
  if await self.gate(i):await swap(i,'📊 **Records & Awards**',RecordsDashboard())
 @discord.ui.button(label='⚙️ Bot Settings',style=discord.ButtonStyle.secondary)
 async def settings(self,i,b):
  if await self.gate(i):await swap(i,'⚙️ **Bot Settings**',SettingsDashboard())
class BallSelect(discord.ui.Select):
 def __init__(self,bowler_id):
  self.bowler_id=bowler_id;super().__init__(placeholder='Choose primary strike ball',options=[discord.SelectOption(label=v.name,value=k,description=f'Hook {v.hook:.2f} • Length {v.length:.2f} • Control {v.control:.2f}') for k,v in BALLS.items()])
 async def callback(self,i):set_bowler_ball(self.bowler_id,self.values[0]);await edit_panel(i, content=f'🎳 Primary ball set to **{BALLS[self.values[0]].name}**. Spares use Plastic automatically.', view=ArsenalView(self.bowler_id))
class ArsenalView(HomeView):
 def __init__(self,bowler_id):super().__init__();self.add_item(BallSelect(bowler_id))
class CareerView(HomeView):
 def __init__(self,bowler_id):super().__init__();self.bowler_id=bowler_id
 @discord.ui.button(label='Change Sprite',emoji='🎭',style=discord.ButtonStyle.success)
 async def sprite(self,i,b):
  bowler=get_bowler_by_owner(i.user.id)
  if not bowler or bowler.id!=self.bowler_id:
   return await i.response.send_message('Only the linked bowler owner can edit this sprite.',ephemeral=True)
  await open_sprite_editor(i,bowler)
 @discord.ui.button(label='Career Progress',emoji='📈',style=discord.ButtonStyle.primary)
 async def progress(self,i,b):
  from services.career_finale import career_profile
  p=career_profile(self.bowler_id)
  if not p:return await edit_panel(i, content='Bowler unavailable.', view=CareerView(self.bowler_id))
  next_rank=f"{p['xp']}/{p['next_rank_xp']} XP to next rank" if p['next_rank_xp'] is not None else 'Maximum rank reached'
  skills=' • '.join(f"{key.title()} {value}" for key,value in p['attributes'].items())
  await edit_panel(i, content=f"📈 **{p['name']} — Career**\n**Rank {p['rank']} — {p['rank_title']}**\n{next_rank} ({p['rank_percent']:.1f}%)\n**{p['games']} games** • Average {p['average']:.2f} • High {p['high_game']}\nAchievements **{p['achievement_count']}** • Honours **{p['honours_count']}**\nCosmetic exhibition XP: **{p['cosmetic_xp']}** (does not affect rank)\n{skills}", view=CareerView(self.bowler_id))
 @discord.ui.button(label='Career Timeline',emoji='🕰️',style=discord.ButtonStyle.primary)
 async def timeline(self,i,b):
  from services.career import recent_timeline
  rows=recent_timeline(self.bowler_id,15)
  text='\n'.join(f"{r['icon']} **{r['headline']}** — {r['detail']}" for r in rows) or 'No career milestones yet.'
  await edit_panel(i, content='🕰️ **CAREER TIMELINE**\n'+text, view=CareerView(self.bowler_id))
 @discord.ui.button(label='Honours',emoji='🏆',style=discord.ButtonStyle.success)
 async def honours(self,i,b):
  from services.honours import honours_for_bowler
  rows=honours_for_bowler(self.bowler_id)
  text='\n'.join(f"• **{r['title']}** — {r['detail']}" for r in rows[:15]) or 'No career honours yet.'
  await edit_panel(i, content='🏆 **CAREER HONOURS**\n'+text, view=CareerView(self.bowler_id))
 @discord.ui.button(label='Tendencies',emoji='🧬',style=discord.ButtonStyle.secondary)
 async def tendencies(self,i,b):
  from services.career import tendency_summary
  rows=tendency_summary(self.bowler_id)
  text='\n'.join(f"**{r['stat'].title()}**: {r['score']:+.1f} ({r['evidence']} recent signals)" for r in rows) or 'No strong tendencies yet.'
  await edit_panel(i, content='🧬 **CAREER TENDENCIES**\n'+text+'\n\n±10 sustained evidence triggers an attribute change.', view=CareerView(self.bowler_id))
class PublicMenu(discord.ui.View):
 def __init__(self,admin=False):
  super().__init__(timeout=None)
  if not admin:
   self.remove_item(self.admin)
 @discord.ui.button(label='Create Bowler',emoji='➕',style=discord.ButtonStyle.success,custom_id='gs:create')
 async def create(self,i,b):
  if get_bowler_by_owner(i.user.id):return await i.response.send_message('You already have a linked bowler.',ephemeral=True)
  await i.response.send_modal(BowlerIdentityModal())
 @discord.ui.button(label='My Bowler',emoji='🎳',style=discord.ButtonStyle.primary,custom_id='gs:mybowler')
 async def mine(self,i,b):
  x=get_bowler_by_owner(i.user.id)
  if not x:return await i.response.send_message('You do not have a linked bowler yet — use **Create Bowler**.',ephemeral=True)
  embed=bowler_embed(x)
  embed.set_image(url=f'attachment://{PREVIEW_FILENAME}')
  await edit_panel(i, embed=embed, view=CareerView(x.id), file=bowler_art_file(x.sprite_key))
 @discord.ui.button(label='Edit Bowler',emoji='🎭',style=discord.ButtonStyle.primary,custom_id='gs:editbowler')
 async def edit_bowler(self,i,b):
  bowler=get_bowler_by_owner(i.user.id)
  if not bowler:return await i.response.send_message('Create your linked bowler first.',ephemeral=True)
  await open_sprite_editor(i,bowler)
 @discord.ui.button(label='Career Records',emoji='🏛️',style=discord.ButtonStyle.secondary,custom_id='gs:records')
 async def records(self,i,b):
  from cogs.dashboard_ui import CareerRecordView
  await edit_panel(i, content='🏛️ **Career Records**\nCompare earned records; averages require three completed games.', view=CareerRecordView())
 @discord.ui.button(label='My Stats',emoji='📊',style=discord.ButtonStyle.secondary,custom_id='gs:mystats')
 async def stats(self,i,b):
  x=get_bowler_by_owner(i.user.id)
  if not x:return await i.response.send_message('Create a bowler first.',ephemeral=True)
  await edit_panel(i, embed=bowler_embed(x), view=HomeView())
 @discord.ui.button(label='Achievements',emoji='🏅',style=discord.ButtonStyle.secondary,custom_id='gs:achievements')
 async def achievements(self,i,b):
  x=get_bowler_by_owner(i.user.id)
  if not x:return await i.response.send_message('Create a bowler first.',ephemeral=True)
  with connect() as c:r=c.execute('SELECT title FROM achievements WHERE bowler_id=? ORDER BY earned_at',(x.id,)).fetchall()
  await edit_panel(i, content='🏅 **Achievements**\n'+('\n'.join('• '+a['title'] for a in r) or 'None yet.'), view=HomeView())
 @discord.ui.button(label='My Arsenal',emoji='🎯',style=discord.ButtonStyle.secondary,custom_id='gs:arsenal')
 async def arsenal(self,i,b):
  x=get_bowler_by_owner(i.user.id)
  if not x:return await i.response.send_message('Create a bowler first.',ephemeral=True)
  load=bowler_loadout(x.id);await edit_panel(i, content=f"🎯 **{x.name}'s Arsenal**\nPrimary: **{BALLS[load.get('primary_ball','hybrid')].name}**", view=ArsenalView(x.id))
 @discord.ui.button(label='Browse Bowlers',emoji='👀',style=discord.ButtonStyle.secondary,custom_id='gs:browse')
 async def browse(self,i,b):await edit_panel(i, content='🎳 **Bowlers**\n'+('\n'.join('• '+x['name'] for x in list_bowlers()) or 'None'), view=HomeView())
 @discord.ui.button(label='Challenge Bowler',emoji='⚔️',style=discord.ButtonStyle.primary,custom_id='gs:challenge')
 async def challenge(self,i,b):
  if not get_bowler_by_owner(i.user.id):return await i.response.send_message('Create your linked bowler before challenging anyone.',ephemeral=True)
  from cogs.friendly_challenges import ChallengeComposer
  await edit_panel(i, content='⚔️ **Friendly Exhibition Challenge** — Select a linked opponent. A public invitation will appear in this channel for them to accept or decline.', view=ChallengeComposer(i.user.id))
 @discord.ui.button(label='Season Hub',emoji='📅',style=discord.ButtonStyle.secondary,custom_id='gs:seasonhub')
 async def seasonhub(self,i,b):
  from cogs.season_ui import SeasonExperience
  await edit_panel(i, content='📅 **Gutter Saints Season Hub**', view=SeasonExperience())
 @discord.ui.button(label='My Competition',emoji='🏆',style=discord.ButtonStyle.primary,custom_id='gs:mycompetition')
 async def mycompetition(self,i,b):
  from cogs.competition_ui import my_competitions_embed
  await edit_panel(i, embed=my_competitions_embed(i.user.id), view=HomeView())
 @discord.ui.button(label='Gutter Gazette',emoji='📰',style=discord.ButtonStyle.primary,custom_id='gs:gazette')
 async def gazette(self,i,b):
  from services.gazette import latest_gazette,format_gazette,gazette_archive
  g=latest_gazette()
  archive=gazette_archive(5)
  tail='\n\n**Recent Issues**\n'+'\n'.join(f"• #{x['issue_no']} — {x['tournament']}: {x['headline']}" for x in archive) if archive else ''
  await edit_panel(i, content=format_gazette(g)+tail, view=HomeView())
 @discord.ui.button(label='Admin Control',emoji='🛠️',style=discord.ButtonStyle.danger,custom_id='gs:admin')
 async def admin(self,i,b):
  if not admin_ok(i):return await i.response.send_message('Admin/Manage Server permission required.',ephemeral=True)
  await swap(i,'🛠️ **Gutter Saints Admin Control**',AdminMenu())
class Menu(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='menu',description='Open the Gutter Saints main menu')
 async def menu(self,i:discord.Interaction):await i.response.send_message('🎳 **THE GUTTER SAINTS**\nBowling, careers, achievements and tournament control.',view=PublicMenu(admin=admin_ok(i)),ephemeral=True)
async def setup(bot):await bot.add_cog(Menu(bot))
