# phyrexian/management/commands/export_games.py
"""
Export game records to CSV or JSON.

Usage:
    python manage.py export_games --format csv --output games.csv
    python manage.py export_games --format json --output games.json
    python manage.py export_games --user admin --magic-format commander
"""
import csv
import json
from django.core.management.base import BaseCommand
from phyrexian.models import GameRecord


class Command(BaseCommand):
    help = "Export game records to CSV or JSON."

    def add_arguments(self, parser):
        parser.add_argument(
            "--format", choices=["csv", "json"], default="csv",
            help="Output format (default: csv).",
        )
        parser.add_argument(
            "--output", "-o", default="-",
            help="Output file path (default: stdout).",
        )
        parser.add_argument(
            "--user", help="Filter by username.",
        )
        parser.add_argument(
            "--magic-format", help="Filter by Magic format (e.g. commander).",
        )
        parser.add_argument(
            "--from-date", help="Filter games from this date (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--to-date", help="Filter games up to this date (YYYY-MM-DD).",
        )

    def handle(self, *args, **options):
        qs = (
            GameRecord.objects
            .filter(is_active=True)
            .select_related("user", "deck")
            .prefetch_related("opponents")
            .order_by("-date_played")
        )
        if options["user"]:
            qs = qs.filter(user__username=options["user"])
        if options["magic_format"]:
            qs = qs.filter(format=options["magic_format"])
        if options["from_date"]:
            qs = qs.filter(date_played__gte=options["from_date"])
        if options["to_date"]:
            qs = qs.filter(date_played__lte=options["to_date"])

        records = list(qs)
        self.stdout.write(f"Exporting {len(records)} game(s)...")

        if options["format"] == "json":
            self._export_json(records, options["output"])
        else:
            self._export_csv(records, options["output"])

        self.stdout.write(self.style.SUCCESS("Done."))

    def _export_csv(self, records, output):
        import sys
        f = sys.stdout if output == "-" else open(output, "w", newline="", encoding="utf-8")
        try:
            writer = csv.writer(f)
            writer.writerow([
                "id", "user", "date", "format", "result", "deck", "commanders",
                "placement", "elimination_cause", "elimination_turn",
                "eliminator", "turns", "opponents", "notes",
            ])
            for g in records:
                opponents = "; ".join(
                    f"{o.name} ({o.deck_name})" for o in g.opponents.all()
                )
                writer.writerow([
                    str(g.pk), g.user.username, g.date_played, g.format,
                    g.result, g.deck.name if g.deck else "",
                    ", ".join(g.my_commanders or []),
                    g.my_placement, g.elimination_cause, g.elimination_turn or "",
                    g.eliminator_name, g.turns or "", opponents, g.notes,
                ])
        finally:
            if f is not sys.stdout:
                f.close()

    def _export_json(self, records, output):
        import sys
        data = []
        for g in records:
            data.append({
                "id": str(g.pk),
                "user": g.user.username,
                "date": str(g.date_played),
                "format": g.format,
                "result": g.result,
                "deck": g.deck.name if g.deck else None,
                "commanders": g.my_commanders or [],
                "placement": g.my_placement,
                "elimination_cause": g.elimination_cause,
                "elimination_turn": g.elimination_turn,
                "eliminator": g.eliminator_name,
                "turns": g.turns,
                "notes": g.notes,
                "opponents": [
                    {
                        "name": o.name,
                        "deck_name": o.deck_name,
                        "commanders": o.commanders or [],
                        "placement": o.placement,
                        "elimination_cause": o.elimination_cause,
                        "elimination_turn": o.elimination_turn,
                        "eliminator": o.eliminator_name,
                    }
                    for o in g.opponents.all()
                ],
            })
        text = json.dumps(data, indent=2, ensure_ascii=False)
        if output == "-":
            sys.stdout.write(text + "\n")
        else:
            with open(output, "w", encoding="utf-8") as f:
                f.write(text)
