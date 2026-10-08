"""Premium newspaper artwork generated entirely from archived issue text."""
import io,textwrap
from PIL import Image,ImageDraw,ImageFont

def _font(size,bold=False):
 names=['DejaVuSans-Bold.ttf','DejaVuSans.ttf'] if bold else ['DejaVuSans.ttf']
 for name in names:
  try:return ImageFont.truetype(name,size)
  except OSError:pass
 return ImageFont.load_default()

def render_issue(issue):
 w,h=1200,1550
 image=Image.new('RGB',(w,h),'#f1ead7')
 d=ImageDraw.Draw(image)
 ink='#17243a';muted='#59657a';accent='#9d3e31'
 d.rectangle((0,0,w,28),fill=ink)
 d.text((70,63),'THE GUTTER SAINTS',font=_font(58,True),fill=ink)
 d.text((72,142),'THE WEEKLY BOWLING GAZETTE',font=_font(24,True),fill=accent)
 d.line((70,195,1130,195),fill=ink,width=5)
 d.text((72,218),f"SEASON EDITION  /  ISSUE {issue['issue_no']:03d}",font=_font(19,True),fill=muted)
 d.text((740,218),f"{issue['week_start']}  —  {issue['week_end']}",font=_font(19),fill=muted)
 d.line((70,265,1130,265),fill=ink,width=2)
 headline=issue['headline']
 y=294
 for line in textwrap.wrap(headline,width=28)[:3]:
  d.text((72,y),line,font=_font(47,True),fill=ink)
  y+=63
 y+=30
 d.rectangle((72,y,1128,y+11),fill=accent);y+=45
 d.text((72,y),'THIS WEEK ON THE LANES',font=_font(25,True),fill=accent);y+=52
 for raw in issue['body'].splitlines():
  if y>h-175:break
  for line in textwrap.wrap(raw,width=68,break_long_words=False) or ['']:
   d.text((80,y),line,font=_font(23),fill=ink)
   y+=37
  y+=12
 d.line((70,h-130,1130,h-130),fill=ink,width=2)
 d.text((72,h-103),'RESULTS  •  RIVALRIES  •  CHAMPIONSHIPS',font=_font(19,True),fill=muted)
 d.text((880,h-103),'GUTTER SAINTS',font=_font(19,True),fill=accent)
 buf=io.BytesIO();image.save(buf,format='PNG',optimize=True);buf.seek(0)
 return buf
