import logging
import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from multiverse.models import CardPrint
from omenpath.models import PriceQuote
from omenpath.pricing import ADAPTERS


log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Refresh cached market prices from configured external sources (TCGPlayer, Cardmarket, Scryfall)."

    def add_arguments(self, parser):
        parser.add_argument("--source", choices=list(ADAPTERS.keys()), help="Limit to a single source.")
        parser.add_argument("--set", help="Only prints in this set code.")
        parser.add_argument("--stale-hours", type=int, default=24,
                            help="Skip prints with fresh quotes newer than this (default 24h).")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--delay", type=float, default=0.1, help="Seconds between API calls.")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        sources = [opts["source"]] if opts["source"] else list(ADAPTERS.keys())
        sources = [s for s in sources if ADAPTERS[s].is_configured()]
        if not sources:
            self.stdout.write(self.style.WARNING("No configured price sources — nothing to do."))
            return

        cutoff = timezone.now() - timedelta(hours=opts["stale_hours"])
        qs = CardPrint.objects.all()
        if opts["set"]:
            qs = qs.filter(cardset__code__iexact=opts["set"])
        if opts["limit"]:
            qs = qs[: opts["limit"]]

        total_prints = qs.count()
        self.stdout.write(f"Refreshing {total_prints} prints from: {', '.join(sources)}")

        updated = 0
        for i, card_print in enumerate(qs.iterator(chunk_size=200), start=1):
            for source_id in sources:
                adapter = ADAPTERS[source_id]
                fresh = PriceQuote.objects.filter(
                    card_print=card_print, source=source_id, fetched_at__gte=cutoff,
                ).exists()
                if fresh:
                    continue
                try:
                    results = adapter.fetch(card_print)
                except Exception as exc:
                    log.warning("price fetch failed: source=%s print=%s err=%s", source_id, card_print.pk, exc)
                    continue
                if opts["dry_run"]:
                    for r in results:
                        self.stdout.write(f"  [{source_id}] {card_print} {r.finish} {r.price} {r.currency}")
                    continue
                with transaction.atomic():
                    for r in results:
                        PriceQuote.objects.update_or_create(
                            card_print=card_print,
                            source=source_id,
                            finish=r.finish,
                            currency=r.currency,
                            defaults={"price": r.price, "raw": r.raw},
                        )
                        updated += 1
                if opts["delay"]:
                    time.sleep(opts["delay"])
            if i % 500 == 0:
                self.stdout.write(f"  …{i}/{total_prints}")

        self.stdout.write(self.style.SUCCESS(f"Done. {updated} price quotes written."))
