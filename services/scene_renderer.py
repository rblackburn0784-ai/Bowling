"""Gutter Saints cinematic lane compositor. Cosmetic-only, no bowling RNG.

A pin-free photographic lane with linked overhead/head-on pin states.
The engine's before/down/after lists are the sole source of pin truth.
Coordinates use a 941x1672 master background; Discord output is 753x1338.
"""
from functools import lru_cache
from pathlib import Path
import logging

from PIL import Image, ImageDraw, ImageEnhance
from services import bowler_sprites, ball_sprites

ROOT=Path(__file__).resolve().parent.parent
BG=ROOT/'assets'/'lane'/'gutter_saints_empty.png'
PINS=ROOT/'assets'/'pins'
# Canonical folders: assets/lane/gutter_saints_empty.png and assets/pins/{overhead,vertical}.
OUT=ROOT/'data'/'lane_cards'
SIZE=(941,1672)
EXPORT_SIZE=(753,1338)
# Real pin numbering: rearmost row 7-10, headpin 1 nearest the bowler.
OVERHEAD={
 7:(305,100),8:(410,100),9:(515,100),10:(620,100),
 4:(355,184),5:(462,184),6:(568,184),
 2:(410,269),3:(515,269),1:(462,352),
}
FRONT={
 7:(384,713),8:(438,713),9:(493,713),10:(547,713),
 4:(411,720),5:(465,720),6:(520,720),
 2:(438,727),3:(492,727),1:(465,735),
}
FALLS=('fall_left','fall_backward','fall_right','fall_forward')

def _lane_file():
    return BG if BG.is_file() else None

@lru_cache(maxsize=1)
def _background():
    path=_lane_file()
    if path is None:
        return None
    try:
        with Image.open(path) as im:
            return im.convert('RGBA').resize(SIZE,Image.Resampling.LANCZOS)
    except (OSError,ValueError):
        logging.getLogger(__name__).exception('Invalid Gutter Saints lane background: %s',path)
        return None

@lru_cache(maxsize=45)
def _pin(view,name):
    path=PINS/view/(name+'.png')
    if not path.is_file():
        return None
    try:
        with Image.open(path) as im:
            return im.convert('RGBA')
    except (OSError,ValueError):
        logging.getLogger(__name__).warning('Cannot load pin sprite %s',path)
        return None

def available():
    return _background() is not None

def _paste(base,sprite,x,y):
    if sprite is not None:
        base.alpha_composite(sprite,(round(x),round(y)))

def _fit(img,w,h):
    ratio=min(w/img.width,h/img.height)
    return img.resize((max(1,round(img.width*ratio)),max(1,round(img.height*ratio))),Image.Resampling.LANCZOS)

def _fallback_pin(base,x,y,diameter):
    r=diameter//2
    ImageDraw.Draw(base).ellipse((x-r,y-r,x+r,y+r),fill='#f1e8d0',outline='#a83233',width=2)

def _upright(base,view,p):
    if view=='overhead':
        x,y=OVERHEAD[p]
        image=_pin(view,f'pin_{p}')
        if image:
            _paste(base,image,x-image.width/2,y-image.height/2)
        else:
            _fallback_pin(base,x,y,32)
        return
    x,y=FRONT[p]
    image=_pin(view,'standing')
    if image:
        scale={1:1.08,2:1.02,3:1.02,4:.98,5:.98,6:.98,
               7:.93,8:.93,9:.93,10:.93}[p]
        image=image.resize((round(image.width*scale),round(image.height*scale)),Image.Resampling.LANCZOS)
        if p%3==0:
            image=ImageEnhance.Brightness(image).enhance(.94)
        elif p%3==1:
            image=ImageEnhance.Brightness(image).enhance(1.03)
        _paste(base,image,x-image.width/2,y-image.height)
    else:
        _fallback_pin(base,x,y-25,22)

def _fall(base,view,p,progress):
    x,y=(OVERHEAD if view=='overhead' else FRONT)[p]
    direction=FALLS[(p*7)%4]
    fallen=_pin(view,direction)
    standing=_pin(view,f'pin_{p}' if view=='overhead' else 'standing')
    if progress<.34 and standing is not None:
        _upright(base,view,p)
        return
    if progress<.68 and standing is not None:
        angle=(-32 if p%2 else 32)*(1 if view=='vertical' else -.65)
        rotated=standing.rotate(angle,Image.Resampling.BICUBIC,expand=True)
        if view=='vertical':
            _paste(base,rotated,x-rotated.width/2,y-rotated.height)
        else:
            _paste(base,rotated,x-rotated.width/2,y-rotated.height/2)
        return
    if fallen is None:
        return
    # v2.8.5c: slightly enlarge settled fallen sprites only.
    # Upright pins and the intermediate lean retain their original sizing.
    scale = 1.12 if view=='vertical' else 1.10
    fallen = fallen.resize((round(fallen.width*scale),round(fallen.height*scale)),Image.Resampling.LANCZOS)
    if view=='vertical':
        _paste(base,fallen,x-fallen.width/2,y-fallen.height*.65)
    else:
        _paste(base,fallen,x-fallen.width/2,y-fallen.height/2)

