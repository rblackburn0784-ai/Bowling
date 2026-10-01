import discord
from discord import app_commands
from discord.ext import commands
from storage.database import connect
from services.media import pick

class Awards(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='award_give',description='Give a tournament or special award to a bowler')
 async def give(self,i:discord.Interaction,bowler:str,title:str,detail:str=''):
  with connect() as c:
   b=c.execute('SELECT id FROM bowlers WHERE name=? COLLATE NOCASE',(bowler,)).fetchone()
   if not b:return await i.response.send_message('Bowler not found.',ephemeral=True)
   c.execute('INSERT INTO awards(bowler_id,title,detail) VALUES(?,?,?)',(b['id'],title,detail));c.execute('UPDATE bowler_stats SET awards=awards+1 WHERE bowler_id=?',(b['id'],))
  await i.response.send_message(f'🏅 **{title}**\nAwarded to **{bowler}**'+(f'\n*{detail}*' if detail else ''));u=pick('award')
  if u:await i.channel.send(u)
 @app_commands.command(name='awards',description='Show awards won by a bowler')
 async def show(self,i:discord.Interaction,bowler:str):
  with connect() as c:r=c.execute('''SELECT a.title,a.detail,a.created_at FROM awards a JOIN bowlers b ON b.id=a.bowler_id WHERE b.name=? COLLATE NOCASE ORDER BY a.id DESC''',(bowler,)).fetchall()
  await i.response.send_message(f"🏅 **{bowler} — Awards**\n"+('\n'.join(f"• **{x['title']}**"+(f" — {x['detail']}" if x['detail'] else '') for x in r) or 'No awards yet.'))
async def setup(bot):await bot.add_cog(Awards(bot))
