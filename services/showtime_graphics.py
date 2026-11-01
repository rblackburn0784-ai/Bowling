"""v2.9.3c scoreboard cards; visual-only replacement for showtime_graphics.

Updated intro card to the new simplified neon matchup template.
Start-card text sizing and placement are aligned to the approved filled-in
reference version supplied by the user. No gameplay, RNG, scoring writes, or
extra shot animations occur in this module.
"""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from PIL import Image, ImageDraw, ImageFont
from services.showtime import is_finals

WIDTH, HEIGHT = 1672, 941
CYAN = (172, 238, 255)
INK = (245, 249, 255)
GOLD = (255, 216, 107)
DARK = (0, 13, 28)
ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'assets' / 'scoreboards'


def _font(size, bold=False):
    """Real scalable fonts on Windows/Linux/macOS; never silently use tiny PIL bitmap text.

    Windows is the most common local deployment platform for this bot.
    Impact most closely approximates the reference's heavy condensed lettering.
    """
    import os
    import sys
    win = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    home = Path.home()
    preferred = (
        [str(win / 'impact.ttf'), str(win / 'bahnschrift.ttf'),
         str(win / 'arialbd.ttf'), str(win / 'ARIALNBD.TTF'),
         '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf',
         '/usr/share/fonts/truetype/liberation2/LiberationSansNarrow-Bold.ttf',
         '/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf',
         '/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf',
         'DejaVuSansCondensed-Bold.ttf', 'Arial Bold.ttf'] if bold else
        [str(win / 'arial.ttf'),str(win / 'ARIALN.TTF'),
         '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf',
         '/System/Library/Fonts/Supplemental/Arial Narrow.ttf',
         'DejaVuSansCondensed.ttf']
    )
    for path in preferred:
        try:
            return ImageFont.truetype(path, int(size))
        except (OSError, ValueError):
            pass
    # Pillow's DejaVu family is often bundled with the installed package even
    # on Windows; ImageFont.load_default() is NEVER adequate for scoreboards.
    for name in ('DejaVuSansCondensed-Bold.ttf','DejaVuSans-Bold.ttf','arial.ttf'):
        try:
            return ImageFont.truetype(name, int(size))
        except (OSError, ValueError):
            pass
    raise RuntimeError('A scalable TrueType font is required to render Gutter Saints scorecards. Install DejaVu Sans or make Windows Fonts accessible.')


def _trim(d, text, font, max_width):
    s = str(text or '').replace('\n', ' ').strip()
    if not s:
        return ''
    if d.textbbox((0, 0), s, font=font)[2] <= max_width:
        return s
    while s and d.textbbox((0, 0), s + '…', font=font)[2] > max_width:
        s = s[:-1]
    return s.rstrip() + ('…' if s else '')


def _write(d, text, x, y, max_width, size=23, color=INK, bold=False,
           anchor='la', stroke=None, line_spacing=4):
    font = _font(size, bold)
    fill = _trim(d, text, font, max_width)
    sw = stroke if stroke is not None else (2 if bold and size >= 20 else 0)
    sf = DARK if sw else None
    d.multiline_text((x, y), fill, font=font, fill=color, anchor=anchor,
                     spacing=line_spacing, align='center',
                     stroke_width=sw, stroke_fill=sf)


def _background(file):
    p = TEMPLATES / file
    try:
        with Image.open(p) as im:
            return im.convert('RGB').resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    except (OSError, ValueError):
        return Image.new('RGB', (WIDTH, HEIGHT), (7, 14, 36))


def _png(im):
    out = BytesIO()
    im.save(out, 'PNG', optimize=True)
    out.seek(0)
    return out


def _players(session):
    """Keep two-lane neon templates meaningful for multi-bowler team games."""
    players = list(getattr(session, 'players', ()) or ())
    if len(players) > 2:
        from services.showtime import group_rosters
        groups = group_rosters(session)
        if len(groups) == 2 and 'Individual Bowlers' not in groups:
            result = []
            for team in groups:
                members = [p for p in players if getattr(p.bowler, 'team_name', None) == team]
                proxy = SimpleNamespace(bowler=SimpleNamespace(name=team, rank=None, handedness='R'),
                                        frames=[], split_frames=set(), _team_members=members,
                                        _team_name=team)
                result.append(proxy)
            return result
    return players[:2]


