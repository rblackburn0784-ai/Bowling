from pathlib import Path
import json
ASSET=Path(__file__).resolve().parent.parent/'assets'/'branding.json'
DEFAULT={"default":{"title":"THE GUTTER SAINTS","background":None},"tournaments":{}}
def load_branding():
    try:return json.loads(ASSET.read_text(encoding='utf-8'))
    except Exception:return DEFAULT
def tournament_brand(name=None):
    data=load_branding()
    if name and name in data.get('tournaments',{}):return data['tournaments'][name]
    return data.get('default',DEFAULT['default'])
