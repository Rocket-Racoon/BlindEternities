# phyrexian/management/commands/recalculate_elo.py
"""
Recalculate all ELO ratings from scratch using game history.

Wipes current ratings & history, then replays every game chronologically.

Usage:
    python manage.py recalculate_elo
    python manage.py recalculate_elo --magic-format commander
    python manage.py recalculate_elo --dry-run
"""
from django.core.management.base import BaseCommand
from phyrexian.models import GameRecord, GameResult, EloRating, EloHistory
from phyrexian.elo import PlayerResult, apply_elo_changes, DEFAULT_RATING


class Command(BaseCommand):
    help = "Recalculate all ELO ratings from game history."

    def add_arguments(self, parser):
        parser.add_argument(
            "--magic-format", help="Only recalculate for one format.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Show what would change without saving.",
        )

    def handle(self, *args, **options):
        fmt_filter = options.get("magic_format")
        dry_run = options["dry_run"]

        if not dry_run:
            qs_r = EloRating.objects.all()
            qs_h = EloHistory.objects.all()
            if fmt_filter:
                qs_r = qs_r.filter(format=fmt_filter)
                qs_h = qs_h.filter(format=fmt_filter)
            count_r = qs_r.count()
            count_h = qs_h.count()
            qs_h.delete()
            qs_r.delete()
            self.stdout.write(f"Cleared {count_r} rating(s) and {count_h} history entries.")

        # Replay games chronologically
        games = (
            GameRecord.objects
            .filter(is_active=True)
            .select_related("user")
            .prefetch_related("opponents")
            .order_by("date_played", "created_at")
        )
        if fmt_filter:
            games = games.filter(format=fmt_filter)

        # Track in-memory ratings for dry-run and for building PlayerResult
        mem_ratings: dict[int, dict[str, int]] = {}  # {user_id: {format: rating}}
        mem_matches: dict[int, dict[str, int]] = {}  # {user_id: {format: count}}

        processed = 0
        skipped = 0

        for game in games:
            if not game.user_id:
                skipped += 1
                continue

            fmt = game.format
            participants = []

            # The logged user
            uid = game.user_id
            r = mem_ratings.setdefault(uid, {}).get(fmt, DEFAULT_RATING)
            m = mem_matches.setdefault(uid, {}).get(fmt, 0)
            placement = game.my_placement or (1 if game.result == GameResult.WIN else 2)
            participants.append(PlayerResult(
                user_id=uid, rating=r, matches_played=m, placement=placement,
            ))

            # Opponents with linked decks (which have a user)
            for opp in game.opponents.select_related("deck__user").all():
                if not opp.deck_id or not opp.deck.user_id:
                    continue
                oid = opp.deck.user_id
                if oid == uid:
                    continue  # skip self
                or_ = mem_ratings.setdefault(oid, {}).get(fmt, DEFAULT_RATING)
                om = mem_matches.setdefault(oid, {}).get(fmt, 0)
                op = opp.placement or (1 if opp.is_winner else 2)
                participants.append(PlayerResult(
                    user_id=oid, rating=or_, matches_played=om, placement=op,
                ))

            if len(participants) < 2:
                skipped += 1
                continue

            if dry_run:
                from phyrexian.elo import calculate_multiplayer_elo
                changes = calculate_multiplayer_elo(participants)
                for c in changes:
                    mem_ratings[c.user_id][fmt] = c.new_rating
                    mem_matches.setdefault(c.user_id, {})[fmt] = (
                        mem_matches.get(c.user_id, {}).get(fmt, 0) + 1
                    )
                    if c.change != 0:
                        self.stdout.write(
                            f"  {game.date_played} | user={c.user_id} "
                            f"{c.old_rating} → {c.new_rating} ({c.change:+d})"
                        )
            else:
                changes = apply_elo_changes(fmt, participants, game_record=game)
                for c in changes:
                    mem_ratings[c.user_id][fmt] = c.new_rating
                    mem_matches.setdefault(c.user_id, {})[fmt] = (
                        mem_matches.get(c.user_id, {}).get(fmt, 0) + 1
                    )

            processed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{'[DRY RUN] ' if dry_run else ''}"
                f"Processed {processed} game(s), skipped {skipped}."
            )
        )
