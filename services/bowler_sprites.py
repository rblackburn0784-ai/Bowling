"""Five-frame transparent PNG approach sprites; no changes to bowling physics."""
from functools import lru_cache
import re
from pathlib import Path
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
SPRITE_DIR = ROOT / 'assets' / 'sprites'
SUPPORTED = ('the_dude', 'jesus')
MAX_CHOICES=20
FRAMES = 5
APPROACH_FRAME_SECONDS = 0.18

def installed_sprites():
    return _discover_installed(str(SPRITE_DIR.resolve()))

@lru_cache(maxsize=8)
def _discover_installed(folder):
    directory=Path(folder)
    if not directory.is_dir():return ()
    names=sorted(x.name for x in directory.iterdir()
                 if x.is_dir() and re.fullmatch(r'[a-z][a-z0-9_]{0,39}',x.name))
    ordered=list(SUPPORTED)+[x for x in names if x not in SUPPORTED]
    return tuple(k for k in ordered if k in names and has_sequence(k))[:MAX_CHOICES]

def sprite_label(key):
    return {'the_dude':'The Dude','jesus':'Jesus'}.get(
        key,key.replace('_',' ').title() if key else 'Standard / Unassigned')

@lru_cache(maxsize=32)
def _image(key, frame):
    if (not re.fullmatch(r'[a-z][a-z0-9_]{0,39}',str(key))
            or not (SPRITE_DIR/key).is_dir() or not 1 <= frame <= FRAMES):
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

def _remove_flattened_checker(image):
    """Recover transparency when old cheer PNGs baked in a grey checkerboard.

    Only applies to *opaque* images whose corners look like the supplied
    light-neutral transparency preview. Actual transparent PNGs and opaque
    photos without these corners are not altered. Cached at load time.
    """
    rgba=image.convert('RGBA')
    if rgba.getchannel('A').getextrema()[0] < 255:
        return rgba
    points=((0,0),(rgba.width-1,0),(0,rgba.height-1),
            (rgba.width-1,rgba.height-1))
    corners=[rgba.getpixel(p)[:3] for p in points]
    if not all(min(pixel)>=200 and max(pixel)-min(pixel)<=12
               for pixel in corners):
        return rgba
    r,g,b=rgba.split()[:3]
    highest=ImageChops.lighter(r,ImageChops.lighter(g,b))
    lowest=ImageChops.darker(r,ImageChops.darker(g,b))
    spread=ImageChops.subtract(highest,lowest)
    light=lowest.point(lambda v:255 if v>=204 else 0)
    neutral=spread.point(lambda v:255 if v<=9 else 0)
    alpha=ImageChops.invert(ImageChops.multiply(light,neutral))
    rgba.putalpha(alpha)
    return rgba


@lru_cache(maxsize=8)
def celebration_image(key):
    """Optional victory pose from assets/sprites/<character>/cheer.png.

    Missing artwork must not crash or block game completion. Keeps the
    numbered five-frame approach animations entirely unchanged.
    """
    if not key or not re.fullmatch(r'[a-z][a-z0-9_]{0,39}',str(key)):
        return None
    path=SPRITE_DIR/key/'cheer.png'
    if not path.is_file():
        return None
    try:
        with Image.open(path) as source:
            rgba=_remove_flattened_checker(source)
            bbox=rgba.getbbox()
            return rgba.crop(bbox) if bbox else None
    except (OSError, ValueError):
        return None


def sprite_key(bowler):
    # Explicit player assignment takes precedence. Names are convenience defaults.
    explicit = getattr(bowler, 'sprite_key', None)
    if explicit == 'none':
        return None
    if explicit in installed_sprites():
        return explicit
    name = bowler.name.casefold().replace(' ', '').replace('_','')
    if name in ('thedude','dude'):
        return 'the_dude'
    if name == 'jesus':
        return 'jesus'
    return None

def has_sequence(key):
    return bool(key and re.fullmatch(r'[a-z][a-z0-9_]{0,39}',str(key)) and
                (SPRITE_DIR/key).is_dir() and all(_image(key,frame) is not None for frame in range(1,FRAMES+1)))

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

def assign_match_sprites(bowlers):
    """Give every unassigned match bowler a presentation-only character.

    Stable per match: first unassigned uses The Dude, second Jesus, then
    alternates. Explicit selections including 'none' are never overwritten.
    Existing named TheDude/Jesus take priority. This changes only in-memory
    bowler objects, not the SQLite roster or player attributes.
    """
    players = list(bowlers)
    occupied = set()
    for bowler in players:
        character = sprite_key(bowler)
        if character in installed_sprites():
            occupied.add(character)
    for bowler in players:
        if getattr(bowler, 'sprite_key', None) is not None:
            continue
        natural = sprite_key(bowler)
        if natural:
            bowler.sprite_key = natural
            continue
        playable = installed_sprites()
        choice = next((key for key in playable if key not in occupied),None)
        if choice is None and playable:
            choice=playable[sum(1 for p in players[:players.index(bowler)]
                               if getattr(p,'sprite_key',None) in playable) % len(playable)]
        bowler.sprite_key=choice
        if choice:occupied.add(choice)
    return {getattr(bowler, 'id',idx):sprite_key(bowler)
            for idx,bowler in enumerate(players)}
