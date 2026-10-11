"""Conventional ten-pin scoring and safe 10-frame input validation.

USBC / IBF scoring: strike + next two deliveries, spare + next one;
the tenth awards two bonus balls for a strike or one for a spare.
"""
def _valid_complete(frames):
    if len(frames)!=10:
        return False
    for index,frame in enumerate(frames):
        if not isinstance(frame,(list,tuple)):
            raise ValueError('Frame rolls must be a sequence')
        if any(type(pin) is not int or not 0<=pin<=10 for pin in frame):
            raise ValueError(f'Frame {index+1} has a non-integer or illegal pin count')
        if index<9:
            if len(frame)==1 and frame[0]==10:
                continue
            if len(frame)!=2 or frame[0]==10 or sum(frame)>10:
                raise ValueError(f'Invalid frame {index+1}: {frame}')
        else:
            if not frame:
                return False
            first=frame[0]
            if first==10:
                if len(frame)<3:return False
                if len(frame)!=3 or (frame[1]<10 and frame[1]+frame[2]>10):
                    raise ValueError(f'Invalid tenth-frame strike bonuses: {frame}')
            else:
                if len(frame)<2:return False
                if frame[0]+frame[1]>10:
                    raise ValueError(f'Invalid tenth-frame pin count: {frame}')
                spare=frame[0]+frame[1]==10
                expected=3 if spare else 2
                if len(frame)<expected:return False
                if len(frame)!=expected:
                    raise ValueError(f'Invalid tenth-frame bonus count: {frame}')
    return True


def score_game(frames):
    """Score a complete conventional game; incomplete games return 0.

    Reject impossible completed games rather than crediting invalid strikes,
    spares, or extra rolls. All outputs are in the legal 0–300 range.
    """
    if len(frames)<10:
        return 0
    if len(frames)!=10:
        raise ValueError('A conventional bowling game has exactly ten frames')
    if not _valid_complete(frames):
        return 0
    rolls=[pins for frame in frames for pins in frame]
    total=0
    index=0
    for _ in range(10):
        if rolls[index]==10:
            total+=10+rolls[index+1]+rolls[index+2]
            index+=1
        elif rolls[index]+rolls[index+1]==10:
            total+=10+rolls[index+2]
            index+=2
        else:
            total+=rolls[index]+rolls[index+1]
            index+=2
    if not 0<=total<=300:
        raise ValueError('Score outside legal ten-pin range')
    return total


def frame_notation(frame):
    if not frame:return ''
    if len(frame)==1 and frame[0]==10:return 'X'
    out=[]
    for index,pins in enumerate(frame):
        if pins==10:out.append('X')
        elif index>0 and frame[index-1]+pins==10:out.append('/')
        elif pins==0:out.append('-')
        else:out.append(str(pins))
    return ''.join(out)
