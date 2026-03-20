# multiverse/management/commands/sync_rulings.py
import uuid
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from multiverse.models import Card, Ruling


SCRYFALL_BULK_RULINGS = f"{settings.SCRYFALL_API_BASE}/bulk-data/rulings"
HEADERS = settings.SCRYFALL_HEADERS
TIMEOUT = settings.SCRYFALL_TIMEOUT_SHORT
BATCH_SIZE = settings.SCRYFALL_BATCH_SIZE 


class Command(BaseCommand):
    help = "Sincroniza rulings (erratas) desde Scryfall"

    def add_arguments(self, parser):
        parser.add_argument(
            "--oracle-id",
            type=str,
            help="Sincroniza rulings de una sola carta por oracle_id",
        )

    def handle(self, *args, **options):
        start     = timezone.now()
        oracle_id = options.get("oracle_id")

        if oracle_id:
            self._sync_single(oracle_id, options["verbosity"])
        else:
            self._sync_bulk(options["verbosity"])

        elapsed = (timezone.now() - start).total_seconds()
        self.stdout.write(self.style.SUCCESS(
            f"\nRulings sincronizados en {elapsed:.1f}s"
        ))

    def _sync_bulk(self, verbosity):
        self.stdout.write("Descargando bulk data de rulings...")
        try:
            meta     = requests.get(SCRYFALL_BULK_RULINGS, headers=HEADERS, timeout=15)
            meta.raise_for_status()
            data_url = meta.json().get("download_uri")

            response = requests.get(data_url, headers=HEADERS, timeout=300)
            response.raise_for_status()
            rulings  = response.json()
        except requests.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
            return

        self.stdout.write(f"Procesando {len(rulings)} rulings...")
        created = updated = skipped = 0

        # Prefetch oracle_ids existentes
        card_map = {
            str(c.oracle_id): c
            for c in Card.objects.only("id", "oracle_id")
        }

        batches = [rulings[i:i+BATCH_SIZE] for i in range(0, len(rulings), BATCH_SIZE)]

        for i, batch in enumerate(batches, 1):
            if verbosity >= 2:
                self.stdout.write(f"  Batch {i}/{len(batches)}...")

            for ruling_data in batch:
                oracle_id = ruling_data.get("oracle_id")
                card      = card_map.get(oracle_id)

                if not card:
                    skipped += 1
                    continue

                obj, was_created = Ruling.objects.get_or_create(
                    card=card,
                    published_at=ruling_data.get("published_at"),
                    comment=ruling_data.get("comment", ""),
                    defaults={
                        "source":    ruling_data.get("source", ""),
                        "is_active": True,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Rulings — creados: {created} | ya existían: {updated} | sin carta: {skipped}"
        ))

    def _sync_single(self, oracle_id, verbosity):
        try:
            card = Card.objects.get(oracle_id=uuid.UUID(oracle_id))
        except (Card.DoesNotExist, ValueError):
            self.stderr.write(self.style.ERROR(f"Carta no encontrada: {oracle_id}"))
            return

        url = f"{settings.SCRYFALL_API_BASE}/cards/{oracle_id}/rulings"
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            rulings  = response.json().get("data", [])
        except requests.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
            return

        created = 0
        for ruling_data in rulings:
            _, was_created = Ruling.objects.get_or_create(
                card=card,
                published_at=ruling_data.get("published_at"),
                comment=ruling_data.get("comment", ""),
                defaults={"source": ruling_data.get("source", "")},
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"{card.name} — {created} rulings nuevos de {len(rulings)} totales"
        ))