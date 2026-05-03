"""
Bulk-tag MTG cards using a local Ollama model.

By default tags only cards that don't yet have a CardTag row. Use --retag
to re-tag everything (or a filtered subset). Re-tagging overwrites the
existing CardTag for that card.

Examples:
    python manage.py tag_cards
    python manage.py tag_cards --limit 100
    python manage.py tag_cards --set znr
    python manage.py tag_cards --retag --concurrency 8
    python manage.py tag_cards --model qwen2.5 --vocab-only
    python manage.py tag_cards --dry-run --limit 20
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from multiverse.models import Card

from conflux.models import CardTag
from conflux.tagger import tag_cards_concurrent
from conflux.vocabulary import VOCABULARY_VERSION


class Command(BaseCommand):
    help = "Classify MTG cards via Ollama and store function + theme tags."

    def add_arguments(self, parser):
        parser.add_argument(
            "--set", dest="set_code",
            help="Restrict to cards with at least one print in this set code (case-insensitive).",
        )
        parser.add_argument(
            "--limit", type=int,
            help="Only process the first N matching cards (after the un-tagged filter).",
        )
        parser.add_argument(
            "--retag", action="store_true",
            help="Re-tag cards that already have a CardTag row.",
        )
        parser.add_argument(
            "--vocab-only", action="store_true",
            help="Re-tag only cards whose stored vocabulary_version is older than the current one.",
        )
        parser.add_argument(
            "--concurrency", type=int, default=5,
            help="Max concurrent Ollama requests (default: 5). Higher needs more VRAM.",
        )
        parser.add_argument(
            "--model",
            help="Override OLLAMA_MODEL for this run (e.g. qwen2.5, llama3.1).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Show what would be tagged without calling Ollama or writing rows.",
        )

    def handle(self, *args, **opts):
        qs = Card.objects.filter(is_active=True)

        if opts["set_code"]:
            qs = qs.filter(prints__cardset__code__iexact=opts["set_code"]).distinct()

        if opts["vocab_only"]:
            qs = qs.filter(conflux_tags__vocabulary_version__lt=VOCABULARY_VERSION)
        elif not opts["retag"]:
            qs = qs.filter(conflux_tags__isnull=True)

        qs = qs.order_by("name")
        if opts["limit"]:
            qs = qs[: opts["limit"]]

        cards = list(qs)
        total = len(cards)

        if total == 0:
            self.stdout.write(self.style.NOTICE("No cards match — nothing to do."))
            return

        self.stdout.write(self.style.NOTICE(
            f"Tagging {total} card(s) with model={opts['model'] or 'default'} "
            f"concurrency={opts['concurrency']} vocab=v{VOCABULARY_VERSION}"
        ))

        if opts["dry_run"]:
            for c in cards[:10]:
                self.stdout.write(f"  would tag: {c.name}")
            if total > 10:
                self.stdout.write(f"  ... and {total - 10} more")
            return

        success = 0
        errors  = 0

        def _progress(i, n, card, result):
            mark = self.style.ERROR("X") if result["error"] else self.style.SUCCESS("OK")
            tags = result["function_tags"] + result["theme_tags"]
            label = ", ".join(tags) if tags else "(no tags)"
            self.stdout.write(f"  [{i}/{n}] {mark} {card.name}: {label}")

        for card, result in tag_cards_concurrent(
            cards,
            concurrency = opts["concurrency"],
            model       = opts["model"],
            on_progress = _progress,
        ):
            if result["error"]:
                errors += 1
                self.stderr.write(self.style.ERROR(f"  {card.name}: {result['error']}"))
                # Persist the error too so re-runs can target failed rows.
                CardTag.objects.update_or_create(
                    card=card,
                    defaults={
                        "function_tags":      [],
                        "theme_tags":         [],
                        "reasoning":          "",
                        "model_name":         result["model_name"],
                        "vocabulary_version": result["vocabulary_version"],
                        "error":              result["error"][:1000],
                    },
                )
                continue

            with transaction.atomic():
                CardTag.objects.update_or_create(
                    card=card,
                    defaults={
                        "function_tags":      result["function_tags"],
                        "theme_tags":         result["theme_tags"],
                        "reasoning":          result["reasoning"],
                        "model_name":         result["model_name"],
                        "vocabulary_version": result["vocabulary_version"],
                        "error":              "",
                    },
                )
            success += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. {success} tagged, {errors} error(s)."
        ))
