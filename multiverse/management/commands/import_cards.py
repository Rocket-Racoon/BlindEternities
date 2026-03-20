# multiverse/management/commands/import_cards.py
import json
import uuid
import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from multiverse.models import Card, CardFace, CardPrint, CardSet, CardLegality, Ruling
# Al inicio de sync_cards.py e import_cards.py
from multiverse.utils import (
    compute_deck_rules,
    build_card_defaults,
    build_face_defaults,
    build_print_defaults,
    parse_uuid,
)


BATCH_SIZE = settings.SCRYFALL_BATCH_SIZE


class Command(BaseCommand):
    help = "Importa cartas desde un archivo JSON local (formato Scryfall bulk data)"

    def add_arguments(self, parser):
        parser.add_argument(
            "file",
            type=str,
            help="Ruta al archivo JSON (ej: C:/dumps/oracle-cards.json)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Procesa sin guardar nada",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limita el número de cartas procesadas (útil para pruebas)",
        )
        parser.add_argument(
            "--set",
            type=str,
            dest="set_code",
            help="Filtra solo las cartas de un set (ej: --set znr)",
        )
        parser.add_argument(
            "--skip-faces",
            action="store_true",
            help="No sincroniza CardFace",
        )
        parser.add_argument(
            "--skip-legality",
            action="store_true",
            help="No sincroniza CardLegality",
        )
        parser.add_argument(
            "--skip-prints",
            action="store_true",
            help="No sincroniza CardPrint",
        )

    def handle(self, *args, **options):
        filepath     = options["file"]
        dry_run      = options["dry_run"]
        limit        = options["limit"]
        set_code     = options.get("set_code", "").lower()
        skip_faces   = options["skip_faces"]
        skip_legality= options["skip_legality"]
        skip_prints  = options["skip_prints"]
        start        = timezone.now()

        # --- Validar archivo ---
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
            raise CommandError(
                "El archivo debe contener un array JSON de cartas. "
                "Asegúrate de usar el bulk data de oracle-cards de Scryfall."
            )

        total = len(cards_data)
        self.stdout.write(f"  {total} cartas encontradas en el archivo.")

        # --- Filtrar por set si se especificó ---
        if set_code:
            cards_data = [c for c in cards_data if c.get("set", "").lower() == set_code]
            self.stdout.write(
                f"  Filtrado a {len(cards_data)} cartas del set {set_code.upper()}."
            )

        # --- Aplicar límite ---
        if limit:
            cards_data = cards_data[:limit]
            self.stdout.write(self.style.WARNING(
                f"  Limitado a {limit} cartas."
            ))

        if not cards_data:
            self.stdout.write(self.style.WARNING("No hay cartas para procesar."))
            return

        # --- Procesar en batches ---
        self.stdout.write(f"Procesando {len(cards_data)} cartas...")

        created = updated = errors = 0
        batches = [
            cards_data[i:i+BATCH_SIZE]
            for i in range(0, len(cards_data), BATCH_SIZE)
        ]

        for i, batch in enumerate(batches, 1):
            self.stdout.write(f"  Batch {i}/{len(batches)}...")
            c, u, e = self._process_batch(
                batch,
                dry_run,
                skip_faces,
                skip_legality,
                skip_prints,
                options["verbosity"],
            )
            created += c
            updated += u
            errors  += e

        elapsed = (timezone.now() - start).total_seconds()

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\n[dry-run] {len(cards_data)} cartas procesadas en {elapsed:.1f}s — nada fue guardado."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nImportación completada en {elapsed:.1f}s — "
                f"creadas: {created} | actualizadas: {updated} | errores: {errors}"
            ))

    @transaction.atomic
    def _process_batch(self, batch, dry_run, skip_faces, skip_legality, skip_prints, verbosity):
        created = updated = errors = 0

        for data in batch:
            try:
                oracle_id = data.get("oracle_id")
                if not oracle_id:
                    if verbosity >= 2:
                        self.stdout.write(
                            self.style.WARNING(f"    Sin oracle_id: {data.get('name', '?')}")
                        )
                    continue

                if dry_run:
                    if verbosity >= 2:
                        self.stdout.write(f"    [dry-run] {data.get('name')}")
                    continue

                # --- Card ---
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
                    action = "+" if was_created else "~"
                    self.stdout.write(f"    {action} {card.name}")

                # --- CardFaces ---
                if not skip_faces and data.get("card_faces"):
                    self._sync_faces(card, data["card_faces"])

                # --- CardLegality ---
                if not skip_legality and data.get("legalities"):
                    CardLegality.objects.update_or_create(
                        card=card,
                        defaults={"data": data["legalities"]},
                    )

                # --- CardPrint ---
                if not skip_prints and data.get("id"):
                    self._sync_print(card, data)

            except Exception as e:
                errors += 1
                self.stderr.write(
                    self.style.ERROR(f"    Error en {data.get('name', '?')}: {e}")
                )

        return created, updated, errors

    def _sync_faces(self, card, faces_data):
        for i, face_data in enumerate(faces_data):
            CardFace.objects.update_or_create(
                card=card,
                face_index=i,
                defaults=build_face_defaults(face_data),
            )

    def _sync_print(self, card, data):
        scryfall_id = data.get("id")
        if not scryfall_id:
            return
        set_code = data.get("set", "").lower()
        try:
            cardset = CardSet.objects.get(code=set_code)
        except CardSet.DoesNotExist:
            self.stderr.write(
                self.style.WARNING(f"      Set no encontrado: {set_code}")
            )
            return
        CardPrint.objects.update_or_create(
            scryfall_id=parse_uuid(scryfall_id),
            defaults=build_print_defaults(card, cardset, data),
        )
