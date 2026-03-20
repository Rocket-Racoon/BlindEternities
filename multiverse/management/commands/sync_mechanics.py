# multiverse/management/commands/sync_mechanics.py
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from core.models import Mechanic
from core.constants import MechanicType


HEADERS = settings.SCRYFALL_HEADERS
TIMEOUT = settings.SCRYFALL_TIMEOUT_SHORT

TARGETS = {
    "keyword-abilities": MechanicType.KEYWORD,
    "keyword-actions":   MechanicType.ACTION,
    "ability-words":     MechanicType.ABILITYWORD,
}


class Command(BaseCommand):
    help = "Sincroniza mechanics desde Scryfall (keywords, actions, ability words)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra los datos sin guardar nada",
        )
        parser.add_argument(
            "--kind",
            type=str,
            choices=["keyword-abilities", "keyword-actions", "ability-words"],
            help="Sincroniza solo un tipo de mechanic",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        kind    = options.get("kind")
        start   = timezone.now()
        targets = {kind: TARGETS[kind]} if kind else TARGETS

        total_created = total_updated = 0

        for catalog_key, mechanic_kind in targets.items():
            self.stdout.write(f"Sincronizando {catalog_key}...")

            data = self._fetch(catalog_key)
            if data is None:
                continue

            count = len(data)

            if dry_run:
                self.stdout.write(self.style.WARNING(
                    f"  [dry-run] {catalog_key} — {count} entradas"
                ))
                if options["verbosity"] >= 2:
                    for name in data[:10]:
                        self.stdout.write(f"    {name}")
                    if count > 10:
                        self.stdout.write(f"    ... y {count - 10} más")
                continue

            created = updated = 0
            now     = timezone.now()

            for name in data:
                _, was_created = Mechanic.objects.update_or_create(
                    slug=slugify(name),
                    defaults={
                        "name":      name,
                        "kind":      mechanic_kind,
                        "synced_at": now,
                        "is_active": True,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

            total_created += created
            total_updated += updated

            self.stdout.write(self.style.SUCCESS(
                f"  {catalog_key} — creados: {created} | actualizados: {updated}"
            ))

        elapsed = (timezone.now() - start).total_seconds()

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"\nMechanics sincronizados en {elapsed:.1f}s — "
                f"creados: {total_created} | actualizados: {total_updated}"
            ))

    def _fetch(self, catalog_key):
        url = f"{settings.SCRYFALL_API_BASE}/catalog/{catalog_key}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.RequestException as e:
            self.stderr.write(self.style.ERROR(f"  Error en {catalog_key}: {e}"))
            return None