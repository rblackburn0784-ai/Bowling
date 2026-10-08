"""Five-frame transparent PNG approach sprites; no changes to bowling physics."""
from functools import lru_cache
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SPRITE_DIR = ROOT / 'assets' / 'sprites'
SUPPORTED = ('the_dude', 'jesus')
FRAMES = 5
APPROACH_FRAME_SECONDS = 0.18

@lru_cache(maxsize=32)
def _image(key, frame):
    if key not in SUPPORTED or not 1 <= frame <= FRAMES:
        return None
    path = SPRITE_DIR / key / f'{frame}.png'
    if not path.is_file():
        return None
    try:
        with Image.open(path) as source:
            rgba = source.convert('RGBA')
            box = rgba.getbbox()
            return rgba.crop(box) if box else None
    except (OSError, ValueError):
        return None

def sprite_key(bowler):
    # Explicit player assignment takes precedence. Names are convenience defaults.
    explicit = getattr(bowler, 'sprite_key', None)
    if explicit == 'none':
        return None
    if explicit in SUPPORTED:
        return explicit
    name = bowler.name.casefold().replace(' ', '').replace('_','')
    if name in ('thedude','dude'):
        return 'the_dude'
    if name == 'jesus':
        return 'jesus'
    return None

def has_sequence(key):
    return key in SUPPORTED and all(_image(key,frame) is not None for frame in range(1,FRAMES+1))

def draw_approach(base, bowler, frame):
    """Return True when a sprite was composited. Coordinate system: original 680×760 lane."""
    key = sprite_key(bowler)
    if not key or not has_sequence(key):
        return False
    source = _image(key,frame)
    if source is None:
        return False
    # The bowler approaches the foul line. Keep feet anchored to the wood
    # and gently reduce scale as the bowler advances toward the distant deck.
    height = (292,279,267,254,243)[frame-1]
    width = max(1,round(source.width * height / source.height))
    pose = source.resize((width,height),Image.Resampling.LANCZOS)
    bottom = (653,641,628,617,606)[frame-1]
    x = 340 - width//2
    y = bottom-height
    base.paste(pose,(x,y),pose)
    return True
