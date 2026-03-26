# multiverse/management/commands/import_cards.py
"""
Imports cards from a local Scryfall JSON dump file.

Handles Card, CardFace, CardLegality, and optionally CardPrint.
For full print coverage, use sync_prints after importing.
"""
import json
import uuid
import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from multiverse.models import Card, CardFace, CardPrint, CardSet, CardLegality
from multiverse.utils import (
    compute_deck_rules,
    build_card_defaults,
    build_face_defaults,
    build_print_defaults,
    parse_uuid,
)


BATCH_SIZE = settings.SCRYFALL_BATCH_SIZE


class Command(BaseCommand):
    help = "Importa cartas desde un archivo JSON local (formato Scryfall bulk)"

    def add_arguments(self, parser):
        parser.add_argument("file", type=str, help="Ruta al JSON")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--set", type=str, dest="set_code")
        parser.add_argument("--skip-faces", action="store_true")
        parser.add_argument("--skip-legality", action="store_true")
        parser.add_argument(
            "--with-prints", action="store_true",
            help="Also create CardPrint from the data (default: skip, use sync_prints instead)",
        )

    def handle(self, *args, **options):
        filepath      = options["file"]
        dry_run       = options["dry_run"]
        limit         = options["limit"]
        set_code      = (options.get("set_code") or "").lower()
        skip_faces    = options["skip_faces"]
        skip_legality = options["skip_legality"]
        with_prints   = options["with_prints"]
        verbosity     = options["verbosity"]
        start         = timezone.now()

        if not os.path.exists(filepath):
            raise CommandError(f"Archivo no encontrado: {filepath}")
        if not filepath.endswith(".json"):
            raise CommandError("El archivo debe ser .json")

        file_size = os.path.getsize(filepath) / (1024 * 1024)
        self.stdout.write(f"Leyendo {filepath} ({file_size:.1f} MB)...")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                cards_data = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f"JSON inválido: {e}")

        if not isinstance(cards_data, list):
            raise CommandError("El archivo debe contener un array JSON de cartas.")

        total = len(cards_data)
        self.stdout.write(f"  {total} entradas encontradas.")

        if set_code:
            cards_data = [c for c in cards_data if c.get("set", "").lower() == set_code]
            self.stdout.write(f"  Filtrado a {len(cards_data)} del set {set_code.upper()}.")

        if limit:
            cards_data = cards_data[:limit]
            self.stdout.write(self.style.WARNING(f"  Limitado a {limit} cartas."))

        if not cards_data:
            self.stdout.write(self.style.WARNING("No hay cartas para procesar."))
            return

        self.stdout.write(f"Procesando {len(cards_data)} cartas...")

        created = updated = errors = 0
        batches = [cards_data[i:i+BATCH_SIZE] for i in range(0, len(cards_data), BATCH_SIZE)]

        for i, batch in enumerate(batches, 1):
            self.stdout.write(f"  Batch {i}/{len(batches)}...")
            c, u, e = self._process_batch(
                batch, dry_run, skip_faces, skip_legality, with_prints, verbosity,
            )
            created += c
            updated += u
            errors  += e

        elapsed = (timezone.now() - start).total_seconds()
        self.stdout.write(self.style.SUCCESS(
            f"\nImportación en {elapsed:.1f}s — "
            f"creadas: {created} | actualizadas: {updated} | errores: {errors}"
        ))

    @transaction.atomic
    def _process_batch(self, batch, dry_run, skip_faces, skip_legality, with_prints, verbosity):
        created = updated = errors = 0

        for data in batch:
            try:
                oracle_id = data.get("oracle_id")
                if not oracle_id:
                    continue

                if dry_run:
                    if verbosity >= 2:
                        self.stdout.write(f"    [dry-run] {data.get('name')}")
                    continue

                # Card
                deck_rules    = compute_deck_rules(data)
                card_defaults = build_card_defaults(data, deck_rules)
                card, was_created = Card.objects.update_or_create(
                    oracle_id=uuid.UUID(oracle_id),
                    defaults=card_defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

                if verbosity >= 2:
                    self.stdout.write(f"    {'+'if was_created else '~'} {card.name}")

                # CardFaces
                if not skip_faces and data.get("card_faces"):
                    for i, face in enumerate(data["card_faces"]):
                        CardFace.objects.update_or_create(
                            card=card, face_index=i,
                            defaults=build_face_defaults(face),
                        )

                # CardLegality
                if not skip_legality and data.get("legalities"):
                    CardLegality.objects.update_or_create(
                        card=card,
                        defaults={"data": data["legalities"]},
                    )

                # CardPrint (opt-in)
                if with_prints and data.get("id"):
                    set_code = data.get("set", "").lower()
                    try:
                        cardset = CardSet.objects.get(code=set_code)
                    except CardSet.DoesNotExist:
                        continue
                    CardPrint.objects.update_or_create(
                        scryfall_id=parse_uuid(data["id"]),
                        defaults=build_print_defaults(card, cardset, data),
                    )

            except Exception as e:
                errors += 1
                self.stderr.write(self.style.ERROR(
                    f"    Error en {data.get('name', '?')}: {e}"
                ))

        return created, updated, errors
