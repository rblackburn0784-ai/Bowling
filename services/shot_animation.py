"""Smooth one-upload GIFs for the Gutter Saints animated lane.

Composes the full approach -> travelling ball -> breakpoint -> impact
timeline before uploading; Discord sees ONE animation edit per shot rather
than 20 separate network roundtrips. The engine's result is never displayed
in the embed until playback has elapsed.
"""
from io import BytesIO
from PIL import Image
from services import scene_renderer

MAX_GIF_BYTES=7_500_000
# 4:3 hybrid broadcast, same lane proportions at every fallback size.
# Smaller GIFs keep the same camera layout if the upload is too large.
SIZES=((1000,750),(920,690),(840,630))
# (stage, character frame, ball progress, impact-frame, milliseconds)
# Each GIF gets a clearly visible full approach, ball flight, and *progressive*
# pin knockdown. The final frames hold settled fallen pins long enough to see
# them before the scoreboard switches to the post-delivery leave.
ANIMATION_SEQUENCE=(
    *(('approach',i,None,0,105) for i in range(1,6)),
    *(('path',None,p,j,90) for j,p in enumerate((.05,.12,.19,.27,.35,.44,.53,.61),1)),
    *(('breakpoint',None,p,j,95) for j,p in enumerate((.67,.73,.79,.84,.89),1)),
    ('impact',None,.92,1,115),  # contact, pins upright
    ('impact',None,.955,2,120), # slight tip
    ('impact',None,.98,3,145),  # half fall
    ('impact',None,1.0,4,155),  # deep fall
    ('impact',None,1.0,5,540),  # knocked-down pins held visibly
)
# discord.File uploads do not tell us when the client actually begins playing
# the GIF. Leave headroom so slower clients can see flight and pinfall before
# the result image replaces the attachment.
DISCORD_PLAYBACK_HEADROOM_SECONDS=1.5
DURATION_SECONDS=sum(item[-1] for item in ANIMATION_SEQUENCE)/1000

def _frames(session,event,size):
    frames=[]
    for stage,pose,progress,impact,milliseconds in ANIMATION_SEQUENCE:
        frame=scene_renderer.render_scene_image(session,event,stage,
            sprite_frame=pose,ball_frame=impact,ball_progress=progress,
            output_size=size)
        if frame is None:
            return None
        frames.append(frame)
    return frames

def _encode(frames):
    # A stable shared palette keeps motion smooth. Sample approach, ball
    # travel, breakpoint and impact, *not just the first approach pose*:
    # spare deliveries use a cream Plastic ball that may be absent from
    # the bowler's pose, and a first-frame-only palette can lose its colours.
    w,h=frames[0].size
    montage=Image.new('RGB',(w,h))
    sample_ids=(0,7,min(14,len(frames)-1),len(frames)-1)
    positions=((0,0),(w//2,0),(0,h//2),(w//2,h//2))
    for index,(x,y) in zip(sample_ids,positions):
        tile=frames[index].resize((w//2,h//2),Image.Resampling.LANCZOS)
        montage.paste(tile,(x,y))
    palette=montage.quantize(colors=160,method=Image.Quantize.MEDIANCUT)
    indexed=[frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in frames]
    output=BytesIO()
    indexed[0].save(output,format='GIF',save_all=True,append_images=indexed[1:],
        duration=[item[-1] for item in ANIMATION_SEQUENCE],
        optimize=True,disposal=1)
    return output.getvalue()

def animated_shot(session,event):
    """Return (BytesIO, duration_seconds), or (None,0) for legacy fallback.

    PNG assets, gameplay state, and the bowling engine RNG remain unchanged.
    Downscale only if needed to fit a normal Discord upload size.
    """
    if not scene_renderer.available():
        return None,0
    for dimensions in SIZES:
        frames=_frames(session,event,dimensions)
        if not frames:
            return None,0
        gif=_encode(frames)
        if len(gif)<=MAX_GIF_BYTES:
            return BytesIO(gif),DURATION_SECONDS
    return None,0
