"""Presentation-only winner resolution for match-end character celebrations.

Only a unique winning bowler or team is crowned. No score/XP/physics writes.
"""
from services.analytics import player_summary


def winning_bowler(session):
    if len(session.players)<2 or not session.complete:
        return None
    totals=session.team_totals()
    if len(totals)>1:
        peak=max(totals.values())
        best_teams=[team for team,score in totals.items() if score==peak]
        if len(best_teams)!=1:
            return None  # Drawn team match
        candidates=[p for p in session.players
                    if getattr(p.bowler,'team_name',None)==best_teams[0]]
    else:
        candidates=list(session.players)
    if not candidates:
        return None
    high=max(player_summary(p)['score'] for p in candidates)
    best=[p for p in candidates if player_summary(p)['score']==high]
    if len(best)!=1:
        return None  # No single victor, never arbitrarily crown a tied player
    return best[0]
