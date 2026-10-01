from dataclasses import dataclass

@dataclass(slots=True)
class BowlingEvent:
    type:str; bowler:str; frame:int; ball:int; pins:int; pressure:float=0.0
    team:str|None=None; leverage:str|None=None; leave:str|None=None

def classify(event):
    if event.get('split_conversion'):
        return 'seven_ten_conversion' if '7–10' in event.get('split_name','') else 'split_conversion'
    if event.get('spare'):return 'spare'
    if event.get('pins')==10:
        streak=event.get('strike_streak',1)
        if streak>=12:return 'perfect_300'
        if streak>=11:return 'perfect_watch'
        if streak>=9:return 'front_nine'
        if streak>=6:return 'six_pack'
        if streak>=3:return 'turkey'
        return 'strike'
    if event.get('pins')==0:return 'gutter'
    if event.get('split'):
        return 'seven_ten' if '7–10' in event.get('leave_name','') else 'split'
    return 'delivery'

AUDIO_MAP={'strike':'strike','spare':'spare','split':'crowd_gasp','seven_ten':'crowd_gasp','split_conversion':'crowd_roar','seven_ten_conversion':'crowd_roar','gutter':'crowd_groan','turkey':'streak','six_pack':'streak','front_nine':'tension','perfect_watch':'tension','perfect_300':'champion'}
GIF_MAP={'seven_ten_conversion':'seven_ten_conversion','split_conversion':'split_conversion','perfect_300':'perfect','perfect_watch':'perfect','front_nine':'perfect'}