def _name(player):
    return str(getattr(getattr(player, 'bowler', None), 'name', 'Unknown'))


def _competition(session):
    if is_finals(session):
        return 'CHAMPIONSHIP FINAL'
    if getattr(session, 'friendly_challenge', False) or getattr(session, 'exhibition', False) or getattr(session, 'is_exhibition', False):
        return 'FRIENDLY EXHIBITION'
    if getattr(session, 'fixture_id', None):
        return 'COMPETITION FIXTURE'
    if getattr(session, 'tournament_id', None):
        return 'TOURNAMENT MATCH'
    if getattr(session, 'competition_id', None):
        return 'COMPETITION MATCH'
    return 'FRIENDLY MATCH'


def _lane_details(session):
    pair = getattr(session, 'lane_pair', None)
    left = getattr(getattr(pair, 'left', None), 'number', None)
    right = getattr(getattr(pair, 'right', None), 'number', None)
    oil = str(getattr(session, 'lane', 'house') or 'house').replace('_', ' ').title()
    if left is not None:
        lane_text = f'LANE {left}'
    elif right is not None:
        lane_text = f'LANE {right}'
    else:
        lane_text = 'LANE TBA'
    return lane_text, oil


def _bowler_info(player):
    if hasattr(player, '_team_members'):
        names = ', '.join(_name(p) for p in player._team_members)
        return f'{len(player._team_members)} BOWLERS  |  {names}'
    b = getattr(player, 'bowler', None)
    if b is None:
        return 'RANKED  |  RIGHT HANDED'
    hand = str(getattr(b, 'handedness', 'R')).upper()
    handed = 'LEFT HANDED' if hand.startswith('L') else 'RIGHT HANDED'
    rank = getattr(b, 'rank', None)
    prefix = f'#{rank} RANKED' if rank is not None else 'UNRANKED'
    return f'{prefix}  |  {handed}'


def _frames(session, p):
    try:
        card = session.card()
        if isinstance(card, dict):
            return list(card.get(_name(p), []) or [])[:10]
    except (ValueError, AttributeError, TypeError):
        pass
    return []


def _score(session, p):
    if hasattr(p, '_team_members'):
        try:
            totals = session.team_totals()
            if p._team_name in totals:
                return totals[p._team_name]
            scores = session.scores()
            return sum(int(scores.get(_name(member), 0)) for member in p._team_members)
        except (AttributeError, TypeError, ValueError):
            return None
    try:
        scores = session.scores()
        if isinstance(scores, dict):
            return scores.get(_name(p))
    except (ValueError, AttributeError, TypeError):
        pass
    return None


def _best_frame(p):
    if hasattr(p, '_team_members'):
        return max((_best_frame(member) for member in p._team_members),default=0)
    frames = list(getattr(p, 'frames', []) or [])[:10]
    result = []
    for i, frame in enumerate(frames):
        if not frame:
            continue
        future = [v for f in frames[i+1:] for v in f]
        if i == 9:
            result.append(sum(frame))
        elif frame[0] == 10 and len(future) >= 2:
            result.append(10 + sum(future[:2]))
        elif len(frame) >= 2 and sum(frame[:2]) == 10 and future:
            result.append(10 + future[0])
        elif len(frame) >= 2:
            result.append(sum(frame[:2]))
    return max(result, default=0)


