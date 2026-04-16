# phyrexian/management/commands/export_elo.py
"""
Export ELO ratings and history to CSV.

Usage:
    python manage.py export_elo --output ratings.csv
    python manage.py export_elo --history --output history.csv
    python manage.py export_elo --magic-format commander
"""
import csv
from django.core.management.base import BaseCommand
from phyrexian.models import EloRating, EloHistory


class Command(BaseCommand):
    help = "Export ELO ratings or history to CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output", "-o", default="-",
            help="Output file path (default: stdout).",
        )
        parser.add_argument(
            "--magic-format", help="Filter by Magic format.",
        )
        parser.add_argument(
            "--history", action="store_true",
            help="Export full rating history instead of current ratings.",
        )

    def handle(self, *args, **options):
        import sys
        if options["history"]:
            self._export_history(options)
        else:
            self._export_ratings(options)
        self.stdout.write(self.style.SUCCESS("Done."))

    def _export_ratings(self, options):
        import sys
        qs = (
            EloRating.objects
            .filter(matches_played__gt=0)
            .select_related("user")
            .order_by("-rating")
        )
        if options["magic_format"]:
            qs = qs.filter(format=options["magic_format"])

        f = sys.stdout if options["output"] == "-" else open(options["output"], "w", newline="", encoding="utf-8")
        try:
            writer = csv.writer(f)
            writer.writerow(["user", "format", "rating", "matches", "wins", "losses", "draws", "peak"])
            for r in qs:
                writer.writerow([
                    r.user.username, r.format, r.rating,
                    r.matches_played, r.wins, r.losses, r.draws, r.peak_rating,
                ])
        finally:
            if f is not sys.stdout:
                f.close()

    def _export_history(self, options):
        import sys
        qs = (
            EloHistory.objects
            .select_related("user", "game")
            .order_by("-created_at")
        )
        if options["magic_format"]:
            qs = qs.filter(format=options["magic_format"])

        f = sys.stdout if options["output"] == "-" else open(options["output"], "w", newline="", encoding="utf-8")
        try:
            writer = csv.writer(f)
            writer.writerow(["date", "user", "format", "old_rating", "new_rating", "change", "game_id"])
            for h in qs:
                writer.writerow([
                    h.created_at.isoformat(), h.user.username, h.format,
                    h.old_rating, h.new_rating, h.change,
                    str(h.game_id) if h.game_id else "",
                ])
        finally:
            if f is not sys.stdout:
                f.close()
