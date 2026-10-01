import json,random
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent/'assets'
DEFAULTS={'strike':[],'spare':[],'split':[],'gutter':[],'entrance':[],'crowd_hype':[],'crowd_groan':[],'perfect':[],'tournament':[],'award':[]}

def _config():
    p=BASE/'media.json'
    if not p.exists(): return DEFAULTS
    try:
        d=json.loads(p.read_text(encoding='utf8')); return {**DEFAULTS,**d}
    except Exception:return DEFAULTS

def pick(kind,rng=None):
    vals=_config().get(kind,[])
    return (rng or random).choice(vals) if vals else None
