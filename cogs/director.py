import discord
from discord import app_commands
from discord.ext import commands
from services.v25 import tournament_dashboard,backup_database,undo_snapshot,restore_session,export_tournament_xlsx
from services.state import SESSIONS
from services.v271 import set_tournament_presentation,tournament_presentation
from services.lane_physics import PATTERNS
from services.career import rollback_delivery_changes
class DirectorView(discord.ui.View):
 def __init__(self,name):super().__init__(timeout=600);self.name=name
 @discord.ui.button(label='Main Menu',emoji='🏠',style=discord.ButtonStyle.secondary,row=4)
 async def home(self,i,b):
  from cogs.menu import PublicMenu
  await i.response.edit_message(content='🎳 **THE GUTTER SAINTS**\nBowling, careers, achievements and tournament control.',embed=None,view=PublicMenu())
 @discord.ui.button(label='Admin Home',emoji='🛠️',style=discord.ButtonStyle.secondary,row=4)
 async def adminhome(self,i,b):
  from cogs.menu import AdminMenu
  await i.response.edit_message(content='🛠️ **Gutter Saints Admin Control**',embed=None,view=AdminMenu())
 @discord.ui.button(label='🎥 Presentation',style=discord.ButtonStyle.secondary)
 async def presentation(self,i,b):await i.response.send_modal(PresentationModal(self.name))
 @discord.ui.button(label='Undo Last Ball',style=discord.ButtonStyle.danger)
 async def undo(self,i,b):
  current=SESSIONS.get(i.channel_id);changes=getattr(current,'last_attribute_changes',[]) if current else [];bid=getattr(current,'last_attribute_bowler_id',None) if current else None
  s=undo_snapshot(i.channel_id)
  if not s:return await i.response.send_message('No earlier snapshot.',ephemeral=True)
  rollback_delivery_changes(bid,changes);SESSIONS[i.channel_id]=s;await i.response.send_message('↩️ Last ball restored.',ephemeral=True)
 @discord.ui.button(label='Restore Match',style=discord.ButtonStyle.primary)
 async def restore(self,i,b):
  s=restore_session(i.channel_id)
  if not s:return await i.response.send_message('No saved active match.',ephemeral=True)
  SESSIONS[i.channel_id]=s;await i.response.send_message('♻️ Match restored.',ephemeral=True)
 @discord.ui.button(label='Publish Gazette',emoji='📰',style=discord.ButtonStyle.primary)
 async def gazette(self,i,b):
  from services.gazette import build_gazette,format_gazette
  from storage.database import connect
  with connect() as c:t=c.execute('SELECT id FROM tournaments WHERE name=? COLLATE NOCASE',(self.name,)).fetchone()
  if not t:return await i.response.send_message('Tournament not found.',ephemeral=True)
  g=build_gazette(t['id'])
  if not g:return await i.response.send_message('Not enough recorded tournament action for a Gazette issue yet.',ephemeral=True)
  await i.response.send_message(format_gazette(g),ephemeral=False)
 @discord.ui.button(label='Career Honours',emoji='🏆',style=discord.ButtonStyle.success)
 async def honours(self,i,b):
  from services.honours import finalize_tournament_honours
  from storage.database import connect
  with connect() as c:t=c.execute('SELECT id,status FROM tournaments WHERE name=? COLLATE NOCASE',(self.name,)).fetchone()
  if not t:return await i.response.send_message('Tournament not found.',ephemeral=True)
  if t['status']!='complete':return await i.response.send_message('Career Honours unlock when the tournament is complete.',ephemeral=True)
  result=finalize_tournament_honours(t['id']);new=result['new'] if result else []
  await i.response.send_message(f"🏆 **{self.name} CAREER HONOURS**\nChampion: **{result['champion']}**\n"+('New honours recorded:\n'+'\n'.join(f'• {n} — {h}' for n,h in new) if new else 'All honours were already recorded.'),ephemeral=False)
 @discord.ui.button(label='Export XLSX',style=discord.ButtonStyle.secondary)
 async def export(self,i,b):
  p=export_tournament_xlsx(self.name)
  if not p:return await i.response.send_message('Nothing to export.',ephemeral=True)
  await i.response.send_message(file=discord.File(p))
class PresentationModal(discord.ui.Modal,title='Tournament Presentation'):
 pattern=discord.ui.TextInput(label='Oil pattern',placeholder='house / fresh / oily / dry / transition',required=False)
 layout=discord.ui.TextInput(label='Layout',placeholder='standard / broadcast / finals / chaos',required=False)
 lane=discord.ui.TextInput(label='Lane pair start',placeholder='3',required=False)
 brand=discord.ui.TextInput(label='Broadcast title',required=False,max_length=38)
 def __init__(self,name):super().__init__();self.name=name
 async def on_submit(self,i):
  try:lane=int(self.lane.value) if self.lane.value else None
  except ValueError:return await i.response.send_message('Lane must be a number.',ephemeral=True)
  ok,err=set_tournament_presentation(self.name,self.pattern.value.lower() or None,self.layout.value.lower() or None,lane,self.brand.value or None)
  await i.response.send_message('🎥 Tournament presentation updated.' if ok else err,ephemeral=True)

class Director(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='director',description='Open Tournament Director')
 @app_commands.default_permissions(manage_guild=True)
 async def director(self,i:discord.Interaction,tournament:str|None=None):
  d=tournament_dashboard(tournament)
  if not d:return await i.response.send_message('No active tournament.',ephemeral=True)
  t,matches,nxt,leaders=d;done=sum(x['status']=='complete' for x in matches);p=tournament_presentation(t['id']);desc=f"Status **{t['status']}** • Completed **{done}/{len(matches)}**\n🎥 **{p['layout'].title()}** • Lanes **{p['lane_start']}/{p['lane_start']+1}** • Pattern **{t['lane_condition'].title()}**\n"
  if nxt:desc+=f"Next: **R{nxt['round_no']} M{nxt['match_no']} — {nxt['team_a']} vs {nxt['team_b']}**\n"
  if leaders:desc+='\n**Leaders**\n'+'\n'.join(f"{x['name']} — {x['avg']:.1f}" for x in leaders)
  await i.response.send_message(embed=discord.Embed(title=f"🏆 Tournament Director — {t['name']}",description=desc),view=DirectorView(t['name']))
async def setup(bot):await bot.add_cog(Director(bot))
