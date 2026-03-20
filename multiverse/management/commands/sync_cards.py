# multiverse/management/commands/sync_cards.py
import uuid
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
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


SCRYFALL_BULK_URL  = f"{settings.SCRYFALL_API_BASE}/bulk-data/oracle-cards"
SCRYFALL_SET_URL   = f"{settings.SCRYFALL_API_BASE}/cards/search"
HEADERS = settings.SCRYFALL_HEADERS
TIMEOUT = settings.SCRYFALL_TIMEOUT_SHORT
BATCH_SIZE = settings.SCRYFALL_BATCH_SIZE 


class Command(BaseCommand):
    help = "Sincroniza cartas desde Scryfall via bulk data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--set",
            type=str,
            dest="set_code",
            help="Sincroniza solo las cartas de un set (ej: --set znr)",
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
            "--skip-faces",
            action="store_true",
            help="No sincroniza CardFace (más rápido)",
        )
        parser.add_argument(
            "--skip-legality",
            action="store_true",
            help="No sincroniza CardLegality",
        )

    def handle(self, *args, **options):
        dry_run      = options["dry_run"]
        set_code     = options.get("set_code", "").lower()
        limit        = options["limit"]
        skip_faces   = options["skip_faces"]
        skip_legality= options["skip_legality"]
        start        = timezone.now()

        # --- Obtener datos ---
        if set_code:
            cards_data = self._fetch_set(set_code)
        else:
            cards_data = self._fetch_bulk()

        if cards_data is None:
            return

        total = len(cards_data)
        if limit:
            cards_data = cards_data[:limit]
            self.stdout.write(
                self.style.WARNING(f"Limitado a {limit} cartas de {total} disponibles.")
            )

        self.stdout.write(f"Procesando {len(cards_data)} cartas...")

        # --- Procesar en batches ---
        created = updated = errors = 0
        batches = [cards_data[i:i+BATCH_SIZE] for i in range(0, len(cards_data), BATCH_SIZE)]

        for i, batch in enumerate(batches, 1):
            self.stdout.write(f"  Batch {i}/{len(batches)}...")
            c, u, e = self._process_batch(
                batch, dry_run, skip_faces, skip_legality, options["verbosity"]
            )
            created += c
            updated += u
            errors  += e

        elapsed = (timezone.now() - start).total_seconds()
        self.stdout.write(self.style.SUCCESS(
            f"\nCartas sincronizadas en {elapsed:.1f}s — "
            f"creadas: {created} | actualizadas: {updated} | errores: {errors}"
        ))

    def _fetch_bulk(self):
        """Descarga el bulk data de oracle cards desde Scryfall."""
        self.stdout.write("Obteniendo URL de bulk data...")
        try:
            meta     = requests.get(SCRYFALL_BULK_URL, headers=HEADERS, timeout=15)
            meta.raise_for_status()
            data_url = meta.json().get("download_uri")

            self.stdout.write(f"Descargando bulk data desde {data_url}...")
            response = requests.get(data_url, headers=HEADERS, timeout=300)
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Error descargando bulk data: {e}"))
            return None

    def _fetch_set(self, set_code):
        """Obtiene cartas de un set específico via search API."""
        self.stdout.write(f"Obteniendo cartas del set {set_code.upper()}...")
        cards = []
        url   = f"{SCRYFALL_SET_URL}?q=set:{set_code}&unique=cards"

        while url:
            try:
                response = requests.get(url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                data = response.json()
                cards.extend(data.get("data", []))
                url = data.get("next_page")
            except requests.RequestException as e:
                self.stderr.write(self.style.ERROR(f"Error: {e}"))
                break

        return cards

    @transaction.atomic
    def _process_batch(self, batch, dry_run, skip_faces, skip_legality, verbosity):
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

                # --- CardPrint (el print default incluido en oracle-cards) ---
                if data.get("id"):
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
