# phyrexian/management/commands/recalculate_tournament_stats.py
"""
Recalculate TournamentStats for all users from existing tournament data.

Usage:
    python manage.py recalculate_tournament_stats
    python manage.py recalculate_tournament_stats --user admin
    python manage.py recalculate_tournament_stats --magic-format commander
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from phyrexian.models import TournamentParticipant, TournamentStatus
from phyrexian.tournament import recompute_tournament_stats


class Command(BaseCommand):
    help = "Recalculate tournament stats for users from existing tournament data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user", help="Only recompute for one username.",
        )
        parser.add_argument(
            "--magic-format", help="Only recompute for one format.",
        )

    def handle(self, *args, **options):
        qs = TournamentParticipant.objects.filter(
            user__isnull=False,
            tournament__status=TournamentStatus.FINISHED,
        ).values_list("user_id", "tournament__format").distinct()

        if options["user"]:
            try:
                user = User.objects.get(username=options["user"])
                qs = qs.filter(user_id=user.pk)
            except User.DoesNotExist:
                self.stderr.write(f"User '{options['user']}' not found.")
                return
        if options["magic_format"]:
            qs = qs.filter(tournament__format=options["magic_format"])

        pairs = list(qs)
        self.stdout.write(f"Recomputing stats for {len(pairs)} (user, format) pair(s)...")

        for uid, fmt in pairs:
            recompute_tournament_stats(uid, fmt)
            self.stdout.write(f"  user_id={uid} format={fmt}")

        self.stdout.write(self.style.SUCCESS("Done."))
