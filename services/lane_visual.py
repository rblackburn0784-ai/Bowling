from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / 'data' / 'lane_cards'
OUT.mkdir(parents=True, exist_ok=True)
PIN_POS={7:(235,95),8:(305,95),9:(375,95),10:(445,95),4:(270,145),5:(340,145),6:(410,145),2:(305,195),3:(375,195),1:(340,245)}

def _font(size=22,bold=False):
    try:return ImageFont.truetype('arialbd.ttf' if bold else 'arial.ttf',size)
    except Exception:return ImageFont.load_default()

def lane_card(session,event=None):
    w,h=680,760
    im=Image.new('RGB',(w,h),(12,14,24));d=ImageDraw.Draw(im)
    d.rounded_rectangle((28,25,w-28,h-25),24,fill=(24,27,39),outline=(211,168,64),width=4)
    d.text((w//2,52),'THE GUTTER SAINTS',font=_font(30,True),anchor='ma',fill=(245,226,172))
    d.text((w//2,86),f'{session.lane.upper()} LANE  •  OIL {max(0,100-int(session.ball_count/90*100))}%',font=_font(18),anchor='ma',fill=(205,205,215))
    d.rounded_rectangle((185,120,495,310),20,fill=(238,226,194),outline=(120,90,55),width=3)
    standing=set(event['after'] if event else session.current().standing)
    before=set(event['before'] if event else standing)
    for p,(x,y) in PIN_POS.items():
        if p in standing:
            d.ellipse((x-16,y-16,x+16,y+16),fill=(250,250,247),outline=(145,30,35),width=3)
            d.text((x,y),str(p),font=_font(14,True),anchor='mm',fill=(25,25,25))
        elif p in before:d.ellipse((x-10,y-10,x+10,y+10),outline=(130,130,130),width=2)
    d.polygon([(220,330),(460,330),(560,665),(120,665)],fill=(184,135,72),outline=(230,196,130))
    for n in range(1,10):
        x1=220+n*24;x2=120+n*44;d.line((x1,330,x2,665),fill=(135,95,55),width=1)
    if event:
        q=float(event.get('quality',.5)); startx=340; endx=340+int((.5-q)*120)
        d.line((startx,640,startx+int((endx-startx)*.35),520,endx,355),fill=(30,30,30),width=8)
        d.ellipse((startx-11,629,startx+11,651),fill=(35,35,42),outline=(235,235,240))
        title=f"{event['bowler']} • Frame {event['frame']} Ball {event['ball']}";result=f"{event['pins']} pin{'s' if event['pins']!=1 else ''}"
        if event.get('split_conversion'):result=f"{event.get('split_name','Split')} CONVERTED!"
        elif event.get('spare'):result='SPARE!'
        elif event['pins']==10:result='STRIKE!'
        elif event['pins']==0:result='GUTTER'
        elif event.get('leave_name'):result=event['leave_name']
        d.text((w//2,690),title,font=_font(22,True),anchor='ma',fill=(245,245,250));d.text((w//2,720),result,font=_font(24,True),anchor='ma',fill=(245,226,172))
    path=OUT/f"lane_{id(session)}.png";im.save(path,'PNG');return path
