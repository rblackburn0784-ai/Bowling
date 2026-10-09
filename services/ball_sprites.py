"""Visual-only bowling ball sprites for travel, breakpoint and impact.

Uses the existing game engine path and its selected ball_key.  Never touches
session RNG or changes ball physics, game results, scores or career data.
"""
from functools import lru_cache
from pathlib import Path
import hashlib
import math
from PIL import Image, ImageDraw

BALL_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'balls'
BALL_VARIANTS = {
    'hybrid': ('hybrid_pink_black.png','hybrid_green_black.png'),
    'solid': ('solid_blue.png','solid_red.png','solid_orange.png'),
    'pearl': ('pearl_teal.png','pearl_purple.png'),
    'urethane': ('urethane_blue.png','urethane_black.png'),
    'plastic': ('plastic_cream_black.png',),
}

def resolve_ball_variant(ball_key, bowler_name=''):
    """Stable per-bowler, per-type selection; never Python salted hash()."""
    key = (ball_key or 'hybrid').casefold()
    names = BALL_VARIANTS.get(key)
    if not names:
        return None
    identity = (str(bowler_name).casefold() + ':' + key).encode('utf-8')
    number = int.from_bytes(hashlib.blake2s(identity,digest_size=4).digest(),'big')
    return names[number % len(names)]

@lru_cache(maxsize=32)
def _load(filename):
    if not filename:
        return None
    path = BALL_DIR / filename
    if not path.is_file():
        return None
    try:
        with Image.open(path) as image:
            rgba=image.convert('RGBA')
            bounds=rgba.getbbox()
            return rgba.crop(bounds) if bounds else None
    except (OSError,ValueError):
        return None

def has_ball_sprite(ball_key,bowler_name=''):
    return _load(resolve_ball_variant(ball_key,bowler_name)) is not None

def path_points(event):
    """The very same lane geometry as the previous _path() renderer."""
    phys=event.get('physics') or {}
    metrics=phys.get('metrics') or {}
    hand=-1 if str(event.get('handedness','R')).upper().startswith('L') else 1
    miss=float(phys.get('miss',0))
    hook=(float(metrics.get('entry_angle',4))-3)*hand
    start=(340,640)
    breakx=340+int(hand*70+miss*26)
    impact=340+int(hook*18+miss*18)
    return (start,(start[0]+int((breakx-start[0])*.55),500),(breakx,405),(impact,345))

def point_on_path(points,progress):
    """Arc-length interpolation so the ball tracks the guide line smoothly."""
    progress=max(0.0,min(1.0,float(progress)))
    legs=[math.hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(points,points[1:])]
    length=sum(legs)
    distance=length*progress
    for i,segment in enumerate(legs):
        if distance<=segment or i==len(legs)-1:
            t=min(1.0,max(0.0,distance/segment)) if segment else 1
            a,b=points[i],points[i+1]
            return a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t
        distance-=segment
    return points[-1]

def _ball_size(y):
    # Original 680×760 canvas: near bowler = larger, near pins = smaller.
    position=max(0.,min(1.,(640.-float(y))/(640.-345.)))
    return round(57-(57-25)*position)

def _spin_angle(event,progress):
    metrics=(event.get('physics') or {}).get('metrics') or {}
    try:revs=float(metrics.get('revs',250))
    except (ValueError,TypeError):revs=250.
    revs=max(80.,min(650.,revs))
    # Approximately 2 seconds of lane travel at 200-350 rpm; visually
    # exaggerated slightly so the holes/colour pattern visibly rotate.
    turns=(revs/60.)*2.*progress
    hand=-1 if str(event.get('handedness','R')).upper().startswith('L') else 1
    return (turns*360.*hand) % 360.

def draw_ball_sprite(canvas,event,position,progress):
    """Composite a rotated perspective sprite. True if used, else fallback."""
    filename=resolve_ball_variant(event.get('ball_key'),event.get('bowler'))
    source=_load(filename)
    if source is None:
        return False
    x,y=position
    size=_ball_size(y)
    ball=source.resize((size,size),Image.Resampling.LANCZOS)
    ball=ball.rotate(_spin_angle(event,progress),Image.Resampling.BICUBIC,expand=True)
    px=round(x-ball.width/2)
    py=round(y-ball.height/2)
    canvas.paste(ball,(px,py),ball)
    return True

def draw_lane_ball(canvas,event,progress,show_ball=True):
    """Draw the existing dark path line; overlay sprite or old circle."""
    pts=path_points(event)
    x,y=point_on_path(pts,progress)
    d=ImageDraw.Draw(canvas)
    trail=[pts[0]]
    for a,b in zip(pts,pts[1:]):
        if b[1]>=y:trail.append(b)
        else:break
    trail.append((x,y))
    d.line(trail,fill=(28,28,35),width=8,joint='curve')
    if not show_ball:
        return
    if draw_ball_sprite(canvas,event,(x,y),progress):
        return
    # Missing sprite or unknown equipment: original simple drawn-ball fallback.
    r=11
    d.ellipse((x-r,y-r,x+r,y+r),fill=(35,35,42),outline=(245,245,250))
