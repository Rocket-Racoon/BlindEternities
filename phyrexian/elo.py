# phyrexian/elo.py
"""
Multiplayer ELO rating engine for Magic: The Gathering.

Uses pairwise comparison: for an N-player game, each pair of players is
treated as a 1v1 match.  Players who placed higher "won" that comparison.
The ELO change is the average across all pairwise deltas.

Default K-factor: 32 for new players (<30 games), 24 for established.
Starting rating: 1200.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


DEFAULT_RATING = 1200
K_NEW = 32          # K-factor for <30 matches
K_ESTABLISHED = 24  # K-factor for >=30 matches
NEW_THRESHOLD = 30


@dataclass
class PlayerResult:
    """Input for the ELO engine: one participant in a game."""
    user_id: int
    rating: int
    matches_played: int
    placement: int          # 1 = winner, 2 = second, etc.


@dataclass
class RatingChange:
    """Output: computed delta for one participant."""
    user_id: int
    old_rating: int
    new_rating: int
    change: int


def _expected_score(ra: int, rb: int) -> float:
    """Standard ELO expected score of player A vs player B."""
    return 1.0 / (1.0 + math.pow(10, (rb - ra) / 400.0))


def _k_factor(matches_played: int) -> int:
    return K_NEW if matches_played < NEW_THRESHOLD else K_ESTABLISHED


def _actual_score(placement_a: int, placement_b: int) -> float:
    """
    Pairwise actual score:
      - A placed higher (lower number) than B → 1.0
      - Same placement (draw) → 0.5
      - A placed lower → 0.0
    """
    if placement_a < placement_b:
        return 1.0
    elif placement_a == placement_b:
        return 0.5
    return 0.0


def calculate_multiplayer_elo(results: list[PlayerResult]) -> list[RatingChange]:
    """
    Calculate ELO changes for a multiplayer game.

    Each player is compared pairwise against every other player.
    The delta is the average of all pairwise ELO deltas.

    Args:
        results: list of PlayerResult (one per participant, with placement).

    Returns:
        list of RatingChange (one per participant).
    """
    if len(results) < 2:
        return []

    changes: list[RatingChange] = []
    n = len(results)

    for player in results:
        k = _k_factor(player.matches_played)
        total_delta = 0.0

        for opponent in results:
            if opponent.user_id == player.user_id:
                continue
            expected = _expected_score(player.rating, opponent.rating)
            actual = _actual_score(player.placement, opponent.placement)
            total_delta += k * (actual - expected)

        # Average across all opponents
        avg_delta = total_delta / (n - 1)
        change = round(avg_delta)
        new_rating = max(100, player.rating + change)  # floor at 100

        changes.append(RatingChange(
            user_id=player.user_id,
            old_rating=player.rating,
            new_rating=new_rating,
            change=new_rating - player.rating,
        ))

    return changes


def apply_elo_changes(
    game_format: str,
    results: list[PlayerResult],
    game_record=None,
    tournament_match=None,
) -> list[RatingChange]:
    """
    Calculate AND persist ELO changes to the database.

    Creates/updates EloRating and appends EloHistory for each player.
    Returns the list of RatingChange objects.
    """
    from .models import EloRating, EloHistory

    changes = calculate_multiplayer_elo(results)
    if not changes:
        return changes

    # Build opponents snapshot for each player
    player_map = {r.user_id: r for r in results}

    for rc in changes:
        rating_obj, _created = EloRating.objects.get_or_create(
            user_id=rc.user_id,
            format=game_format,
            defaults={"rating": DEFAULT_RATING},
        )

        rating_obj.rating = rc.new_rating
        rating_obj.matches_played += 1
        if rc.new_rating > rating_obj.peak_rating:
            rating_obj.peak_rating = rc.new_rating

        player = player_map[rc.user_id]
        if player.placement == 1:
            rating_obj.wins += 1
        elif player.placement == max(r.placement for r in results):
            rating_obj.losses += 1
        else:
            # Middle placements in multiplayer — count as draw
            rating_obj.draws += 1

        rating_obj.save()

        opponents_snap = [
            {
                "user_id": r.user_id,
                "rating": r.rating,
                "placement": r.placement,
            }
            for r in results if r.user_id != rc.user_id
        ]

        EloHistory.objects.create(
            user_id=rc.user_id,
            format=game_format,
            old_rating=rc.old_rating,
            new_rating=rc.new_rating,
            change=rc.change,
            game=game_record,
            tournament_match=tournament_match,
            opponents_snapshot=opponents_snap,
        )

    return changes