def pin_layers(base,event,stage='approach',impact_frame=0):
    if not event:
        return
    before=set(event.get('before',[]))
    down=set(event.get('down',[])) & before
    after=set(event.get('after',[]))
    for view in ('overhead','vertical'):
        for p in sorted(before,reverse=True):
            if p not in OVERHEAD:
                continue
            if stage=='leave':
                if p in after:
                    _upright(base,view,p)
            elif stage=='impact' and p in down:
                _fall(base,view,p,max(0,min(1,(impact_frame-1)/2)))
            else:
                _upright(base,view,p)

def _bowler(base,session,event,frame):
    if not event:
        return False
    player=next((g.bowler for g in session.players if g.bowler.id==event.get('bowler_id')),None)
    if player is None:
        return False
    key=bowler_sprites.sprite_key(player)
    if not bowler_sprites.has_sequence(key):
        return False
    source=bowler_sprites._image(key,frame)
    if source is None:
        return False
    # Hold a consistent body height through release. The original scale curve
    # made Jesus appear to shrink noticeably on his fifth frame.
    heights=(760,760,760,760,760)
    bottoms=(1660,1655,1650,1645,1640)
    if key=='jesus' and frame==2:
        # Source frame 2 was rendered without a ball. Overlay one from the
        # existing black urethane art at the low right-hand carry position.
        # This only changes the visual layer; ball physics are unchanged.
        source=source.copy()
        ball=ball_sprites._load('urethane_black.png')
        if ball is not None:
            diameter=90
            held=_fit(ball,diameter,diameter)
            source.alpha_composite(held,(source.width-held.width-4,
                                         round(source.height*.59)-held.height//2))
    pose=_fit(source,650,heights[frame-1])
    _paste(base,pose,(SIZE[0]-pose.width)/2,bottoms[frame-1]-pose.height)
    return True

def _ball(base,event,progress):
    pts=ball_sprites.path_points(event)
    x,y=ball_sprites.point_on_path(pts,progress)
    fraction=max(0.,min(1.,(640-y)/295))
    px=470+(x-340)*(1.3-.55*fraction)
    py=1535-795*fraction
    name=ball_sprites.resolve_ball_variant(event.get('ball_key'),event.get('bowler'))
    source=ball_sprites._load(name)
    size=round(71-(71-25)*fraction)
    # Keep small/distance balls readable against the glossy wooden lane.
    # The plastic spare ball is cream-coloured and otherwise blends into it.
    r=size/2
    d=ImageDraw.Draw(base)
    d.ellipse((px-r-3,py-r-1,px+r+3,py+r+5),
              fill=(19,14,19,205),outline=(236,225,203,220),width=1)
    if source:
        sprite=_fit(source,size,size).rotate(ball_sprites._spin_angle(event,progress),Image.Resampling.BICUBIC,expand=True)
        _paste(base,sprite,px-sprite.width/2,py-sprite.height/2)
    else:
        d.ellipse((px-r,py-r,px+r,py+r),fill='#251d35',outline='#faf1ff',width=2)

def render_scene_image(session,event=None,stage='leave',sprite_frame=None,ball_frame=0,
                       ball_progress=None,output_size=EXPORT_SIZE):
    """Compose a frame in memory for animated GIFs or still images."""
    background=_background()
    if background is None:
        return None
    im=background.copy()
    if event:
        pin_layers(im,event,stage,ball_frame)
        # The large approach pose formerly covered the travelling ball;
        # draw the bowler first, then composite the released ball above it.
        _bowler(im,session,event,(sprite_frame or 1) if stage=='approach' else 5)
        if stage in ('path','breakpoint','impact'):
            progress=ball_progress if ball_progress is not None else {'path':.45,'breakpoint':.77,'impact':.98}[stage]
            _ball(im,event,progress)
    return im.convert('RGB').resize(output_size,Image.Resampling.LANCZOS)


def render_scene(session,event=None,stage='leave',sprite_frame=None,ball_frame=0,ball_progress=None):
    image=render_scene_image(session,event,stage,sprite_frame,ball_frame,ball_progress)
    if image is None:
        return None
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/f'scene_{id(session)}_{stage}_{sprite_frame or 0}_{ball_frame}.png'
    image.save(path,'PNG',optimize=True)
    return path
