import json,random,asyncio,shutil
from pathlib import Path
import discord
BASE=Path(__file__).resolve().parent.parent
MANIFEST=BASE/'assets'/'audio.json'

def _cfg():
    try:return json.loads(MANIFEST.read_text(encoding='utf8'))
    except Exception:return {}

def pick_sound(kind):
    vals=_cfg().get(kind,[])
    if not vals:return None
    p=BASE/'assets'/'sounds'/random.choice(vals)
    return p if p.exists() else None

async def play_sound(channel,kind,volume=.55):
    """Play one local effect if the bot is already connected to the guild voice channel."""
    if not channel.guild:return False
    vc=channel.guild.voice_client
    path=pick_sound(kind)
    if not vc or not vc.is_connected() or not path or not shutil.which('ffmpeg'):return False
    if vc.is_playing():vc.stop()
    src=discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(str(path)),volume=volume)
    vc.play(src)
    return True

async def join_user_voice(interaction):
    voice=getattr(interaction.user,'voice',None)
    if not voice or not voice.channel:return False,'Join a voice channel first.'
    current=interaction.guild.voice_client
    if current:
        await current.move_to(voice.channel)
    else:await voice.channel.connect()
    return True,f'🔊 Connected to **{voice.channel.name}**.'
