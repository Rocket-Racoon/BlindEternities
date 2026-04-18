# phyrexian/tournament.py
"""
Tournament bracket generation: Swiss pairing and Single Elimination.
"""
from __future__ import annotations

import math
import random
from itertools import combinations

from .models import (
    Tournament, TournamentParticipant, TournamentRound, TournamentMatch,
    TournamentMatchPlayer, BracketType, TournamentStatus, GameResult,
)


def generate_next_round(tournament: Tournament) -> TournamentRound | None:
    """
    Generate the next round of the tournament.

    Returns the newly created TournamentRound, or None if the tournament is
    already finished.
    """
    if tournament.status == TournamentStatus.FINISHED:
        return None

    next_num = tournament.current_round + 1

    # Check if tournament should end
    if tournament.bracket_type == BracketType.SWISS:
        total = tournament.total_rounds
        if next_num > total:
            return None
        return _generate_swiss_round(tournament, next_num)
    else:
        return _generate_single_elim_round(tournament, next_num)


def _randomize_seeds(tournament: Tournament) -> None:
    """Shuffle seed numbers for all participants (called once at tournament start)."""
    participants = list(tournament.participants.filter(dropped=False))
    random.shuffle(participants)
    for i, p in enumerate(participants, start=1):
        p.seed = i
    TournamentParticipant.objects.bulk_update(participants, ["seed"])


def _generate_swiss_round(tournament: Tournament, round_number: int) -> TournamentRound:
    """Swiss pairing: group players by match points, avoid rematches."""
    pod_size = tournament.pod_size

    if round_number == 1:
        # Randomize seating for the first round
        _randomize_seeds(tournament)
        participants = list(
            tournament.participants
            .filter(dropped=False)
            .order_by("seed")
        )
    else:
        # Subsequent rounds: pair by standings, break ties by seed
        participants = list(
            tournament.participants
            .filter(dropped=False)
            .order_by("-match_points", "-opp_match_win_pct", "seed")
        )

    # Build set of past pairings to avoid rematches
    past_pods: set[frozenset] = set()
    for rnd in tournament.rounds.all():
        for match in rnd.matches.all():
            pks = frozenset(
                mp.participant_id for mp in match.players.all()
            )
            past_pods.add(pks)

    pods = _pair_into_pods(participants, pod_size, past_pods)

    rnd = TournamentRound.objects.create(
        tournament=tournament, round_number=round_number,
    )
    for table_num, pod in enumerate(pods, start=1):
        is_bye = len(pod) < 2
        match = TournamentMatch.objects.create(
            round=rnd, table_number=table_num, is_bye=is_bye,
        )
        for p in pod:
            TournamentMatchPlayer.objects.create(
                match=match, participant=p,
            )
        # Auto-resolve byes
        if is_bye and pod:
            mp = match.players.first()
            mp.result = GameResult.WIN
            mp.placement = 1
            mp.save(update_fields=["result", "placement", "updated_at"])
            match.is_complete = True
            match.save(update_fields=["is_complete", "updated_at"])

    tournament.current_round = round_number
    if tournament.status == TournamentStatus.SETUP:
        tournament.status = TournamentStatus.ACTIVE
    tournament.save(update_fields=["current_round", "status", "updated_at"])
    return rnd


def _pair_into_pods(
    participants: list[TournamentParticipant],
    pod_size: int,
    avoid: set[frozenset],
) -> list[list[TournamentParticipant]]:
    """
    Greedily pair participants into pods of `pod_size`.

    Players are already sorted by standing.  We walk through them and fill
    pods top-down, skipping rematches when possible.
    """
    remaining = list(participants)
    pods: list[list[TournamentParticipant]] = []

    while remaining:
        pod: list[TournamentParticipant] = [remaining.pop(0)]
        while len(pod) < pod_size and remaining:
            # Prefer a player we haven't faced yet
            best = None
            for i, candidate in enumerate(remaining):
                test_set = frozenset(member.pk for member in pod) | {candidate.pk}
                # For 1v1 check exact pair; for multiplayer just check
                # we haven't been in the same pod before.
                if pod_size == 2:
                    if test_set not in avoid:
                        best = i
                        break
                else:
                    # In multiplayer, avoid any pair that already met
                    pair_overlap = any(
                        frozenset({member.pk, candidate.pk}).issubset(past)
                        for member in pod
                        for past in avoid
                    )
                    if not pair_overlap:
                        best = i
                        break
            if best is None:
                # Couldn't avoid rematch — take next available
                best = 0
            pod.append(remaining.pop(best))
        pods.append(pod)

    return pods


