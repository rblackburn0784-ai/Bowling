import discord
from discord import app_commands
from discord.ext import commands
from services.audio import join_user_voice
from services.lane_visual import lane_card
from services.state import SESSIONS

class AV(commands.Cog):
 def __init__(self,bot):self.bot=bot
 @app_commands.command(name='audio_join',description='Connect Gutter Saints presentation audio to your voice channel')
 async def join(self,i:discord.Interaction):
  ok,msg=await join_user_voice(i);await i.response.send_message(msg,ephemeral=not ok)
 @app_commands.command(name='audio_leave',description='Disconnect presentation audio')
 async def leave(self,i:discord.Interaction):
  vc=i.guild.voice_client if i.guild else None
  if vc:await vc.disconnect();await i.response.send_message('🔇 Presentation audio disconnected.',ephemeral=True)
  else:await i.response.send_message('I am not connected to voice.',ephemeral=True)
 @app_commands.command(name='lane_view',description='Show the current graphical lane and standing pins')
 async def lane(self,i:discord.Interaction):
  s=SESSIONS.get(i.channel_id)
  if not s:return await i.response.send_message('No active game in this channel.',ephemeral=True)
  p=lane_card(s);await i.response.send_message(file=discord.File(p,filename='gutter_lane.png'))
async def setup(bot):await bot.add_cog(AV(bot))
