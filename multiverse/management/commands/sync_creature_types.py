# multiverse/management/commands/sync_creature_types.py
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from core.models import CreatureType


URL     = f"{settings.SCRYFALL_API_BASE}/catalog/creature-types"
HEADERS = settings.SCRYFALL_HEADERS
TIMEOUT = settings.SCRYFALL_TIMEOUT_SHORT


class Command(BaseCommand):
    help = "Sincroniza creature types desde Scryfall"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra los datos sin guardar nada",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        start   = timezone.now()

        self.stdout.write("Obteniendo creature types desde Scryfall...")

        try:
            response = requests.get(URL, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Error de red: {e}"))
            return

        data  = response.json().get("data", [])
        total = len(data)

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"[dry-run] {total} creature types encontrados:"
            ))
            for name in data[:20]:
                self.stdout.write(f"  {name}")
            if total > 20:
                self.stdout.write(f"  ... y {total - 20} más")
            return

        created = updated = 0
        now     = timezone.now()

        for name in data:
            _, was_created = CreatureType.objects.update_or_create(
                slug=slugify(name),
                defaults={
                    "name":      name,
                    "synced_at": now,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        elapsed = (timezone.now() - start).total_seconds()
        self.stdout.write(self.style.SUCCESS(
            f"Creature types sincronizados en {elapsed:.1f}s — "
            f"creados: {created} | actualizados: {updated} | total: {total}"
        ))