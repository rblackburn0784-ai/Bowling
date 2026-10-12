"""v2.9.1 presentation director. Purely cosmetic: never reads GameSession.rng.

Stage cues are determined using pre-delivery state only; result cues are
computed AFTER playback. No SQL writes, scores, XP, or pinfall calls here.
"""
import hashlib
from services.analytics import named_leave

STAGE_LABELS = {
    'approach': 'THE APPROACH', 'path': 'BALL IN FLIGHT',
    'breakpoint': 'THE BREAKPOINT', 'impact': 'ON THE DECK',
}
STAGE_TAGLINES = {
    'approach': ('The approach falls quiet.', 'All eyes settle on the release.',
                 'One delivery at a time.', 'The lane is waiting.'),
    'path': ('Tracking the line downlane.', 'The ball is still travelling.',
             'A long look at that trajectory.', 'Watch the speed and shape.'),
    'breakpoint': ('It is making its move.', 'Here comes the entry angle.',
                   'The last few feet matter.', 'Watch where the ball turns.'),
    'impact': ('Contact! Let the pins settle.', 'The rack is still moving.',
               'No early verdict from the booth.', 'Waiting on the final leave.'),
}
FINALS_LINES = (
    'Championship lights are on. Every ball matters.',
    'The audience is leaning forward now.',
    'The title is still there to be won.',
    'Pressure on the lanes. Composure is everything.',
)
RESULT_MOMENTS = {
    '300': ('🏆 PERFECT 300! The building erupts!', '🏆 Twelve consecutive strikes. A perfect 300!'),
    '7-10': ('🚨 A 7–10 CONVERSION! An extraordinary pickup!',
             '🔥 The 7–10 disappears — a spectacular conversion!'),
    'big-four': ('💥 The Big Four is gone! What a conversion!',),
    'greek': ('🤯 Greek Church converted. That was special!',),
    'split': ('🎯 {name} makes the {leave} — enormous spare!',
              '👏 The entire {leave} falls for {name}!'),
    'front-nine': ('🤫 Nine in a row. The perfect game is on the line.',),
    'eleven': ('🤫 ELEVEN STRIKES. One final delivery for 300.',),
    'turkey': ('🦃 Turkey! Three strikes in succession.',),
    'six': ('🎒 Six-pack! The strike streak keeps building.',),
    'tenth-spare': ('🎯 Crucial tenth-frame spare converted by {name}.',),
    'messenger': ('🪽 A messenger comes across the rack for {name}!',),
    'brooklyn': ('🌉 Brooklyn side! The rack falls for {name}.',),
    'ringing_10': ('🔔 Ringing ten! The corner pin refuses to go.',),
    'stone_8': ('🪨 Stone eight! That one deserved better.',),
    'stone_9': ('🪨 Stone nine. The deck holds out.',),
}


def _index(session, event, key, count):
    """Stable cosmetic selection, independent of Python/hash randomization."""
    seed = getattr(session, 'seed', 0)
    ball = getattr(session, 'ball_count', 0)
    material = f'{seed}:{ball}:{event.get("bowler_id", "?")}:{key}'.encode()
    return int.from_bytes(hashlib.blake2s(material, digest_size=4).digest(), 'big') % count


def is_finals(session):
    return str(getattr(session, 'layout', 'broadcast')).lower() == 'finals'


def stage_cue(session, stage, event):
    """Only frame, ball and BEFORE pin state are permitted before reveal."""
    if stage not in STAGE_LABELS:
        return None
    cache = event.setdefault('_showtime_stage', {})
    if stage in cache:
        return cache[stage]
    frame = int(event.get('frame') or 0)
    ball = int(event.get('ball') or 1)
    if frame == 10 and stage == 'approach':
        text = 'Tenth frame. The margin for error is shrinking.'
    elif ball > 1 and stage == 'approach':
        text = 'A second delivery. The bowler has a leave to address.'
    elif is_finals(session) and stage in ('approach', 'breakpoint'):
        text = FINALS_LINES[_index(session, event, 'finals:'+stage, len(FINALS_LINES))]
    else:
        choices = STAGE_TAGLINES[stage]
        text = choices[_index(session, event, 'stage:'+stage, len(choices))]
    cache[stage] = text
    return text


