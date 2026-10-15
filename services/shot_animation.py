"""Single-upload motion and optional read-only broadcast replay.
The replay is rendered from the original, recorded event; it does not bowl again.
"""
from io import BytesIO
from PIL import Image
from services import scene_renderer
from services.showtime_graphics import transition_ribbon
from services.showtime import is_finals

MAX_GIF_BYTES=7_500_000
SIZES=((850,750),(765,675),(680,600))
ANIMATION_SEQUENCE=(
    *(('approach',i,None,0,105) for i in range(1,6)),
    *(('path',None,p,j,90) for j,p in enumerate((.05,.12,.19,.27,.35,.44,.53,.61),1)),
    *(('breakpoint',None,p,j,95) for j,p in enumerate((.67,.73,.79,.84,.89),1)),
    ('impact',None,.92,1,115),
    ('impact',None,.955,2,120),
    ('impact',None,.98,3,145),
    ('impact',None,1.0,4,155),
    ('impact',None,1.0,5,540),
)
DISCORD_PLAYBACK_HEADROOM_SECONDS=0.30
DURATION_SECONDS=sum(item[-1] for item in ANIMATION_SEQUENCE)/1000
REPLAY_SEQUENCE=(
    ('breakpoint',None,.79,3,250),
    ('breakpoint',None,.84,4,270),
    ('breakpoint',None,.89,5,290),
    ('impact',None,.92,1,340),
    ('impact',None,.955,2,420),
    ('impact',None,.98,3,480),
    ('impact',None,1.0,4,510),
    ('impact',None,1.0,5,700),
)
REPLAY_DURATION_SECONDS=sum(x[-1] for x in REPLAY_SEQUENCE)/1000

def _frames(session,event,size,sequence=ANIMATION_SEQUENCE):
    frames=[]
    for stage,pose,progress,impact,_ in sequence:
        frame=scene_renderer.render_scene_image(session,event,stage,
            sprite_frame=pose,ball_frame=impact,ball_progress=progress,
            output_size=size)
        if frame is None:
            return None
        frames.append(transition_ribbon(frame,stage,is_finals(session)))
    return frames

def _encode(frames,sequence=ANIMATION_SEQUENCE):
    w,h=frames[0].size
    montage=Image.new('RGB',(w,h))
    sample_ids=(0,min(3,len(frames)-1),min(5,len(frames)-1),len(frames)-1)
    positions=((0,0),(w//2,0),(0,h//2),(w//2,h//2))
    for index,(x,y) in zip(sample_ids,positions):
        tile=frames[index].resize((w//2,h//2),Image.Resampling.LANCZOS)
        montage.paste(tile,(x,y))
    palette=montage.quantize(colors=160,method=Image.Quantize.MEDIANCUT)
    indexed=[frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in frames]
    output=BytesIO()
    indexed[0].save(output,format='GIF',save_all=True,append_images=indexed[1:],
        duration=[item[-1] for item in sequence],optimize=True,disposal=2)
    return output.getvalue()

def _render(session,event,sequence):
    if not scene_renderer.available():return None,0
    for size in SIZES:
        frames=_frames(session,event,size,sequence)
        if not frames:return None,0
        content=_encode(frames,sequence)
        if len(content)<=MAX_GIF_BYTES:
            return BytesIO(content),sum(row[-1] for row in sequence)/1000
    return None,0

def animated_shot(session,event):
    return _render(session,event,ANIMATION_SEQUENCE)

def replay_shot(session,event,slow_motion=True):
    sequence=REPLAY_SEQUENCE if slow_motion else ANIMATION_SEQUENCE[14:]
    return _render(session,event,sequence)
