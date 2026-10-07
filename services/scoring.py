def score_game(frames):
    rolls=[]
    for f in frames:
        rolls.extend(f)
    total=0; i=0
    # Only score complete games/frames; live scoreboards use notation until completion.
    if len(frames)<10:return 0
    for frame in range(10):
        if rolls[i]==10:
            total += 10 + rolls[i+1] + rolls[i+2]; i+=1
        elif rolls[i]+rolls[i+1]==10:
            total += 10 + rolls[i+2]; i+=2
        else:
            total += rolls[i]+rolls[i+1]; i+=2
    return total

def frame_notation(frame):
    if not frame:return ''
    if len(frame)==1 and frame[0]==10:return 'X'
    out=[]
    for i,p in enumerate(frame):
        if p==10: out.append('X')
        elif i>0 and frame[i-1]+p==10: out.append('/')
        elif p==0: out.append('-')
        else: out.append(str(p))
    return ''.join(out)