def _generate_single_elim_round(
    tournament: Tournament, round_number: int,
) -> TournamentRound | None:
    """Single elimination: winners from previous round advance."""
    pod_size = tournament.pod_size

    if round_number == 1:
        # Randomize seating for the first round
        _randomize_seeds(tournament)
        participants = list(
            tournament.participants
            .filter(dropped=False)
            .order_by("seed")
        )
    else:
        # Advance winners from previous round
        prev_round = tournament.rounds.filter(round_number=round_number - 1).first()
        if not prev_round or not prev_round.is_complete:
            return None
        participants = []
        for match in prev_round.matches.order_by("bracket_position"):
            winner_mp = match.players.filter(placement=1).first()
            if winner_mp:
                participants.append(winner_mp.participant)

    if len(participants) < 2:
        return None

    rnd = TournamentRound.objects.create(
        tournament=tournament, round_number=round_number,
    )

    # Split into pods
    pods: list[list[TournamentParticipant]] = []
    for i in range(0, len(participants), pod_size):
        pods.append(participants[i:i + pod_size])

    for table_num, pod in enumerate(pods, start=1):
        is_bye = len(pod) < 2
        match = TournamentMatch.objects.create(
            round=rnd, table_number=table_num,
            bracket_position=table_num, is_bye=is_bye,
        )
        for p in pod:
            TournamentMatchPlayer.objects.create(match=match, participant=p)
        if is_bye and pod:
            mp = match.players.first()
            mp.result = GameResult.WIN
            mp.placement = 1
            mp.save(update_fields=["result", "placement", "updated_at"])
            match.is_complete = True
            match.save(update_fields=["is_complete", "updated_at"])

    tournament.current_round = round_number
    if tournament.status == TournamentStatus.SETUP:
        tournament.status = TournamentStatus.ACTIVE
    tournament.save(update_fields=["current_round", "status", "updated_at"])
    return rnd


def record_match_result(
    match: TournamentMatch,
    placements: dict,
) -> None:
    """
    Record the result of a match.

    Args:
        match: the TournamentMatch
        placements: {participant_pk_str: placement} — 1 = winner, 2 = second, …
    """
    player_count = match.players.count()
    placed_values = [
        placements.get(str(mp.participant_id), 0)
        for mp in match.players.all()
    ]
    # Tie: everyone has the same placement (e.g. all 1)
    is_tie = len(set(v for v in placed_values if v > 0)) == 1 and placed_values.count(placed_values[0]) == player_count

    for mp in match.players.all():
        place = placements.get(str(mp.participant_id), 0)
        if place == 0:
            place = player_count
        mp.placement = place
        if is_tie:
            mp.result = GameResult.DRAW
        elif place == 1:
            mp.result = GameResult.WIN
        else:
            mp.result = GameResult.LOSS
        mp.save(update_fields=["placement", "result", "updated_at"])

    match.is_complete = True
    match.save(update_fields=["is_complete", "updated_at"])

    # Update participant standings
    _update_standings(match.round.tournament)

    # Check if round is complete
    rnd = match.round
    if not rnd.matches.filter(is_complete=False).exists():
        rnd.is_complete = True
        rnd.save(update_fields=["is_complete", "updated_at"])

        # Check if tournament is finished
        tournament = rnd.tournament
        if tournament.bracket_type == BracketType.SWISS:
            if rnd.round_number >= tournament.total_rounds:
                _finish_tournament(tournament)
        else:
            # Single elim: finished when only 1 player would advance
            winners = []
            for m in rnd.matches.all():
                w = m.players.filter(placement=1).first()
                if w:
                    winners.append(w.participant)
            if len(winners) <= 1:
                _finish_tournament(tournament)


def _update_standings(tournament: Tournament) -> None:
    """Recalculate match points and tiebreakers for all participants."""
    participants = list(tournament.participants.all())
    rounds = tournament.rounds.prefetch_related("matches__players")

    # Reset
    stats = {p.pk: {"mw": 0, "ml": 0, "md": 0, "pts": 0} for p in participants}
    opponents: dict[int, list[int]] = {p.pk: [] for p in participants}

    for rnd in rounds:
        for match in rnd.matches.all():
            if not match.is_complete or match.is_bye:
                continue
            players_in_match = list(match.players.all())
            for mp in players_in_match:
                pk = mp.participant_id
                if mp.result == GameResult.WIN:
                    stats[pk]["mw"] += 1
                    stats[pk]["pts"] += 3
                elif mp.result == GameResult.DRAW:
                    stats[pk]["md"] += 1
                    stats[pk]["pts"] += 1
                elif mp.result == GameResult.LOSS:
                    stats[pk]["ml"] += 1
                # Track opponents
                for other in players_in_match:
                    if other.participant_id != pk:
                        opponents[pk].append(other.participant_id)

    # Save match points
    for p in participants:
        s = stats[p.pk]
        p.match_wins = s["mw"]
        p.match_losses = s["ml"]
        p.match_draws = s["md"]
        p.match_points = s["pts"]

        total_games = s["mw"] + s["ml"] + s["md"]
        p.game_win_pct = s["mw"] / total_games if total_games else 0.0

    # Build per-participant game_win_pct lookup for tiebreaker calc
    gwp_lookup = {p.pk: p.game_win_pct for p in participants}

    # Opponent match win % and game win % (Swiss tiebreakers)
    for p in participants:
        opp_pks = opponents[p.pk]
        if opp_pks:
            opp_mwps = []
            opp_gwps = []
            for opk in opp_pks:
                os = stats[opk]
                ot = os["mw"] + os["ml"] + os["md"]
                mwp = max(0.33, os["mw"] / ot) if ot else 0.33
                gwp = max(0.33, gwp_lookup.get(opk, 0.0)) if gwp_lookup.get(opk, 0.0) > 0 else 0.33
                opp_mwps.append(mwp)
                opp_gwps.append(gwp)
            p.opp_match_win_pct = sum(opp_mwps) / len(opp_mwps)
            p.opp_game_win_pct = sum(opp_gwps) / len(opp_gwps)
        else:
            p.opp_match_win_pct = 0.0
            p.opp_game_win_pct = 0.0

    from django.utils import timezone as tz
    now = tz.now()
    for p in participants:
        p.updated_at = now
    TournamentParticipant.objects.bulk_update(
        participants,
        [
            "match_wins", "match_losses", "match_draws", "match_points",
            "game_win_pct", "opp_match_win_pct", "opp_game_win_pct", "updated_at",
        ],
    )


