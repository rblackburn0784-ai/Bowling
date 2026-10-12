import discord
from discord import app_commands
from discord.ext import commands
from storage.database import connect
from services.media import pick

class Awards(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='award_give',description='Give a tournament or special award to a bowler')
 @app_commands.default_permissions(manage_guild=True)
 async def give(self,i:discord.Interaction,bowler:str,title:str,detail:str=''):
  from cogs.menu import admin_ok
  if not admin_ok(i):return await i.response.send_message('Manage Server permission required to give awards.',ephemeral=True)
  title=title.strip();detail=detail.strip()
  if not title or len(title)>60 or len(detail)>200:return await i.response.send_message('Award title must be 1–60 characters and detail at most 200.',ephemeral=True)
  from services.awards_admin import give_manual_award
  with connect() as c:b=c.execute('SELECT id FROM bowlers WHERE name=? COLLATE NOCASE',(bowler,)).fetchone()
  if not b:return await i.response.send_message('Bowler not found.',ephemeral=True)
  ok,message=give_manual_award(b['id'],title,detail,i.user.id)
  if not ok:return await i.response.send_message(message,ephemeral=True)
  await i.response.send_message(f'🏅 **{title}**\nAwarded to **{message}**'+(f'\n*{detail}*' if detail else ''));u=pick('award')
  if u:await i.channel.send(u)
 @app_commands.command(name='awards',description='Show awards won by a bowler')
 async def show(self,i:discord.Interaction,bowler:str):
  with connect() as c:r=c.execute('''SELECT a.title,a.detail,a.created_at FROM awards a JOIN bowlers b ON b.id=a.bowler_id WHERE b.name=? COLLATE NOCASE ORDER BY a.id DESC''',(bowler,)).fetchall()
  await i.response.send_message(f"🏅 **{bowler} — Awards**\n"+('\n'.join(f"• **{x['title']}**"+(f" — {x['detail']}" if x['detail'] else '') for x in r) or 'No awards yet.'))
async def setup(bot):await bot.add_cog(Awards(bot))
