from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
OUT=Path(__file__).resolve().parent.parent/'data'/'lane_cards';OUT.mkdir(parents=True,exist_ok=True)
PIN_POS={7:(235,137),8:(305,137),9:(375,137),10:(445,137),4:(270,181),5:(340,181),6:(410,181),2:(305,225),3:(375,225),1:(340,269)}
def _font(size=22,bold=False):
    try:return ImageFont.truetype('arialbd.ttf' if bold else 'arial.ttf',size)
    except Exception:return ImageFont.load_default()
def _base(session,event,stage):
    w,h=680,760;im=Image.new('RGB',(w,h),(12,14,24));d=ImageDraw.Draw(im)
    d.rounded_rectangle((28,25,w-28,h-25),24,fill=(24,27,39),outline=(211,168,64),width=4)
    brand=getattr(session,'branding',None) or 'THE GUTTER SAINTS';d.text((w//2,50),brand[:38],font=_font(29,True),anchor='ma',fill=(245,226,172))
    lane_no=event.get('lane_no','—') if event else '—';oil=int((event.get('oil',.54) if event else .54)*100)
    d.text((w//2,84),f"LANE {lane_no} • {session.lane.upper()} • OIL {oil}% • {stage.upper()}",font=_font(17),anchor='ma',fill=(205,205,215))
    d.rounded_rectangle((185,120,495,310),20,fill=(238,226,194),outline=(120,90,55),width=3)
    standing=set((event['before'] if stage in ('approach','path','breakpoint') else event['after']) if event else session.current().standing);before=set(event['before'] if event else standing)
    for p,(x,y) in PIN_POS.items():
        if p in standing:
            d.ellipse((x-16,y-16,x+16,y+16),fill=(250,250,247),outline=(145,30,35),width=3);d.text((x,y),str(p),font=_font(14,True),anchor='mm',fill=(25,25,25))
        elif p in before:
            d.line((x-11,y-11,x+11,y+11),fill=(110,110,110),width=3);d.line((x+11,y-11,x-11,y+11),fill=(110,110,110),width=3)
    d.polygon([(220,330),(460,330),(560,665),(120,665)],fill=(184,135,72),outline=(230,196,130))
    for n in range(1,10):d.line((220+n*24,330,120+n*44,665),fill=(135,95,55),width=1)
    return im,d
def _path(d,event,progress=1.0):
    phys=event.get('physics',{});m=phys.get('metrics',{});hand=-1 if str(event.get('handedness','R')).upper().startswith('L') else 1
    miss=float(phys.get('miss',0));hook=(float(m.get('entry_angle',4))-3)*hand
    start=(340,640);breakx=340+int(hand*70+miss*26);impact=340+int(hook*18+miss*18)
    pts=[start,(start[0]+int((breakx-start[0])*.55),500),(breakx,405),(impact,345)]
    seg=max(2,int(len(pts)*progress));d.line(pts[:seg],fill=(28,28,35),width=8,joint='curve')
    x,y=pts[min(seg-1,len(pts)-1)];d.ellipse((x-11,y-11,x+11,y+11),fill=(35,35,42),outline=(245,245,250))
def lane_card(session,event=None,stage='leave'):
    im,d=_base(session,event,stage)
    if event:
        progress={'approach':.28,'path':.72,'breakpoint':.9,'impact':1.0,'leave':1.0}.get(stage,1.0);_path(d,event,progress)
        m=event.get('physics',{}).get('metrics',{})
        d.text((340,684),f"{event['bowler']} • {event.get('ball_key','hybrid').title()} • {m.get('speed','?')} mph • {m.get('revs','?')} rpm",font=_font(17,True),anchor='ma',fill=(245,245,250))
        d.text((340,711),f"Breakpoint {m.get('breakpoint','?')}' • Entry {m.get('entry_angle','?')}° • Transition {int(event.get('transition',0)*100)}%",font=_font(16),anchor='ma',fill=(245,226,172))
    path=OUT/f"lane_{id(session)}_{stage}.png";im.resize((952,1064),Image.Resampling.LANCZOS).save(path,'PNG');return path
def lane_sequence(session,event):
    return [lane_card(session,event,s) for s in ('approach','path','breakpoint','impact','leave')]
