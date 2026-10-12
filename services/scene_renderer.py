"""Gutter Saints cinematic lane compositor. Cosmetic-only, no bowling RNG.

A pin-free photographic lane with linked overhead/head-on pin states.
The engine's before/down/after lists are the sole source of pin truth.
Coordinates use the new 941x1672 lane for the left hero panel. The two original right pin-camera backgrounds are independent.
"""
from functools import lru_cache
from pathlib import Path
import logging

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from services import bowler_sprites, ball_sprites
from services.hybrid_broadcast import compose_hybrid_broadcast
from services.showtime import celebration_worthy

ROOT=Path(__file__).resolve().parent.parent
BG=ROOT/'assets'/'lane'/'gutter_saints_empty.png'
PINS=ROOT/'assets'/'pins'
CAMERAS=ROOT/'assets'/'cameras'
OVERHEAD_CROP=(250,28,680,400)
PIT_CROP=(312,545,626,835)
# Canonical folders: assets/lane/gutter_saints_empty.png and assets/pins/{overhead,vertical}.
OUT=ROOT/'data'/'lane_cards'
SIZE=(941,1672)
EXPORT_SIZE=(850,750)  # 17:15 hybrid; full left lane edge-to-edge, cameras right
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
# New left image: move the rack down to the actual photographed lane floor.
# The right camera positions remain the original FRONT and OVERHEAD values.
HERO_FRONT={
 7:(384,484),8:(438,484),9:(493,484),10:(547,484),
 4:(411,500),5:(465,500),6:(520,500),
 2:(438,513),3:(492,513),1:(465,526),
}
# Cosmetic-only adjustments. All phases share these proportions.
HERO_BOWLER_SCALE=1.12
HERO_PIN_SCALE=1.08
HERO_FALLEN_SCALE=1.12
OVERHEAD_PIN_SCALE=1.10
PIT_PIN_SCALE=1.14
PIT_FALLEN_SCALE=1.16
# The previously supplied resized overhead sprite pack has filenames
# out of order relative to the red numbers printed on the pin heads.
# Keep the user's existing files; resolve TRUE pin numbers at load time.
OVERHEAD_ASSET_NUMBER={
  1:1,2:4,3:5,4:2,5:3,6:10,7:6,8:7,9:9,10:8
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

# Circle centres baked into the older overhead_empty.png (5-3-2 artwork).
# The art itself is unchanged; only the in-memory camera plate is corrected.
LEGACY_OVERHEAD_CIRCLES=(
    (281,386),(470,386),(628,386),(805,386),(974,386),
    (418,602),(621,599),(837,601),(515,833),(735,833),
)

def _regulation_overhead_plate(original):
    """Heal the older 5-3-2 *painted* pin marks and draw 4-3-2-1 spots.

    Only activates if seven or more original positions are visibly dark relative
    to surrounding wood, so genuine clean decks are passed through unchanged.
    The replacement pixels are sampled from nearby timber, avoiding hard circles.
    """
    if not (original.width>=600 and original.height>=600):
        return original
    sx=original.width/1254;sy=original.height/1254
    image=original.convert('RGBA')
    rgb=image.convert('RGB')
    def lum(x,y):
        r,g,b=rgb.getpixel((max(0,min(image.width-1,round(x))),
                            max(0,min(image.height-1,round(y)))))
        return .2126*r+.7152*g+.0722*b
    old=[]
    for x,y in LEGACY_OVERHEAD_CIRCLES:
        px,py=x*sx,y*sy
        local=sum(lum(px+36*sx*dx,py+36*sy*dy)
                  for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)))/4
        if local>25 and lum(px,py)<local*.72:
            old.append((px,py))
    if len(old)<7:
        return original
    healed=image.copy()
    radius=max(14,round(28*min(sx,sy)))
    for px,py in old:
        x=round(px);y=round(py)
        left=max(0,x-radius);top=max(0,y-radius)
        right=min(image.width,x+radius+1);bottom=min(image.height,y+radius+1)
        width=right-left;height=bottom-top
        # Clone a neighbouring *unmarked* stretch of the same timber strip.
        offset=round(55*sy)
        donor_top=max(0,min(image.height-height,top+offset))
        donor=image.crop((left,donor_top,left+width,donor_top+height))
        mask=Image.new('L',(width,height));d=ImageDraw.Draw(mask)
        d.ellipse((2,2,width-3,height-3),fill=255)
        mask=mask.filter(ImageFilter.GaussianBlur(max(2,round(5*min(sx,sy)))))
        healed.paste(donor,(left,top),mask)
    d=ImageDraw.Draw(healed,'RGBA')
    for u,v in CAMERA_OVERHEAD.values():
        x=round(u*image.width);y=round(v*image.height)
        r=max(6,round(13*min(sx,sy)))
        d.ellipse((x-r-2,y-r+1,x+r+2,y+r+5),fill=(15,10,8,100))
        d.ellipse((x-r,y-r,x+r,y+r),fill=(21,17,13,185))
    return healed

