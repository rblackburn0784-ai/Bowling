import discord
from services.commentary import event_text,perfect_watch\nfrom services.career import rank_title

def bowler_embed(b):
    e=discord.Embed(title=f'🎳 {b.name}',description=f'{b.handedness}-handed bowler • **{rank_title(b.rank)} — Rank {b.rank}**')
    for n in ['rank','accuracy','consistency','spin','nerves','style','flair']:e.add_field(name=n.title(),value=getattr(b,n),inline=True)
    e.set_footer(text=f'Bowling attribute total: {b.stat_total}');return e

def scoreboard_embed(session,last=None,team_names=None):
    e=discord.Embed(title='🎳 Gutter Saints — Live Game',description=f'Lane: **{session.lane.title()}** • Seed: `{session.seed}`')
    cards=session.card()
    totals={}
    for p in session.players:
        frames=cards[p.bowler.name]+['·']*(10-len(cards[p.bowler.name]));value=' | '.join(f'{i+1}:{x}' for i,x in enumerate(frames[:10]))
        if p.complete:value+=f"\n**Final: {session.scores()[p.bowler.name]}**"
        team=getattr(p.bowler,'team_name',None)
        if p.complete and team:totals[team]=totals.get(team,0)+session.scores()[p.bowler.name]
        e.add_field(name=f"{p.bowler.name}"+(f' — {team}' if team else ''),value=value,inline=False)
    if totals:e.add_field(name='🏆 Team Totals',value='\n'.join(f'**{k}: {v}**' for k,v in totals.items()),inline=False)
    if last:
        e.add_field(name='🎙️ Commentary',value=event_text(session,last),inline=False)
        p=next(x for x in session.players if x.bowler.name==last['bowler']);watch=perfect_watch(p)
        if watch:e.add_field(name='🚨 Perfect Game Watch',value=watch,inline=False)
    return e

def bracket_embed(t,rows):
    e=discord.Embed(title=f"🏆 {t['name']}",description=f"Status: **{t['status'].replace('_',' ').title()}** • Lane: **{t['lane_condition'].title()}**")
    rounds={}
    for r in rows:rounds.setdefault(r['round_no'],[]).append(r)
    for rn,ms in rounds.items():
        text=[]
        for m in ms:
            a=m['team_a'] or 'BYE';b=m['team_b'] or 'BYE';sc=f" ({m['score_a']}–{m['score_b']})" if m['score_a'] is not None else ''
            text.append(f"**M{m['match_no']}** {a} vs {b}{sc}"+(f" → **{m['winner']}**" if m['winner'] else ''))
        e.add_field(name=f'Round {rn}',value='\n'.join(text),inline=False)
    return e