def _result_key(event):
    if event.get('split_conversion'):
        label = str(event.get('split_name') or named_leave(event.get('before', ())) or 'split')
        normalized = label.casefold().replace('–', '-').replace('—', '-')
        if '7-10' in normalized: return '7-10'
        if 'big four' in normalized: return 'big-four'
        if 'greek church' in normalized: return 'greek'
        return 'split'
    strikes = int(event.get('strike_streak') or 0)
    if strikes >= 12: return '300'
    if strikes == 11: return 'eleven'
    if strikes == 9: return 'front-nine'
    if strikes == 6: return 'six'
    if strikes == 3: return 'turkey'
    if event.get('spare') and event.get('frame') == 10: return 'tenth-spare'
    for key in ('messenger','brooklyn','ringing_10','stone_8','stone_9'):
        if key in (event.get('carry_tags') or []): return key
    return None


def result_cue(session, event):
    """Optional headline after the pinfall is fully revealed. Cache per event."""
    if '_showtime_result' in event: return event['_showtime_result']
    key = _result_key(event)
    if key is None:
        event['_showtime_result'] = None
        return None
    choices = RESULT_MOMENTS[key]
    name = str(event.get('bowler', 'Our bowler'))
    leave = str(event.get('split_name') or named_leave(event.get('before', ())) or 'split')
    cue = choices[_index(session, event, 'result:'+key, len(choices))].format(name=name,leave=leave)
    event['_showtime_result'] = cue
    return cue


def crowd_cue(session, event):
    """One sparse finals crowd beat, returned as text (never an extra message)."""
    if not is_finals(session): return None
    count = int(getattr(session, 'ball_count', 0))
    if int(getattr(session, '_showtime_crowd_ball', -99)) >= count-3:
        return None
    critical = _result_key(event)
    if critical in ('300','7-10','big-four','greek','eleven'):
        beat = '📣 The crowd rises to its feet.'
    elif event.get('frame') == 10 and (event.get('spare') or event.get('pins') == 10):
        beat = '👏 Applause echoes down the championship lanes.'
    elif event.get('split'):
        beat = '😮 A sharp gasp rolls through the stands.'
    elif event.get('pins') == 0:
        beat = '🤫 The crowd goes quiet for a moment.'
    else:
        return None
    session._showtime_crowd_ball = count
    return beat


def celebration_worthy(event):
    """Only post-delivery camera stills may use the optional cheer pose."""
    return bool(event and (event.get('split_conversion') or
                int(event.get('strike_streak') or 0) >= 3 or
                (int(event.get('pins') or 0) == 10 and not event.get('spare'))))


def group_rosters(session):
    groups = {}
    for player in getattr(session, 'players', ()):
        bowler = player.bowler
        label = getattr(bowler, 'team_name', None) or 'Individual Bowlers'
        groups.setdefault(label, []).append(str(bowler.name))
    return groups


def is_elimination_final(fixture, competition_format, fixtures=()):
    """Distinguish a real championship fixture from an ordinary league round."""
    bracket = str(fixture.get('bracket') or '').lower()
    if bracket in ('grand_final','final'):
        return True
    if str(competition_format).lower() not in ('single_elimination','double_elimination','stepladder'):
        return False
    rows = [r for r in fixtures if r.get('stage_id')==fixture.get('stage_id')
            and r.get('bracket')==fixture.get('bracket')]
    if not rows:
        return False
    final_round = max(int(r['round_no']) for r in rows)
    last = [r for r in rows if int(r['round_no'])==final_round]
    return len(last)==1 and last[0].get('id')==fixture.get('id')
