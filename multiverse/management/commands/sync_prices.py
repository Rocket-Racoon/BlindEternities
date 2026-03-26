# multiverse/management/commands/sync_prices.py
"""
Updates prices on existing CardPrint records from Scryfall bulk data.
Only touches the prices field — does not create or delete prints.
"""
import uuid
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from multiverse.models import CardPrint


BULK_URL   = f"{settings.SCRYFALL_API_BASE}/bulk-data/default-cards"
HEADERS    = settings.SCRYFALL_HEADERS
BATCH_SIZE = settings.SCRYFALL_BATCH_SIZE


class Command(BaseCommand):
    help = "Actualiza precios de CardPrint desde Scryfall (default-cards)"

    def handle(self, *args, **options):
        start = timezone.now()
        self.stdout.write("Obteniendo URL de default-cards bulk data...")

        try:
            meta = requests.get(BULK_URL, headers=HEADERS, timeout=15)
            meta.raise_for_status()
            data_url = meta.json().get("download_uri")
            self.stdout.write(f"Descargando desde {data_url}...")
            resp = requests.get(data_url, headers=HEADERS, timeout=600)
            resp.raise_for_status()
            all_cards = resp.json()
        except requests.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
            return

        total   = len(all_cards)
        updated = skipped = 0
        self.stdout.write(f"Actualizando precios de {total} prints...")

        batches = [all_cards[i:i+BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]

        for i, batch in enumerate(batches, 1):
            if i % 20 == 1 or i == len(batches):
                self.stdout.write(f"  Batch {i}/{len(batches)} — actualizados: {updated}")

            # Build scryfall_id → prices map
            prices_map = {}
            for card_data in batch:
                sid    = card_data.get("id")
                prices = card_data.get("prices")
                if sid and prices:
                    try:
                        prices_map[uuid.UUID(sid)] = prices
                    except (ValueError, AttributeError):
                        continue

            # Bulk fetch existing prints
            prints = CardPrint.objects.filter(scryfall_id__in=prices_map.keys())
            to_update = []
            for p in prints:
                new_prices = prices_map.get(p.scryfall_id)
                if new_prices and new_prices != p.prices:
                    p.prices = new_prices
                    to_update.append(p)

            if to_update:
                CardPrint.objects.bulk_update(to_update, ["prices", "updated_at"])
                updated += len(to_update)
            skipped += len(batch) - len(to_update)

        elapsed = (timezone.now() - start).total_seconds()
        self.stdout.write(self.style.SUCCESS(
            f"\nPrecios actualizados en {elapsed:.1f}s — "
            f"actualizados: {updated} | sin cambios: {skipped}"
        ))
