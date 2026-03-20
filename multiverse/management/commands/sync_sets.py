# multiverse/management/commands/sync_sets.py
import re
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from multiverse.models import CardSet
from core.constants import CardSetType, UNSET_CODES


SETS_URL   = f"{settings.SCRYFALL_API_BASE}/sets"
HEADERS    = settings.SCRYFALL_HEADERS
BATCH_SIZE = settings.SCRYFALL_BATCH_SIZE

HEROES_PATTERN   = re.compile(r'^PH\d+$', re.IGNORECASE)
FRONTCARDS_WORDS = "front cards"
ART_WORDS        = "art series"
SCENE_WORDS      = "scene box"
JUMPSTART_WORDS  = "jumpstart"


def resolve_set_type(code, name, scryfall_type):
    """
    Determina el set_type final aplicando nuestras reglas de negocio
    sobre el set_type que viene de Scryfall.
    """
    code_lower = code.lower()
    name_lower = name.lower()

    if code_lower in UNSET_CODES:
        return CardSetType.UNSET

    if HEROES_PATTERN.match(code):
        return CardSetType.HEROES

    if FRONTCARDS_WORDS in name_lower:
        return CardSetType.FRONTCARDS

    if ART_WORDS in name_lower:
        return CardSetType.ART

    if SCENE_WORDS in name_lower:
        return CardSetType.SCENE

    if JUMPSTART_WORDS in name_lower:
        return CardSetType.JUMPSTART

    # Sin override — usar el tipo de Scryfall
    return scryfall_type


class Command(BaseCommand):
    help = "Sincroniza los sets de Magic desde Scryfall"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué se actualizaría sin guardar nada",
        )
        parser.add_argument(
            "--code",
            type=str,
            help="Sincroniza solo un set específico (ej: --code znr)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        code    = options.get("code", "").lower()
        start   = timezone.now()

        self.stdout.write("Obteniendo sets desde Scryfall...")

        try:
            response = requests.get(SETS_URL, headers=HEADERS, timeout=settings.SCRYFALL_TIMEOUT_SHORT)
            response.raise_for_status()
        except requests.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Error de red: {e}"))
            return

        sets  = response.json().get("data", [])
        total = len(sets)

        if code:
            sets = [s for s in sets if s.get("code", "").lower() == code]
            if not sets:
                self.stderr.write(self.style.ERROR(f"Set '{code}' no encontrado en Scryfall."))
                return

        created = updated = 0
        self.stdout.write(f"Procesando {len(sets)} sets...")

        for data in sets:
            set_code = data.get("code", "").lower()
            set_name = data.get("name", "")

            if dry_run:
                resolved = resolve_set_type(set_code, set_name, data.get("set_type", ""))
                original = data.get("set_type", "")
                override = f" → {resolved}" if resolved != original else ""
                self.stdout.write(f"  [dry-run] {set_code} — {set_name} ({original}{override})")
                continue

            defaults = self._build_defaults(data)

            obj, was_created = CardSet.objects.update_or_create(
                code=set_code,
                defaults=defaults,
            )

            if was_created:
                created += 1
                if options["verbosity"] >= 2:
                    self.stdout.write(f"  + {set_code} — {obj.name} [{obj.set_type}]")
            else:
                updated += 1
                if options["verbosity"] >= 2:
                    self.stdout.write(f"  ~ {set_code} — {obj.name} [{obj.set_type}]")

        elapsed = (timezone.now() - start).total_seconds()

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"\nSets sincronizados en {elapsed:.1f}s — "
                f"creados: {created} | actualizados: {updated} | total: {total}"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"\n[dry-run] {len(sets)} sets encontrados — nada fue guardado."
            ))

    def _build_defaults(self, data):
        code     = data.get("code", "").lower()
        name     = data.get("name", "")
        set_type = resolve_set_type(code, name, data.get("set_type", ""))

        return {
            "scryfall_id":     self._uuid(data.get("id")),
            "mtgo_code":       data.get("mtgo_code", ""),
            "arena_code":      data.get("arena_code", ""),
            "tcgplayer_id":    data.get("tcgplayer_id"),
            "cardmarket_id":   data.get("cardmarket_id"),
            "name":            name,
            "set_type":        set_type,
            "released_at":     data.get("released_at"),
            "block_code":      data.get("block_code", ""),
            "block":           data.get("block", ""),
            "parent_set_code": data.get("parent_set_code", ""),
            "card_count":      data.get("card_count", 0),
            "printed_size":    data.get("printed_size"),
            "digital":         data.get("digital", False),
            "foil_only":       data.get("foil_only", False),
            "nonfoil_only":    data.get("nonfoil_only", False),
            "icon_svg_uri":    data.get("icon_svg_uri", ""),
            "search_uri":      data.get("search_uri", ""),
            "scryfall_uri":    data.get("scryfall_uri", ""),
            "is_active":       True,
        }

    def _uuid(self, value):
        if not value:
            return None
        try:
            import uuid
            return uuid.UUID(str(value))
        except (ValueError, AttributeError):
            return None