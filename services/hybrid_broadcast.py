"""Hybrid presentation: uncropped, pixel-filled hero lane; independent pin cameras.

The left lane's 941×1672 aspect ratio is preserved in a 422×750 panel.
No matte/letterbox padding, scene distortion, or missing edge artwork.
All three cameras read the same shot event, but have separate backgrounds.
"""
from PIL import Image,ImageDraw,ImageFont

SOURCE_SIZE=(941,1672)
BASE_SIZE=(850,750)
HERO_BOX=(0,0,422,750)
OVERHEAD_BOX=(432,0,850,365)
PIT_BOX=(432,377,850,750)
# Legacy crops retained for backward compatibility only.
OVERHEAD_CROP=(250,28,680,400)
PIT_CROP=(312,545,626,835)
INK=(13,15,21)
GOLD=(183,134,70)
PALE=(246,216,167)

def fit_rectangle(source_size,destination):
    """Return undistorted contained rectangle; useful for compatibility."""
    sw,sh=source_size
    x1,y1,x2,y2=destination
    tw,th=x2-x1,y2-y1
    if not all(x>0 for x in (sw,sh,tw,th)):
        raise ValueError('Invalid camera dimensions')
    scale=min(tw/sw,th/sh)
    w=max(1,round(sw*scale))
    h=max(1,round(sh*scale))
    return x1+(tw-w)//2,y1+(th-h)//2,w,h

def _camera_cover(source,viewport):
    """Fill the camera viewport without distorting sprites or the scene."""
    x1,y1,x2,y2=viewport
    w,h=x2-x1,y2-y1
    if w<=0 or h<=0:
        raise ValueError('Invalid camera viewport')
    sw,sh=source.size
    desired=w/h
    have=sw/sh
    if have>desired:
        crop_width=round(sh*desired)
        left=(sw-crop_width)//2
        area=(left,0,left+crop_width,sh)
    else:
        crop_height=round(sw/desired)
        top=(sh-crop_height)//2
        area=(0,top,sw,top+crop_height)
    return source.crop(area).resize((w,h),Image.Resampling.LANCZOS)

def _header(canvas,box,label):
    x1,y1,x2,_=box
    draw=ImageDraw.Draw(canvas)
    draw.rectangle((x1,y1,x2-1,y1+27),fill=(20,20,25))
    draw.line((x1+2,y1+28,x2-3,y1+28),fill=GOLD,width=2)
    draw.text((x1+10,y1+8),label,fill=PALE,font=ImageFont.load_default())

def compose_hybrid_broadcast(source,output_size=BASE_SIZE,cameras=None):
    """Use supplied left lane and independent right-hand camera images.

    Each region is fitted without changing pixel aspect ratio. The full hero
    image remains visible, edge-to-edge, with zero unused space in HERO_BOX.
    """
    if source.size!=SOURCE_SIZE:
        raise ValueError('Hybrid camera expects the 941x1672 hero lane')
    if len(output_size)!=2 or any(x<=0 for x in output_size):
        raise ValueError('Output size must be positive')
    result=Image.new('RGB',BASE_SIZE,INK)
    hero_width=HERO_BOX[2]-HERO_BOX[0]
    hero_height=HERO_BOX[3]-HERO_BOX[1]
    hero=source.convert('RGB').resize((hero_width,hero_height),Image.Resampling.LANCZOS)
    # 422/750 vs 941/1672 differs by less than 0.03%; rounding only.
    result.paste(hero,HERO_BOX[:2])
    for box,name in ((OVERHEAD_BOX,'overhead'),(PIT_BOX,'pit')):
        x1,y1,x2,y2=box
        if cameras is not None:
            camera=cameras[name].convert('RGB')
        else:
            legacy=OVERHEAD_CROP if name=='overhead' else PIT_CROP
            camera=source.convert('RGB').crop(legacy)
        region=(x1+4,y1+31,x2-4,y2-5)
        result.paste(_camera_cover(camera,region),region[:2])
        draw=ImageDraw.Draw(result)
        draw.rectangle((x1,y1,x2-1,y2-1),outline=GOLD,width=2)
    _header(result,OVERHEAD_BOX,'PIN DECK  |  OVERHEAD')
    _header(result,PIT_BOX,'PIN PIT  |  FRONT')
    if output_size!=BASE_SIZE:
        return result.resize(output_size,Image.Resampling.LANCZOS)
    return result
