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


def _generate_swiss_round(tournament: Tournament, round_number: int) -> TournamentRound:
    """Swiss pairing: group players by match points, avoid rematches."""
    pod_size = tournament.pod_size
    participants = list(
        tournament.participants
        .filter(dropped=False)
        .order_by("-match_points", "-opp_match_win_pct", "?")
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
                test_set = frozenset(p.pk for p in pod) | {candidate.pk}
                # For 1v1 check exact pair; for multiplayer just check
                # we haven't been in the same pod before.
                if pod_size == 2:
                    if test_set not in avoid:
                        best = i
                        break
                else:
                    # In multiplayer, avoid any pair that already met
                    pair_overlap = any(
                        frozenset({p.pk, candidate.pk}).issubset(past)
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
        # Seed-based initial bracket
        participants = list(
            tournament.participants
            .filter(dropped=False)
            .order_by("seed", "?")
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
    placements: dict[int, int],
) -> None:
    """
    Record the result of a match.

    Args:
        match: the TournamentMatch
        placements: {participant_pk: placement} — 1 = winner, 2 = second, …
    """
    for mp in match.players.all():
        place = placements.get(mp.participant_id, 0)
        mp.placement = place
        if place == 1:
            mp.result = GameResult.WIN
        elif place > 1:
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
                gwp = max(0.33, os["mw"] / ot) if ot else 0.33
                opp_mwps.append(mwp)
                opp_gwps.append(gwp)
            p.opp_match_win_pct = sum(opp_mwps) / len(opp_mwps)
            p.opp_game_win_pct = sum(opp_gwps) / len(opp_gwps)
        else:
            p.opp_match_win_pct = 0.0
            p.opp_game_win_pct = 0.0

    TournamentParticipant.objects.bulk_update(
        participants,
        [
            "match_wins", "match_losses", "match_draws", "match_points",
            "game_win_pct", "opp_match_win_pct", "opp_game_win_pct",
        ],
    )


def _finish_tournament(tournament: Tournament) -> None:
    """Mark tournament as finished and assign final standings."""
    participants = list(
        tournament.participants
        .filter(dropped=False)
        .order_by("-match_points", "-opp_match_win_pct", "-game_win_pct")
    )
    for i, p in enumerate(participants, start=1):
        p.final_standing = i
    TournamentParticipant.objects.bulk_update(participants, ["final_standing"])

    # Also assign dropped players after the active ones
    dropped = list(tournament.participants.filter(dropped=True))
    next_pos = len(participants) + 1
    for p in dropped:
        p.final_standing = next_pos
        next_pos += 1
    if dropped:
        TournamentParticipant.objects.bulk_update(dropped, ["final_standing"])

    tournament.status = TournamentStatus.FINISHED
    tournament.save(update_fields=["status", "updated_at"])
