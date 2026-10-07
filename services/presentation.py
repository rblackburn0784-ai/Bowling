from dataclasses import dataclass

PRIORITY={'perfect_300':100,'seven_ten_conversion':96,'perfect_watch':94,'front_nine':90,'six_pack':84,'split_conversion':82,'turkey':75,'messenger':70,'brooklyn':66,'ringing_10':62,'stone_8':61,'stone_9':61,'pocket_7_10':80,'spare':55,'strike':50,'split':45,'gutter':40,'delivery':1}

@dataclass(slots=True)
class BowlingEvent:
    type:str; bowler:str; frame:int; ball:int; pins:int; pressure:float=0.0
    team:str|None=None; leverage:str|None=None; leave:str|None=None

def classify(event):
    candidates=[]
    if event.get('split_conversion'):candidates.append('seven_ten_conversion' if '7–10' in event.get('split_name','') else 'split_conversion')
    if event.get('spare'):candidates.append('spare')
    if event.get('pins')==10:
        streak=event.get('strike_streak',1)
        candidates.append('perfect_300' if streak>=12 else 'perfect_watch' if streak>=11 else 'front_nine' if streak>=9 else 'six_pack' if streak>=6 else 'turkey' if streak>=3 else 'strike')
    if event.get('pins')==0:candidates.append('gutter')
    if event.get('split'):candidates.append('seven_ten' if '7–10' in event.get('leave_name','') else 'split')
    candidates += event.get('carry_tags',[])
    return max(candidates or ['delivery'],key=lambda x:PRIORITY.get(x,10))

AUDIO_MAP={'strike':'strike','spare':'spare','split':'crowd_gasp','seven_ten':'crowd_gasp','split_conversion':'crowd_roar','seven_ten_conversion':'crowd_roar','gutter':'crowd_groan','turkey':'streak','six_pack':'streak','front_nine':'tension','perfect_watch':'tension','perfect_300':'champion','messenger':'crowd_roar','pocket_7_10':'crowd_gasp'}
GIF_MAP={'seven_ten_conversion':'seven_ten_conversion','split_conversion':'split_conversion','perfect_300':'perfect','perfect_watch':'perfect','front_nine':'perfect'}

def layout_policy(layout,event_kind):
    layout=(layout or 'broadcast').lower()
    if layout=='standard':return {'lane':event_kind not in ('delivery',),'media':PRIORITY.get(event_kind,0)>=50,'audio':False}
    if layout=='finals':return {'lane':True,'media':PRIORITY.get(event_kind,0)>=45,'audio':True}
    if layout=='chaos':return {'lane':True,'media':True,'audio':True}
    return {'lane':True,'media':PRIORITY.get(event_kind,0)>=55,'audio':PRIORITY.get(event_kind,0)>=50}
