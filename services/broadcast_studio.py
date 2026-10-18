"""Replay policy and visual-only shot identity for v2.9.5.
Nothing here advances a frame, touches RNG, awards XP, or commits results.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class BroadcastConfig:
    replay: bool = True
    slow_motion: bool = True
    sound: bool = True
    maximum_replays_per_shot: int = 1

def mode(session):
    if getattr(session, 'friendly_challenge', False) or getattr(session, 'practice_no_rewards', False):
        return 'exhibition'
    if getattr(session, 'layout', None) == 'finals':
        return 'finals'
    if getattr(session, 'fixture_id', None) or getattr(session, 'tournament_id', None):
        return 'tournament'
    return 'standard'

def replay_reason(event, session):
    """Trigger only on recorded shot outcomes, never on random graphics."""
    if event.get('strike') or len(event.get('down', ())) == 10:
        return 'STRIKE REPLAY'
    if event.get('split_conversion'):
        return 'SPLIT CONVERSION'
    if event.get('spare') and (len(event.get('before', ())) <= 3 or event.get('leave_name')):
        return 'DIFFICULT SPARE'
    if event.get('frame') == 10 and (event.get('strike') or event.get('spare')):
        return 'CLUTCH TENTH'
    return None

def shot_identity(session, event):
    return (getattr(session, 'session_uid', None),
            getattr(session, 'ball_count', None),
            event.get('bowler_id'), event.get('frame'), event.get('ball'))