def _frame_stats(p):
    if hasattr(p, '_team_members'):
        totals = [_frame_stats(member) for member in p._team_members]
        return tuple(sum(item[index] for item in totals) for index in range(4))
    frames = list(getattr(p, 'frames', []) or [])
    strikes = spares = opens = 0
    for i, f in enumerate(frames[:10]):
        if not f:
            continue
        try:
            rolls = [int(x) for x in f]
        except (TypeError, ValueError):
            continue
        if i < 9:
            if rolls[0] == 10:
                strikes += 1
            elif len(rolls) > 1 and sum(rolls[:2]) == 10:
                spares += 1
            elif len(rolls) > 1:
                opens += 1
        else:
            strikes += sum(x == 10 for x in rolls)
            if rolls[0] != 10 and len(rolls) > 1 and rolls[0] + rolls[1] == 10:
                spares += 1
            if rolls[0] == 10 and len(rolls) > 2 and rolls[1] < 10 and rolls[1] + rolls[2] == 10:
                spares += 1
            if len(rolls) > 1 and rolls[0] < 10 and rolls[0] + rolls[1] < 10:
                opens += 1
    split_count = len(getattr(p, 'split_frames', ()) or ())
    return strikes, spares, opens, split_count


def _intro_details(session, d, players):
    """Match the user-approved 1672x941 sample with dynamic, bold centred text."""
    # The start image is intentionally free of score grid and any baked text.
    for idx, p in enumerate(players):
        cx = 376 if idx == 0 else 1276
        # Bold condensed impact style; dynamically fit unusually long names.
        _centered(d, _name(p), cx, 462, 574, 61, color=INK,
                  minimum=26, stroke=2)
        _centered(d, _bowler_info(p), cx, 534, 545, 33, color=INK,
                  minimum=21, stroke=1)

    lane_text, oil = _lane_details(session)
    _centered(d, lane_text, 218, 747, 170, 35, color=INK, minimum=24, stroke=1)
    _centered(d, 'HOUSE OIL', 543, 719, 213, 32, color=INK, minimum=23, stroke=1)
    _centered(d, oil.upper(), 543, 753, 213, 30, color=CYAN, minimum=22, stroke=1)
    _centered(d, '10 FRAMES', 909, 747, 224, 34, color=INK, minimum=24, stroke=1)
    _centered(d, _competition(session), 1317, 747, 288, 31,
              color=INK, minimum=23, stroke=1)


def intro_card(session):
    im = _background('start.png')
    d = ImageDraw.Draw(im)
    _intro_details(session, d, _players(session))
    return _png(im)


def _fit_text(d, text, max_width, preferred, minimum=16, bold=True):
    """Choose the largest readable font that fits without clipping names."""
    for size in range(preferred, minimum - 1, -1):
        font = _font(size, bold)
        bb = d.textbbox((0, 0), str(text), font=font, stroke_width=1)
        if bb[2] - bb[0] <= max_width:
            return font
    return _font(minimum, bold)


def _centered(d, text, x, y, width, size, *, color=INK, minimum=16, stroke=1):
    font = _fit_text(d, text, width, size, minimum)
    d.text((x, y), str(text), anchor='mm', fill=color, font=font,
           stroke_width=stroke, stroke_fill=DARK)


def _roll_notation(frame, tenth=False):
    """Score-grid ball symbols, leaving cumulative totals to the scoring engine."""
    if not frame:
        return ''
    rolls = list(frame)
    glyphs = []
    for i, n in enumerate(rolls):
        if n == 10:
            glyphs.append('X')
        elif i and n + rolls[i-1] == 10 and (i == 1 and rolls[0] < 10 or
              tenth and i == 2 and rolls[0] == 10 and rolls[1] < 10):
            glyphs.append('/')
        elif n == 0:
            glyphs.append('–')
        else:
            glyphs.append(str(n))
    return ' '.join(glyphs)


def _cumulative(frames):
    """Use the game's own official scoring when frame is completely resolved."""
    from services.scoring import score_game
    out=[]
    for i in range(1, 11):
        if i > len(frames):
            out.append('');continue
        if i == 10:
            try: out.append(str(score_game(frames)))
            except (ValueError, TypeError, IndexError): out.append('')
            continue
        subset = frames[:i]
        rolls = [r for f in frames for r in f]
        at = 0; total = 0; complete = True
        for f in subset:
            if not f:complete=False;break
            if f[0] == 10:
                if at+2 >= len(rolls):complete=False;break
                total += 10 + rolls[at+1] + rolls[at+2];at+=1
            elif len(f)>1 and f[0]+f[1] == 10:
                if at+2 >= len(rolls):complete=False;break
                total += 10 + rolls[at+2];at+=2
            elif len(f)>1:
                total += f[0]+f[1];at+=2
            else:complete=False;break
        out.append(str(total) if complete else '')
    return out


