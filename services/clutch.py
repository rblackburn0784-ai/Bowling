def tenth_requirement(leader_score, current_score_after_9):
    """Human-readable target for a bowler entering the 10th. Uses exact max/min search over legal 10th frames."""
    need=leader_score-current_score_after_9+1
    if need<=0:return 'has already moved in front'
    if need>30:return 'cannot catch the leader in the tenth'
    if need==30:return 'needs XXX to win'
    if need>=20:return f'needs at least {need} in the tenth — a strike is essential'
    if need==20:return 'needs X-X to win'
    if need>10:return f'needs {need} in the tenth to win'
    return f'needs {need} pins in the tenth to win'
