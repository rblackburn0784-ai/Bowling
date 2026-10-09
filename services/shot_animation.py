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
SIZES=((565,1004),(480,854),(405,720))
# (stage, character frame, ball progress, impact-frame, milliseconds)
ANIMATION_SEQUENCE=(
    *(('approach',i,None,0,120) for i in range(1,6)),
    *(('path',None,p,j,100) for j,p in enumerate((.05,.12,.19,.27,.35,.44,.53,.61),1)),
    *(('breakpoint',None,p,j,105) for j,p in enumerate((.67,.73,.79,.84,.89),1)),
    ('impact',None,.93,1,115),
    ('impact',None,.97,2,130),
    ('impact',None,1.0,3,430),
)
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
    # A single shared palette avoids frame-to-frame colour flashes.
    sample=Image.new('RGB',(frames[0].width,frames[0].height))
    sample.paste(frames[0])
    # Palette is derived from a representative frame that includes the
    # character, background and equipment. Optimisation compresses still areas.
    palette=sample.quantize(colors=128,method=Image.Quantize.MEDIANCUT)
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
