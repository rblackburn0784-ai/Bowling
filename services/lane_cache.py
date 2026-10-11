"""Delete only stale generated lane images; never touch user PNG assets."""
import time
from pathlib import Path

def purge_old_lane_cards(root=None,older_than_days=14):
    if root is None:root=Path(__file__).resolve().parents[1]/'data'/'lane_cards'
    else:root=Path(root)
    if not root.is_dir():return 0
    cutoff=time.time()-older_than_days*86400
    removed=0
    for path in root.iterdir():
        if (path.is_file() and path.name.startswith(('scene_','lane_'))
                and path.suffix.lower()=='.png' and path.stat().st_mtime<cutoff):
            path.unlink();removed+=1
    return removed