@lru_cache(maxsize=2)
def _camera_background(name):
    """User-supplied square camera backgrounds, independent of left lane."""
    crop=OVERHEAD_CROP if name=='overhead' else PIT_CROP
    path=CAMERAS/('overhead_empty.png' if name=='overhead' else 'pit_empty.png')
    if path.is_file():
        try:
            with Image.open(path) as original:
                plate=original.convert('RGBA')
                return _regulation_overhead_plate(plate) if name=='overhead' else plate
        except (OSError,ValueError):
            logging.getLogger(__name__).warning('Invalid camera artwork %s',path)
    # Graceful visual fallback with visible pins, not an exception.
    width,height=crop[2]-crop[0],crop[3]-crop[1]
    fallback=Image.new('RGBA',(width,height),(62,42,30,255) if name=='overhead' else (27,25,26,255))
    logging.getLogger(__name__).warning('Missing %s camera art at %s; using fallback',name,path)
    return fallback


# Regulation ten-pin rack as seen from ABOVE, looking toward the headpin.
# Back row: 7, 8, 9, 10. Next: 4, 5, 6. Next: 2, 3. Near: 1.
# Coordinates are independent of (and cannot repair) painted-in circles in
# older 5-3-2 overhead_empty.png plates. Use the clean 4-3-2-1 camera plate.
CAMERA_OVERHEAD={
  7:(.290,.300), 8:(.430,.300), 9:(.570,.300), 10:(.710,.300),
  4:(.360,.423), 5:(.500,.423), 6:(.640,.423),
  2:(.430,.546), 3:(.570,.546),
  1:(.500,.669),
}

CAMERA_PIT={
  7:(.365,.718),8:(.455,.718),9:(.545,.718),10:(.635,.718),
  4:(.410,.748),5:(.50,.748),6:(.590,.748),
  2:(.455,.777),3:(.545,.777),1:(.50,.807),
}

def _camera_pin(base,name,p,progress=None):
    """Composite one pin on the new overhead/pit photographic plate.

    Coordinates are ratios of actual image dimensions, rather than the
    obsolete 430x372/314x290 crops. The gameplay event provides pin truth.
    """
    overhead=name=='overhead'
    view='overhead' if overhead else 'vertical'
    u,v=(CAMERA_OVERHEAD if overhead else CAMERA_PIT)[p]
    x,y=round(base.width*u),round(base.height*v)
    if overhead:
        upright=_pin(view,f'pin_{OVERHEAD_ASSET_NUMBER[p]}')
        target=(round(base.width*.082*OVERHEAD_PIN_SCALE),
                round(base.height*.112*OVERHEAD_PIN_SCALE))
    else:
        upright=_pin(view,'standing')
        y+=round(base.height*(8/1254))
        target=(round(base.width*.078*PIT_PIN_SCALE),
                round(base.height*.154*PIT_PIN_SCALE))
    if upright is None:
        # All 10 real positions remain visible even if a sprite is missing.
        if progress is None or progress<.8:
            _fallback_pin(base,x,y-35 if not overhead else y,
                          round(base.width*(.056*OVERHEAD_PIN_SCALE if overhead else .04*PIT_PIN_SCALE)))
        return
    upright=_fit(upright,*target)
    if progress is None or progress<.15:
        _paste(base,upright,x-upright.width/2,
               y-upright.height if not overhead else y-upright.height/2)
        return
    if progress<.8:
        tilt=(progress-.15)/.65
        angle=(-75 if p%2 else 75)*tilt*(1 if not overhead else -.7)
        rotated=upright.rotate(angle,Image.Resampling.BICUBIC,expand=True)
        _paste(base,rotated,x-rotated.width/2,
               y-rotated.height if not overhead else y-rotated.height/2)
        return
    fallen=_pin(view,FALLS[(p*7)%4])
    if fallen is None:
        return
    fallen=_fit(fallen,
                round(base.width*(.13*OVERHEAD_PIN_SCALE if overhead else .15*PIT_FALLEN_SCALE)),
                round(base.height*(.12*OVERHEAD_PIN_SCALE if overhead else .13*PIT_FALLEN_SCALE)))
    _paste(base,fallen,x-fallen.width/2,
           y-fallen.height*.65 if not overhead else y-fallen.height/2)

