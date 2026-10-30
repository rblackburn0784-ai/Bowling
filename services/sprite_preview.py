"""Read-only bowler preview used in Discord creation and profile UI."""
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from services.bowler_sprites import _image, sprite_label

PREVIEW_FILENAME='gs_bowler_sprite.png'

def render_sprite_preview(key):
    background=Image.new('RGBA',(640,480),(10,14,29,255))
    draw=ImageDraw.Draw(background)
    for y in range(480):
        mix=y/479
        draw.line((0,y,640,y),fill=(int(10+7*mix),int(18+13*mix),int(37+21*mix),255))
    for x in (28,32,608,612):
        draw.line((x,18,x,461),fill=(39,170,222,135),width=2)
    draw.rounded_rectangle((25,24,615,455),radius=23,outline=(43,169,220),width=3)
    draw.ellipse((185,380,455,432),fill=(20,80,115,95))
    pic=_image(key,1) if key else None
    if pic is not None:
        ratio=min(410/max(1,pic.width),340/max(1,pic.height))
        img=pic.resize((max(1,round(pic.width*ratio)),max(1,round(pic.height*ratio))),Image.Resampling.LANCZOS)
        background.alpha_composite(img,((640-img.width)//2,385-img.height))
    try:font=ImageFont.truetype('DejaVuSans-Bold.ttf',28)
    except OSError:font=ImageFont.load_default()
    label=sprite_label(key).upper()
    bounds=draw.textbbox((0,0),label,font=font)
    draw.rounded_rectangle((150,414,490,449),radius=9,fill=(7,16,29,232))
    draw.text(((640-(bounds[2]-bounds[0]))//2,415),label,font=font,fill=(229,243,255))
    out=BytesIO();background.convert('RGB').save(out,'PNG');out.seek(0)
    return out
