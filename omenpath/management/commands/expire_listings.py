"""
Flip OPEN listings whose `expires_at` has passed to EXPIRED.

Run from cron / Windows Task Scheduler — daily is plenty since listing-list
queries already defensively filter on `expires_at`.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from omenpath.models import Listing, ListingStatus


class Command(BaseCommand):
    help = "Mark OPEN listings past their expires_at as EXPIRED."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report how many listings would be expired without changing them.",
        )

    def handle(self, *args, **opts):
        now = timezone.now()
        qs = Listing.objects.filter(
            is_active=True,
            status=ListingStatus.OPEN,
            expires_at__isnull=False,
            expires_at__lte=now,
        )
        count = qs.count()
        if opts["dry_run"]:
            self.stdout.write(self.style.NOTICE(f"[dry-run] would expire {count} listing(s)."))
            return
        if count:
            qs.update(status=ListingStatus.EXPIRED, updated_at=now)
        self.stdout.write(self.style.SUCCESS(f"Expired {count} listing(s)."))
