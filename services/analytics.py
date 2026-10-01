from services.scoring import score_game

LEAVES = {
    frozenset({7,10}): '7–10 Split',
    frozenset({4,6,7,10}): 'Big Four',
    frozenset({4,6,7,9,10}): 'Greek Church',
    frozenset({4,6}): 'Baby Split',
    frozenset({3,10}): 'Baby Split',
    frozenset({2,7}): 'Baby Split',
    frozenset({2,10}): 'Big Split',
    frozenset({3,7}): 'Big Split',
    frozenset({5,7}): 'Woolworth',
    frozenset({5,10}): 'Woolworth',
    frozenset({2,4,5,8}): 'Bucket',
    frozenset({3,5,6,9}): 'Bucket',
    frozenset({1,2,4,7}): 'Washout',
    frozenset({1,3,6,10}): 'Washout',
    frozenset({5,7,10}): 'Lily / Sour Apple',
    frozenset({2,8}): 'Sleeper',
    frozenset({3,9}): 'Sleeper',
    frozenset({1,5,7,10}): 'Sour Apple',
}

def named_leave(pins):
    s=frozenset(pins)
    if s in LEAVES:return LEAVES[s]
    if len(s)==1:return f'Single {next(iter(s))}-pin'
    return None

def frame_flags(frames):
    strikes=spares=splits=split_conversions=turkeys=0
    streak=0; longest=0; opens=0
    split_frames=set()
    for idx,f in enumerate(frames[:10]):
        if not f:continue
        if f[0]==10:
            strikes+=1;streak+=1;longest=max(longest,streak)
            if streak>=3:turkeys+=1
        else:
            streak=0
            if len(f)>=2 and sum(f[:2])==10:spares+=1
            else:opens+=1
    if len(frames)>=10 and frames[9]:
        strikes += sum(1 for x in frames[9][1:] if x==10)
    return dict(strikes=strikes,spares=spares,turkeys=turkeys,longest_streak=longest,clean=int(opens==0),opens=opens)

def player_summary(player):
    score=score_game(player.frames)
    x=frame_flags(player.frames)
    splits=len(getattr(player,'split_frames',set()))
    conv=len(getattr(player,'split_conversions',set()))
    pocket_frames=sum(1 for f in player.frames[:10] if f and (f[0]==10 or (len(f)>=2 and sum(f[:2])==10)))
    x.update(score=score,splits=splits,split_conversions=conv,pocket_pct=pocket_frames/10*100)
    return x