def _finish_tournament(tournament: Tournament) -> None:
    """Mark tournament as finished and assign final standings."""
    participants = list(
        tournament.participants
        .filter(dropped=False)
        .order_by("-match_points", "-opp_match_win_pct", "-game_win_pct")
    )
    from django.utils import timezone as tz
    now = tz.now()
    for i, p in enumerate(participants, start=1):
        p.final_standing = i
        p.updated_at = now
    TournamentParticipant.objects.bulk_update(participants, ["final_standing", "updated_at"])

    # Also assign dropped players after the active ones
    dropped = list(tournament.participants.filter(dropped=True))
    next_pos = len(participants) + 1
    for p in dropped:
        p.final_standing = next_pos
        p.updated_at = now
        next_pos += 1
    if dropped:
        TournamentParticipant.objects.bulk_update(dropped, ["final_standing", "updated_at"])

    tournament.status = TournamentStatus.FINISHED
    tournament.save(update_fields=["status", "updated_at"])

    # Update TournamentStats for every registered user in this tournament
    user_ids = (
        tournament.participants
        .filter(user__isnull=False)
        .values_list("user_id", flat=True)
        .distinct()
    )
    for uid in user_ids:
        recompute_tournament_stats(uid, tournament.format)


def recompute_tournament_stats(user_id: int, game_format: str) -> None:
    """
    Recompute aggregate tournament stats for a user in a specific format.

    Walks every finished tournament the user has participated in for the
    given format, aggregating final standings, match record, and game wins.
    """
    from django.db.models import Sum, Count, Q, Min
    from .models import TournamentStats, TournamentParticipant, TournamentMatchPlayer

    participants = TournamentParticipant.objects.filter(
        user_id=user_id,
        tournament__format=game_format,
        tournament__status=TournamentStatus.FINISHED,
    ).select_related("tournament")

    tournaments_played = participants.count()
    tournaments_won = participants.filter(final_standing=1).count()
    top_4 = participants.filter(final_standing__lte=4, final_standing__gt=0).count()

    match_agg = participants.aggregate(
        mw=Sum("match_wins"),
        ml=Sum("match_losses"),
        md=Sum("match_draws"),
    )
    best = participants.filter(final_standing__gt=0).aggregate(bp=Min("final_standing"))

    # Game wins/losses across all match entries
    game_agg = TournamentMatchPlayer.objects.filter(
        participant__user_id=user_id,
        participant__tournament__format=game_format,
        participant__tournament__status=TournamentStatus.FINISHED,
        match__is_complete=True,
    ).aggregate(
        gw=Sum("game_wins"),
    )
    total_game_wins = game_agg["gw"] or 0

    # For game losses, sum other players' game_wins in the same matches
    game_losses = 0
    match_ids = TournamentMatchPlayer.objects.filter(
        participant__user_id=user_id,
        participant__tournament__format=game_format,
        participant__tournament__status=TournamentStatus.FINISHED,
        match__is_complete=True,
    ).values_list("match_id", flat=True)
    if match_ids:
        other_wins = TournamentMatchPlayer.objects.filter(
            match_id__in=list(match_ids),
        ).exclude(participant__user_id=user_id).aggregate(total=Sum("game_wins"))
        game_losses = other_wins["total"] or 0

    stats, _ = TournamentStats.objects.get_or_create(
        user_id=user_id, format=game_format,
    )
    stats.tournaments_played = tournaments_played
    stats.tournaments_won = tournaments_won
    stats.top_4 = top_4
    stats.match_wins = match_agg["mw"] or 0
    stats.match_losses = match_agg["ml"] or 0
    stats.match_draws = match_agg["md"] or 0
    stats.game_wins = total_game_wins
    stats.game_losses = game_losses
    stats.best_placement = best["bp"] or 0
    stats.save()