def pin_impact_progress(event, pin, impact_frame):
    """Single truth for falling-pin timing in hero, overhead and pit cameras.

    Renderer never samples RNG; all views consume the same contact_order
    (or a depth-ordered fallback for older stored match events).
    """
    down=set(event.get('down',()))
    if pin not in down:return None
    order=(event.get('physics') or {}).get('contact_order') or []
    ordered=[p for p in order if p in down]
    if set(ordered)!=down:
        ordered=sorted(down,key=lambda p:(PIN_ROWS.get(p,3),p))
    index=ordered.index(pin)
    delay=.44*index/max(1,len(ordered)-1)
    phase=max(0.,min(1.,(int(impact_frame)-1)/4.))
    return max(0.,min(1.,(phase-delay)/(1.-delay)))


PIN_ROWS={1:0,2:1,3:1,4:2,5:2,6:2,7:3,8:3,9:3,10:3}


def right_cameras(event,stage='approach',impact_frame=0):
    """Paint both new 1254px square camera backgrounds at native scale.

    Right cameras and the left hero use the SAME down/after pin results.
    No old source-image crop is used to place pin sprites.
    """
    result={}
    for name in ('overhead','pit'):
        background=_camera_background(name).copy()
        if event:
            before=set(event.get('before',[]))
            down=set(event.get('down',[])) & before
            after=set(event.get('after',[]))
            for p in sorted(before,reverse=True):
                if p not in CAMERA_OVERHEAD:
                    continue
                if stage in ('leave','victory'):
                    if p in after:
                        _camera_pin(background,name,p)
                elif stage=='impact' and p in down:
                    _camera_pin(background,name,p,
                                pin_impact_progress(event,p,impact_frame))
                else:
                    _camera_pin(background,name,p)
        result[name]=background.convert('RGB')
    return result


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

def _upright(base,view,p,front_positions=None):
    if view=='overhead':
        x,y=OVERHEAD[p]
        image=_pin(view,f'pin_{OVERHEAD_ASSET_NUMBER[p]}')
        if image:
            _paste(base,image,x-image.width/2,y-image.height/2)
        else:
            _fallback_pin(base,x,y,32)
        return
    x,y=(front_positions or FRONT)[p]
    image=_pin(view,'standing')
    if image:
        scale={1:1.08,2:1.02,3:1.02,4:.98,5:.98,6:.98,
               7:.93,8:.93,9:.93,10:.93}[p]
        if front_positions is HERO_FRONT:
            scale*=HERO_PIN_SCALE
        image=image.resize((round(image.width*scale),round(image.height*scale)),Image.Resampling.LANCZOS)
        if p%3==0:
            image=ImageEnhance.Brightness(image).enhance(.94)
        elif p%3==1:
            image=ImageEnhance.Brightness(image).enhance(1.03)
        _paste(base,image,x-image.width/2,y-image.height)
    else:
        _fallback_pin(base,x,y-25,22)

def _fall(base,view,p,progress,front_positions=None):
    x,y=(OVERHEAD if view=='overhead' else (front_positions or FRONT))[p]
    direction=FALLS[(p*7)%4]
    fallen=_pin(view,direction)
    standing=_pin(view,f'pin_{OVERHEAD_ASSET_NUMBER[p]}' if view=='overhead' else 'standing')
    if progress<.15 and standing is not None:
        _upright(base,view,p,front_positions)
        return
    if progress<.80 and standing is not None:
        if view=='vertical' and front_positions is HERO_FRONT:
            standing=standing.resize((round(standing.width*HERO_PIN_SCALE),
                                      round(standing.height*HERO_PIN_SCALE)),
                                     Image.Resampling.LANCZOS)
        # Intermediate positions rather than an instant upright -> fallen
        # transition. Works for individual pin drops on spare deliveries too.
        tilt=min(1.0,max(0.0,(progress-.15)/.65))
        angle=(-70 if p%2 else 70)*tilt*(1 if view=='vertical' else -.65)
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
    scale = (1.12*HERO_FALLEN_SCALE if front_positions is HERO_FRONT
             else 1.12 if view=='vertical' else 1.10)
    fallen = fallen.resize((round(fallen.width*scale),round(fallen.height*scale)),Image.Resampling.LANCZOS)
    if view=='vertical':
        _paste(base,fallen,x-fallen.width/2,y-fallen.height*.65)
    else:
        _paste(base,fallen,x-fallen.width/2,y-fallen.height/2)

def pin_layers(base,event,stage='approach',impact_frame=0,
               views=('overhead','vertical'),front_positions=None):
    if not event:
        return
    before=set(event.get('before',[]))
    down=set(event.get('down',[])) & before
    after=set(event.get('after',[]))
    for view in views:
        for p in sorted(before,reverse=True):
            if p not in OVERHEAD:
                continue
            if stage in ('leave','victory'):
                if p in after:
                    _upright(base,view,p,front_positions)
            elif stage=='impact' and p in down:
                _fall(base,view,p,max(0,min(1,(impact_frame-1)/4)),front_positions)
            else:
                _upright(base,view,p,front_positions)

