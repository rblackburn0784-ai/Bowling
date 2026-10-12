"""Cinematic match opening and final cards. Separate from the fixed camera layout.

Pillow-only; intentionally independent of the lane PNGs and character sprites.
"""
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from services.showtime import group_rosters, is_finals

WIDTH, HEIGHT = 850, 750
BG = (13, 18, 31)
INK = (240, 237, 226)
GOLD = (229, 184, 105)
CYAN = (113, 208, 218)


def _font(size, bold=False):
    names = ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
             'DejaVuSans-Bold.ttf') if bold else (
             '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'DejaVuSans.ttf')
    for name in names:
        try: return ImageFont.truetype(name, size)
        except OSError: pass
    return ImageFont.load_default()


def _trim(draw, text, font, width):
    text = str(text).replace('\n', ' ')
    if draw.textbbox((0, 0), text, font=font)[2] <= width: return text
    while text and draw.textbbox((0,0),text+'…',font=font)[2] > width:
        text = text[:-1]
    return text+'…' if text else '…'


def _center(draw, text, y, font, fill=INK):
    text = _trim(draw,text,font,780)
    bounds=draw.textbbox((0,0),text,font=font)
    draw.text(((WIDTH-(bounds[2]-bounds[0]))/2,y),text,font=font,fill=fill)


def _base(championship=False):
    im=Image.new('RGB',(WIDTH,HEIGHT),BG)
    d=ImageDraw.Draw(im)
    accent = GOLD if championship else CYAN
    # Restrained broadcast gradients, no production-art dependencies.
    for y in range(HEIGHT):
        lift = int(12 * (1 - abs(y-HEIGHT/2)/(HEIGHT/2)))
        d.line((0,y,WIDTH,y), fill=(13+lift//3,18+lift//2,31+lift))
    for i in range(8):
        x = 35+i*110
        d.line((x,142,x-100,690),fill=(39,48,63),width=2)
    d.rounded_rectangle((30,28,820,722),radius=26,outline=accent,width=3)
    d.line((55,131,795,131),fill=accent,width=2)
    d.line((55,645,795,645),fill=accent,width=2)
    _center(d,'G U T T E R   S A I N T S',65,_font(27,True),accent)
    return im,d,accent


def _finish(im):
    out=BytesIO()
    im.save(out,format='PNG',optimize=True)
    out.seek(0)
    return out


def intro_card(session):
    finals=is_finals(session)
    im,d,accent=_base(finals)
    _center(d,'CHAMPIONSHIP NIGHT' if finals else
            ('TOURNAMENT MATCH' if getattr(session,'tournament_id',None) else
             'COMPETITION FIXTURE' if getattr(session,'fixture_id',None) else
             'FRIENDLY EXHIBITION' if getattr(session,'friendly_challenge',False) else
             'LIVE MATCH INTRODUCTIONS'),168,_font(28,True),accent)
    groups=list(group_rosters(session).items())
    if len(groups)==2:
        positions=(80,452)
        for (team,names),x in zip(groups,positions):
            d.rounded_rectangle((x,252,x+318,585),radius=17,
                                fill=(25,33,47),outline=(72,85,96),width=2)
            d.text((x+19,276),_trim(d,team,_font(21,True),280),font=_font(21,True),fill=accent)
            for row,name in enumerate(names[:7]):
                d.text((x+19,327+row*32),_trim(d,name,_font(17),280),font=_font(17),fill=INK)
            if len(names)>7:d.text((x+19,554),f'+{len(names)-7} more',font=_font(15),fill=CYAN)
        _center(d,'VS',409,_font(35,True),GOLD)
    else:
        names=[p.bowler.name for p in session.players]
        names = names[:12]
        for row,name in enumerate(names):
            x=84 if row%2==0 else 442
            y=266+(row//2)*52
            d.text((x,y),_trim(d,name,_font(22,True),316),font=_font(22,True),fill=INK)
    lane=f'{str(getattr(session,"lane","house")).title()} oil  •  Lanes {session.lane_pair.left.number}/{session.lane_pair.right.number}'
    _center(d,lane,666,_font(19),CYAN)
    return _finish(im)


def final_card(session, winner, awards=()):
    """Visual presentation only. Winner is determined by the committed match."""
    finals=is_finals(session)
    im,d,accent=_base(finals)
    _center(d,'CHAMPIONSHIP RESULT' if finals else 'MATCH FINAL',172,_font(30,True),accent)
    winner=str(winner or 'Draw — honours shared')
    _center(d,'MATCH WINNER' if winner!='Draw — honours shared' else 'FULL-TIME RESULT',256,_font(22,True),GOLD)
    _center(d,winner,319,_font(35,True),INK)
    scores=getattr(session,'team_totals',lambda:{})()
    if len(scores)>1:
        for pos,(name,score) in enumerate(sorted(scores.items(),key=lambda x:-x[1])[:3]):
            _center(d,f'{name}: {score}',413+pos*47,_font(22),CYAN)
    else:
        by_score=[]
        values=session.scores()
        for name,score in values.items():by_score.append((name,score))
        for pos,(name,score) in enumerate(sorted(by_score,key=lambda x:-x[1])[:3]):
            _center(d,f'{name}: {score}',413+pos*47,_font(22),CYAN)
    _center(d,'THE LANES HAVE SPOKEN',673,_font(19,True),accent)
    return _finish(im)


def transition_ribbon(image,stage,finals=False):
    """Overlay only unused space near the overhead camera header, not pin deck.

    Return a copy; never modify the caller's cached frames or the camera
    pin coordinate system. Very small synthetic test canvases stay unchanged.
    """
    from services.showtime import STAGE_LABELS
    if stage not in STAGE_LABELS or image.width<600 or image.height<500:
        return image
    out=image.convert('RGBA')
    layer=Image.new('RGBA',image.size,(0,0,0,0))
    draw=ImageDraw.Draw(layer)
    sx=image.width/850;sy=image.height/750
    box=tuple(round(n*(sx if j%2==0 else sy)) for j,n in enumerate((447,43,823,83)))
    draw.rounded_rectangle(box,radius=max(4,round(9*sx)),fill=(14,20,30,205),
                           outline=(229,184,105,225) if finals else (113,208,218,205),width=max(1,round(2*sx)))
    label=STAGE_LABELS[stage]
    draw.text((round(465*sx),round(51*sy)),label,font=_font(max(9,round(18*sx)),True),fill=GOLD if finals else CYAN)
    return Image.alpha_composite(out,layer).convert('RGB')