def final_card(session, winner, awards=()):
    """v2.9.3c final scoreboard: rendered from committed game, never re-bowls."""
    im = _background('end.png')
    d = ImageDraw.Draw(im)
    players = _players(session)
    # Template: two 80px score rows, ten frames and separate total column.
    centres = [357, 470, 578, 686, 793, 903, 1010, 1118, 1230, 1360]
    for idx, p in enumerate(players):
        name = _name(p)
        ink = CYAN if idx == 0 else (255, 225, 232)
        row_y = 330 + 84*idx
        # Small names in the score grid. A length-aware font keeps both readable.
        
        if len(name) > 17 and ' ' in name:
            pieces = name.split(' ', 1)
            _centered(d, pieces[0], 173, row_y-15, 236, 25, color=INK, minimum=16)
            _centered(d, pieces[1], 173, row_y+12, 236, 23, color=INK, minimum=14)
        else:
            _centered(d, name, 173, row_y, 236, 28, color=INK, minimum=15)
        frames = list(getattr(p, 'frames', []) or [])[:10]
        totals = _cumulative(frames)
        for j in range(10):
            if j >= len(frames):continue
            txt = _roll_notation(frames[j], tenth=(j == 9))
            # First line shows rolls; second line cumulative scoring.
            _centered(d, txt, centres[j], row_y-17, 99, 32, color=INK, minimum=20)
            if totals[j]:
                _centered(d, totals[j], centres[j], row_y+23, 99, 28,
                          color=CYAN if idx == 0 else INK, minimum=20)
        score = _score(session,p)
        if score is None:
            try:score = int(totals[9])
            except (ValueError,IndexError):score = '—'
        _centered(d,str(score),1540,row_y,142,54,color=INK,minimum=35,stroke=2)
        # Names and large scores at left/right of fixed winner ornament.
        panel_mid = 340 if idx == 0 else 1311
        panel_w = 480 if idx == 0 else 520
        _centered(d,name,panel_mid,562,panel_w,48,color=ink,minimum=24,stroke=2)
        _centered(d,str(score),panel_mid,631,350,78,color=INK,minimum=56,stroke=2)
        strikes,spares,opens,_ = _frame_stats(p)
        stats = (str(strikes),str(spares),str(opens),str(_best_frame(p)),
                 f'{(float(score)/10):.1f}' if isinstance(score,(int,float)) else '—')
        stat_centres = [201,295,394,514,668] if idx == 0 else [841,933,1015,1135,1252]
        for x,value in zip(stat_centres,stats):
            _centered(d,value,x,786,102,32,color=CYAN if idx == 0 else (255,185,197),minimum=25)
    # Winner central panel already contains 'WINNER:' graphic.
    win = str(winner or 'DRAW')
    _centered(d,win.upper(),827,639,290,36,color=GOLD,minimum=18,stroke=2)
    return _png(im)

def transition_ribbon(image, stage, finals=False):
    """Unchanged on-lane stage ribbon, independent of the new cards."""
    from services.showtime import STAGE_LABELS
    if stage not in STAGE_LABELS or image.width < 600 or image.height < 500:
        return image
    out = image.convert('RGBA')
    layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    sx = image.width / 850
    sy = image.height / 750
    box = tuple(round(n * (sx if j % 2 == 0 else sy)) for j, n in enumerate((447, 43, 823, 83)))
    accent = (229, 184, 105, 225) if finals else (113, 208, 218, 205)
    draw.rounded_rectangle(box, radius=max(4, round(9 * sx)), fill=(14, 20, 30, 205),
                           outline=accent, width=max(1, round(2 * sx)))
    draw.text((round(465 * sx), round(51 * sy)), STAGE_LABELS[stage],
              font=_font(max(9, round(18 * sx)), True), fill=GOLD if finals else CYAN)
    return Image.alpha_composite(out, layer).convert('RGB')
