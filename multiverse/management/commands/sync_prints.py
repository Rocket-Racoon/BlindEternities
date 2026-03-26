# multiverse/management/commands/sync_prints.py
"""
Syncs ALL card prints from Scryfall's default-cards bulk data.

Each printing (set + collector_number + lang) gets its own CardPrint with
correct image_uris, prices, and print-specific metadata.

Run after sync_cards and sync_sets so Card and CardSet rows exist.
"""
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from multiverse.models import Card, CardPrint, CardSet
from multiverse.utils import build_print_defaults, parse_uuid


BULK_URL   = f"{settings.SCRYFALL_API_BASE}/bulk-data/default-cards"
HEADERS    = settings.SCRYFALL_HEADERS
BATCH_SIZE = settings.SCRYFALL_BATCH_SIZE


class Command(BaseCommand):
    help = "Sincroniza TODOS los prints desde Scryfall (default-cards)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument(
            "--set", type=str, dest="set_code",
            help="Solo prints de un set (ej: --set znr)",
        )
        parser.add_argument(
            "--lang", type=str, default="",
            help="Solo prints de un idioma (ej: --lang en)",
        )

    def handle(self, *args, **options):
        dry_run  = options["dry_run"]
        limit    = options["limit"]
        set_code = (options.get("set_code") or "").lower()
        lang     = (options.get("lang") or "").lower()
        start    = timezone.now()

        # Download
        self.stdout.write("Obteniendo URL de default-cards bulk data...")
        try:
            meta = requests.get(BULK_URL, headers=HEADERS, timeout=15)
            meta.raise_for_status()
            data_url = meta.json().get("download_uri")
            self.stdout.write(f"Descargando desde {data_url}...")
            resp = requests.get(data_url, headers=HEADERS, timeout=600)
            resp.raise_for_status()
            all_data = resp.json()
        except requests.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
            return

        # Filter
        if set_code:
            all_data = [d for d in all_data if d.get("set", "").lower() == set_code]
        if lang:
            all_data = [d for d in all_data if d.get("lang", "").lower() == lang]

        total = len(all_data)
        if limit:
            all_data = all_data[:limit]

        self.stdout.write(f"Procesando {len(all_data)} prints (de {total} filtrados)...")

        # Pre-load lookups
        self.stdout.write("Cargando Cards y Sets en memoria...")
        card_map = {str(c.oracle_id): c for c in Card.objects.only("id", "oracle_id")}
        set_map  = {s.code: s for s in CardSet.objects.only("id", "code")}
        self.stdout.write(f"  {len(card_map)} cards, {len(set_map)} sets en cache.")

        created = updated = skipped = errors = 0
        batches = [all_data[i:i+BATCH_SIZE] for i in range(0, len(all_data), BATCH_SIZE)]

        for i, batch in enumerate(batches, 1):
            if i % 10 == 1 or i == len(batches):
                self.stdout.write(
                    f"  Batch {i}/{len(batches)} — "
                    f"creados: {created} | actualizados: {updated} | "
                    f"omitidos: {skipped} | errores: {errors}"
                )
            c, u, s, e = self._process_batch(batch, card_map, set_map, dry_run)
            created += c
            updated += u
            skipped += s
            errors  += e

        elapsed = (timezone.now() - start).total_seconds()
        self.stdout.write(self.style.SUCCESS(
            f"\nPrints sincronizados en {elapsed:.1f}s — "
            f"creados: {created} | actualizados: {updated} | "
            f"omitidos: {skipped} | errores: {errors}"
        ))

    @transaction.atomic
    def _process_batch(self, batch, card_map, set_map, dry_run):
        created = updated = skipped = errors = 0

        for data in batch:
            try:
                scryfall_id = data.get("id")
                oracle_id   = data.get("oracle_id", "")
                set_code    = data.get("set", "").lower()

                if not scryfall_id or not oracle_id:
                    skipped += 1
                    continue

                card = card_map.get(oracle_id)
                if not card:
                    skipped += 1
                    continue

                cardset = set_map.get(set_code)
                if not cardset:
                    skipped += 1
                    continue

                if dry_run:
                    continue

                _, was_created = CardPrint.objects.update_or_create(
                    scryfall_id=parse_uuid(scryfall_id),
                    defaults=build_print_defaults(card, cardset, data),
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

            except Exception as e:
                errors += 1

        return created, updated, skipped, errors
