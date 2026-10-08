"""Unified lane + scoreboard broadcast panel for Discord."""
from PIL import Image,ImageDraw,ImageFont
from services.lane_visual import lane_card
from services.commentary import event_text
from pathlib import Path

def _font(size,bold=False):
 for path in (('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'):
  try:return ImageFont.truetype(path,size)
  except OSError:pass
 return ImageFont.load_default()

def _wrap(draw,text,font,width):
 words=str(text).split();lines=[];line=''
 for word in words:
  candidate=(line+' '+word).strip()
  if line and draw.textbbox((0,0),candidate,font=font)[2]>width:
   lines.append(line);line=word
  else:line=candidate
 if line:lines.append(line)
 return lines

def broadcast_card(session,event=None,stage='leave'):
 reveal=stage=='leave'
 lane=Image.open(lane_card(session,event,stage)).convert('RGB')
 # Display a single unified broadcast: lane on the left, live match data on the right.
 width,height=1570,1064
 im=Image.new('RGB',(width,height),'#101724')
 im.paste(lane,(0,0))
 d=ImageDraw.Draw(im)
 left=972;right=1542
 d.rounded_rectangle((left,30,right,1034),radius=22,fill='#1c2838',outline='#c8a15a',width=3)
 d.text((1000,57),'GUTTER SAINTS',font=_font(30,True),fill='#eacb83')
 d.text((1000,108),'LIVE MATCH CENTRE',font=_font(20,True),fill='#8de0e7')
 d.line((995,152,1520,152),fill='#516478',width=2)
 d.text((1000,171),f"{session.lane.title()} lane  |  Ball {getattr(session,'ball_count',0)}",font=_font(19),fill='#cbd5e1')
 y=222
 cards=session.card() if reveal else {};scores=session.scores() if reveal else {}
 for p in session.players[:6]:
  name=p.bowler.name
  for j,line in enumerate(_wrap(d,name,_font(22,True),505)[:2]):
   d.text((1000,y),line,font=_font(22,True),fill='#ffffff');y+=29
  frames=cards.get(name,[])
  for line in _wrap(d,'  '.join(f"{i+1}:{v}" for i,v in enumerate(frames)),_font(17),505)[:3]:
   d.text((1000,y),line,font=_font(17),fill='#cbd5e1');y+=24
  if reveal and p.complete:d.text((1000,y),f"FINAL  {scores.get(name,0)}",font=_font(20,True),fill='#8de0e7');y+=27
  y+=23
  if y>760:break
 d.line((995,795,1520,795),fill='#516478',width=2)
 d.text((1000,815),'LAST DELIVERY' if reveal else 'BALL IN MOTION',font=_font(19,True),fill='#eacb83')
 if event and reveal:
  summary=f"{event.get('bowler','')}  |  Frame {event.get('frame','?')}  |  Ball {event.get('ball','?')}  |  {event.get('pins',0)} pins"
  commentary=event_text(session,event)
  y=852
  for text in (summary,commentary):
   for line in _wrap(d,text,_font(18),505)[:3]:
    d.text((1000,y),line,font=_font(18),fill='#e6edf6');y+=27
 else:d.text((1000,858),'Watch the pins — result pending' if event else 'Awaiting the opening delivery',font=_font(18),fill='#e6edf6')
 from io import BytesIO
 buf=BytesIO();im.save(buf,format='PNG',optimize=True);buf.seek(0)
 return buf
