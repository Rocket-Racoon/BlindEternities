# multiverse/management/commands/sync_prices.py
import uuid
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from multiverse.models import CardPrint


SCRYFALL_BULK_PRICES = f"{settings.SCRYFALL_API_BASE}/bulk-data/all-cards"
HEADERS = settings.SCRYFALL_HEADERS
TIMEOUT = settings.SCRYFALL_TIMEOUT_SHORT
BATCH_SIZE = settings.SCRYFALL_BATCH_SIZE 


class Command(BaseCommand):
    help = "Sincroniza precios diarios desde Scryfall"

    def handle(self, *args, **options):
        start = timezone.now()
        self.stdout.write("Obteniendo URL de bulk data (all-cards)...")

        try:
            meta     = requests.get(SCRYFALL_BULK_PRICES, headers=HEADERS, timeout=15)
            meta.raise_for_status()
            data_url = meta.json().get("download_uri")

            self.stdout.write(f"Descargando precios desde {data_url}...")
            response = requests.get(data_url, headers=HEADERS, timeout=600)
            response.raise_for_status()
            all_cards = response.json()
        except requests.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
            return

        total    = len(all_cards)
        updated  = 0
        skipped  = 0

        self.stdout.write(f"Actualizando precios de {total} prints...")

        # Procesar en batches para no saturar la DB
        batches = [all_cards[i:i+BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]

        for i, batch in enumerate(batches, 1):
            self.stdout.write(f"  Batch {i}/{len(batches)}...")
            ids_in_batch = []
            prices_map   = {}

            for card_data in batch:
                scryfall_id = card_data.get("id")
                prices      = card_data.get("prices", {})
                if scryfall_id and prices:
                    try:
                        sid = uuid.UUID(scryfall_id)
                        ids_in_batch.append(sid)
                        prices_map[sid] = prices
                    except (ValueError, AttributeError):
                        continue

            # Bulk fetch de prints existentes
            prints = CardPrint.objects.filter(scryfall_id__in=ids_in_batch)

            for print_obj in prints:
                new_prices = prices_map.get(print_obj.scryfall_id)
                if new_prices and new_prices != print_obj.prices:
                    print_obj.prices = new_prices
                    print_obj.save(update_fields=["prices", "updated_at"])
                    updated += 1
                else:
                    skipped += 1

        elapsed = (timezone.now() - start).total_seconds()
        self.stdout.write(self.style.SUCCESS(
            f"\nPrecios actualizados en {elapsed:.1f}s — "
            f"actualizados: {updated} | sin cambios: {skipped}"
        ))