def _bowler(base,session,event,frame):
    if not event:
        return False
    player=next((g.bowler for g in session.players if g.bowler.id==event.get('bowler_id')),None)
    if player is None:
        return False
    key=bowler_sprites.sprite_key(player)
    if not bowler_sprites.has_sequence(key):
        return False
    source=(bowler_sprites.celebration_image(key) if frame=='cheer'
            else bowler_sprites._image(key,frame))
    if source is None and frame=='cheer':
        # Correctly complete the match if the user hasn't installed cheer.png.
        source=bowler_sprites._image(key,5)
    if source is None:
        return False
    # Hold a consistent body height through release. The original scale curve
    # made Jesus appear to shrink noticeably on his fifth frame.
    heights=(851,851,851,851,851)  # 12% larger, feet remain grounded
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
    # The new lane image has an unobstructed approach. Keep feet at the
    # near edge but place the sprite slightly left of centre for the ball.
    size_index=4 if frame=='cheer' else frame-1
    pose=_fit(source,round(650*HERO_BOWLER_SCALE),heights[size_index])
    _paste(base,pose,(SIZE[0]-pose.width)/2-12,
           bottoms[size_index]-pose.height)
    return True

def _projected_ball(event,progress):
    """Map the physical lane line into the photographic camera perspective.

    Near the foul line the ball must emerge alongside the right-hand
    release of the large Dude/Jesus sprite. The underlying physics line is
    retained and smoothly regained by the breakpoint. No gameplay mutation.
    """
    progress=max(0.0,min(1.0,float(progress)))
    pts=ball_sprites.path_points(event)
    x,y=ball_sprites.point_on_path(pts,progress)
    fraction=max(0.,min(1.,(640-y)/295))
    px=470+(x-340)*(1.3-.55*fraction)
    # Follow the lowered front pin deck; only the visual projection changes.
    py=1515-994*fraction
    # Both five-pose characters carry on their right side. The original
    # centre-line projection was completely under their 760px follow-through
    # silhouette until nearly the pin deck, hiding the entire second shot.
    # Start at the visible release-side of the bowler, then ease to the
    # engine's original trajectory once the ball clears the foreground.
    if progress<=.62:
        release_offset=195.0
    elif progress>=.82:
        release_offset=0.0
    else:
        t=(progress-.62)/.20
        release_offset=195.0*(1.0-t*t*(3.0-2.0*t))
    # The old ball shrank to 25px at impact: under 6px in a 200px-wide
    # Discord preview, essentially invisible. This visual-only broadcast
    # scale keeps the spare Plastic ball and every other type readable.
    return px+release_offset,py,round(82-(82-38)*fraction)


def _ball(base,event,progress):
    px,py,size=_projected_ball(event,progress)
    name=ball_sprites.resolve_ball_variant(event.get('ball_key'),event.get('bowler'))
    source=ball_sprites._load(name)
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
                       ball_progress=None,output_size=EXPORT_SIZE,victor_id=None):
    """Compose a frame in memory for animated GIFs or still images."""
    background=_background()
    if background is None:
        return None
    im=background.copy()
    if event:
        # Left only shows head-on pins now. Overhead pins are limited to
        # the top-right camera; no "double deck" in the hero graphic.
        pin_layers(im,event,stage,ball_frame,views=('vertical',),
                   front_positions=HERO_FRONT)
        if stage in ('path','breakpoint','impact'):
            progress=ball_progress if ball_progress is not None else {'path':.45,'breakpoint':.77,'impact':.98}[stage]
            _ball(im,event,progress)
        character_event=event
        if stage=='victory' and victor_id is not None:
            character_event=dict(event,bowler_id=victor_id)
        pose=('cheer' if stage=='victory' or (stage=='leave' and celebration_worthy(event)) else
              (sprite_frame or 1) if stage=='approach' else 5)
        _bowler(im,session,character_event,pose)
    im=im.convert('RGB')
    # Hybrid: a complete, undistorted full-height lane is the hero panel,
    # with overhead / front-pin close-ups stacked alongside it.
    # Still and GIF frames share precisely the same presentation.
    if output_size[0]/output_size[1]>=1.1:
        return compose_hybrid_broadcast(im,output_size,
                                        cameras=right_cameras(event,stage,ball_frame))
    # Retain original portrait rendering for old callers/custom exports.
    return im.resize(output_size,Image.Resampling.LANCZOS)


def render_scene(session,event=None,stage='leave',sprite_frame=None,ball_frame=0,
                 ball_progress=None,victor_id=None):
    image=render_scene_image(session,event,stage,sprite_frame,ball_frame,
                             ball_progress,victor_id=victor_id)
    if image is None:
        return None
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/f'scene_{id(session)}_{stage}_{sprite_frame or 0}_{ball_frame}.png'
    image.save(path,'PNG',optimize=True)
    return path
