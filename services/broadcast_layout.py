"""Wide broadcast composition for Discord's height-constrained inline image preview.

Keep the original 941x1672 painted lane and sprite coordinates unchanged.
After the full scene is rendered, use camera crops to show the same
animation in three larger panels:
  - live overhead pin deck
  - head-on pit (including the actual pin impact)
  - full-width action lane containing the bowler and most ball travel

This is presentation-only, with no impact on ball physics or pin states.
"""
from PIL import Image, ImageDraw, ImageFont

CANVAS_RATIO = 1.125
BASE_SIZE = (900,800)
SOURCE_SIZE = (941,1672)

def _crop_resize(source, bbox, target):
    return source.crop(bbox).resize(target, Image.Resampling.LANCZOS)

def compose_broadcast(scene, output_size=BASE_SIZE):
    """Make a compact 9:8 broadcast from an already-composited portrait scene."""
    w,h = output_size
    if w <= 0 or h <= 0:
        raise ValueError("Invalid broadcast dimensions")
    # Use a master coordinate system for deterministic crops in all GIF sizes.
    master=Image.new('RGB',BASE_SIZE,(15,17,23))
    d=ImageDraw.Draw(master)
    # Source pin locations are unchanged: the cameras are crops of the actual
    # composited scene, so the deck and pit never disagree about knocked pins.
    upper_y=33
    inset_h=208
    gap=8
    left_w=(900-gap)//2
    right_x=left_w+gap
    overhead=_crop_resize(scene,(192,22,744,418),(left_w,inset_h))
    headon=_crop_resize(scene,(260,577,695,864),(900-right_x,inset_h))
    master.paste(overhead,(0,upper_y))
    master.paste(headon,(right_x,upper_y))
    # The full-width action camera doubles the apparent ball and character
    # width versus a 1:1.78 portrait limited to ~350px on Discord.
    lower_y=250
    live_lane=_crop_resize(scene,(0,825,941,1672),(900,800-lower_y))
    master.paste(live_lane,(0,lower_y))
    # Restrained neon house presentation. Titles remain legible at 400px wide.
    d=ImageDraw.Draw(master)
    d.rectangle((0,0,899,31), fill=(17,18,24))
    d.rectangle((0,32,899,33), fill=(202,147,66))
    d.text((15,10),"THE GUTTER SAINTS    /    OVERHEAD CAM",fill=(252,220,162),font=ImageFont.load_default())
    d.text((right_x+12,10),"PIN PIT CAM",fill=(252,220,162),font=ImageFont.load_default())
    d.rectangle((0,242,899,249),fill=(13,14,20))
    d.rectangle((0,242,899,244),fill=(192,132,58))
    if output_size!=BASE_SIZE:
        return master.resize(output_size,Image.Resampling.LANCZOS)
    return master
