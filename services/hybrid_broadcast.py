"""Hybrid Gutter Saints broadcast: full portrait lane left, two pin cameras right.

The original 941x1672 scene is rendered once (including all animated sprites).
This is ONLY a camera/layout compositor. It uses one shared source image so all
three views always reflect the same before/down/after state and animation step.

Crucially: the portrait lane is letterboxed, never stretched or cropped.
That keeps The Dude, Jesus, their ball releases and the entire house visible.
"""
from PIL import Image, ImageDraw, ImageFont

BASE_SIZE=(1000,750)      # 4:3 Discord-friendly display
SOURCE_SIZE=(941,1672)
HERO_BOX=(0,0,610,750)
OVERHEAD_BOX=(620,0,1000,365)
PIT_BOX=(620,377,1000,750)
OVERHEAD_CROP=(250,28,680,400)
PIT_CROP=(312,545,626,835)
INK=(13,15,21)
GOLD=(183,134,70)
PALE=(246,216,167)
DIVIDER=(36,31,29)

def fit_rectangle(source_size, destination):
    """Centre a whole image in a box, preserving aspect ratio exactly."""
    sw,sh=source_size
    x1,y1,x2,y2=destination
    tw,th=x2-x1,y2-y1
    if not all(v>0 for v in (sw,sh,tw,th)):
        raise ValueError('Invalid camera dimensions')
    ratio=min(tw/sw,th/sh)
    w=max(1,round(sw*ratio))
    h=max(1,round(sh*ratio))
    return (x1+(tw-w)//2,y1+(th-h)//2,w,h)

def _draw_camera(canvas,source,crop,viewport):
    """Show the full camera crop without stretching or losing any pins."""
    box=source.crop(crop)
    x,y,w,h=fit_rectangle(box.size,viewport)
    box=box.resize((w,h),Image.Resampling.LANCZOS)
    canvas.paste(box,(x,y))
    return (x,y,w,h)

def _header(canvas,box,text):
    x1,y1,x2,_=box
    d=ImageDraw.Draw(canvas)
    d.rectangle((x1,y1,x2-1,y1+26),fill=(21,22,27))
    d.line((x1+2,y1+27,x2-3,y1+27),fill=GOLD,width=2)
    d.text((x1+10,y1+7),text,fill=PALE,font=ImageFont.load_default())

def compose_hybrid_broadcast(source,output_size=BASE_SIZE):
    """Composites live lane, overhead and vertical pit into one wide image.

    source is already the fully rendered RGBA/RGB 941x1672 game scene.
    No game state, sprites, ball paths, RNG or pin geometry are mutated.
    """
    if source.size!=SOURCE_SIZE:
        raise ValueError('Hybrid camera expects the original 941x1672 scene')
    if any(v<=0 for v in output_size):
        raise ValueError('Output size must be positive')
    canvas=Image.new('RGB',BASE_SIZE,INK)
    d=ImageDraw.Draw(canvas)
    # Matte/frame outside the original portrait. Never warp the bowler
    # or stretch the lane width to fill HERO_BOX.
    hx1,hy1,hx2,hy2=HERO_BOX
    d.rectangle((hx1,hy1,hx2-1,hy2-1),fill=(16,17,22),outline=GOLD,width=2)
    hero_area=(hx1+8,hy1+10,hx2-8,hy2-10)
    lane_rect=_draw_camera(canvas,source,(0,0,*SOURCE_SIZE),hero_area)
    x,y,w,h=lane_rect
    d.rectangle((x-2,y-2,x+w+1,y+h+1),outline=(225,167,83),width=2)
    # Small side accent bars keep the matte intentional without fake
    # duplicated/stretched lane imagery behind the bowler.
    for side in (hx1+17,hx2-19):
        d.line((side,42,side,706),fill=DIVIDER,width=3)
        d.line((side,116,side,206),fill=(112,49,35),width=3)

    # Top-right overhead and bottom-right head-on camera.
    # Use camera crops on the same actual rendered pin-state image.
    for box in (OVERHEAD_BOX,PIT_BOX):
        x1,y1,x2,y2=box
        d.rectangle((x1,y1,x2-1,y2-1),fill=(12,13,18),outline=GOLD,width=2)
    oh=(OVERHEAD_BOX[0]+6,OVERHEAD_BOX[1]+35,OVERHEAD_BOX[2]-6,OVERHEAD_BOX[3]-8)
    pit=(PIT_BOX[0]+6,PIT_BOX[1]+35,PIT_BOX[2]-6,PIT_BOX[3]-8)
    _draw_camera(canvas,source,OVERHEAD_CROP,oh)
    _draw_camera(canvas,source,PIT_CROP,pit)
    _header(canvas,OVERHEAD_BOX,'PIN DECK  |  OVERHEAD')
    _header(canvas,PIT_BOX,'PIN PIT  |  FRONT')
    # One uniform resize of the *whole finished layout* for GIF fallback
    # resolutions; all ratios, sprite proportions and cameras stay aligned.
    if output_size!=BASE_SIZE:
        canvas=canvas.resize(output_size,Image.Resampling.LANCZOS)
    return canvas
