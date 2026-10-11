"""Pre-release photographic asset validation (no generated placeholder sprites)."""
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
REQUIRED_PLATES={
    'assets/lane/gutter_saints_empty.png':(941,1672),
    'assets/cameras/overhead_empty.png':(1254,1254),
    'assets/cameras/pit_empty.png':(1254,1254),
}
REQUIRED_SPRITES=(
    *[f'assets/pins/overhead/pin_{i}.png' for i in range(1,11)],
    'assets/pins/vertical/standing.png',
    *[f'assets/pins/{v}/{f}.png' for v in ('overhead','vertical')
      for f in ('fall_left','fall_backward','fall_right','fall_forward')],
    *[f'assets/sprites/{b}/{i}.png' for b in ('the_dude','jesus') for i in range(1,6)],
    *[f'assets/balls/{b}.png' for b in (
        'hybrid_pink_black','hybrid_green_black','solid_blue','solid_red','solid_orange',
        'pearl_teal','pearl_purple','urethane_blue','urethane_black','plastic_cream_black')],
)

def validate_broadcast_assets(root=None, strict=False):
    """Return a stable diagnostic; strict=True blocks incomplete release installs."""
    root=Path(root) if root is not None else ROOT
    missing=[];wrong_dimensions=[];invalid=[]
    for relative,expected in REQUIRED_PLATES.items():
        path=root/relative
        if not path.is_file():
            missing.append(relative)
            continue
        try:
            with Image.open(path) as im:
                if im.size!=expected:wrong_dimensions.append((relative,im.size,expected))
                im.verify()
        except (OSError,ValueError):invalid.append(relative)
    for relative in REQUIRED_SPRITES:
        path=root/relative
        if not path.is_file():
            missing.append(relative)
            continue
        try:
            with Image.open(path) as im:im.verify()
        except (OSError,ValueError):invalid.append(relative)
    info={'ok':not (missing or wrong_dimensions or invalid),
          'missing':missing,'wrong_dimensions':wrong_dimensions,'invalid':invalid,
          'expected':len(REQUIRED_PLATES)+len(REQUIRED_SPRITES)}
    if strict and not info['ok']:
        raise RuntimeError('Broadcast art incomplete: '+str(info))
    return info
