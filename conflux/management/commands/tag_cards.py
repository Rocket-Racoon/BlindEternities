"""
Bulk-tag MTG cards using a local Ollama model.

Processes cards in batches (default 100) the same way `import_cards` does:
inside each batch the LLM calls fan out across a thread pool, then the
whole batch's results are written under a single atomic transaction.
This means Ctrl-C between batches loses no committed progress, and DB
write locks are never held during slow LLM calls.

By default tags only cards that don't yet have a CardTag row. Use --retag
to re-tag everything (or a filtered subset). Re-tagging overwrites the
existing CardTag for that card.

Examples:
    python manage.py tag_cards
    python manage.py tag_cards --limit 100
    python manage.py tag_cards --set znr
    python manage.py tag_cards --retag --concurrency 8
    python manage.py tag_cards --batch-size 200 --concurrency 8
    python manage.py tag_cards --model qwen2.5 --vocab-only
    python manage.py tag_cards --dry-run --limit 20
"""
import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from multiverse.models import Card

from conflux.models import CardTag
from conflux.tagger import tag_cards_concurrent
from conflux.vocabulary import VOCABULARY_VERSION


DEFAULT_BATCH_SIZE = 100


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
            "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
            help=f"Cards per batch (default: {DEFAULT_BATCH_SIZE}). Each batch commits as one transaction.",
        )
        parser.add_argument(
            "--concurrency", type=int, default=5,
            help="Max concurrent Ollama requests within a batch (default: 5). Higher needs more VRAM.",
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
        start_ts   = timezone.now()
        batch_size = max(1, opts["batch_size"])

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

        batches = [cards[i : i + batch_size] for i in range(0, total, batch_size)]

        self.stdout.write(self.style.NOTICE(
            f"Tagging {total} card(s) in {len(batches)} batch(es) of {batch_size} — "
            f"model={opts['model'] or 'default'} concurrency={opts['concurrency']} "
            f"vocab=v{VOCABULARY_VERSION}"
        ))

        if opts["dry_run"]:
            for c in cards[:10]:
                self.stdout.write(f"  would tag: {c.name}")
            if total > 10:
                self.stdout.write(f"  ... and {total - 10} more")
            return

        total_ok     = 0
        total_errors = 0

        for batch_idx, batch in enumerate(batches, start=1):
            t0 = time.monotonic()
            ok, errs = self._process_batch(batch, batch_idx, len(batches), opts)
            elapsed = time.monotonic() - t0

            total_ok     += ok
            total_errors += errs
            self.stdout.write(self.style.SUCCESS(
                f"Batch {batch_idx}/{len(batches)}: {ok} ok, {errs} error(s) "
                f"in {elapsed:.1f}s — running total {total_ok}/{total} done"
            ))

        wall = (timezone.now() - start_ts).total_seconds()
        self.stdout.write(self.style.SUCCESS(
            f"\nDone in {wall:.1f}s — {total_ok} tagged, {total_errors} error(s)."
        ))

    # ──────────────────────────────────────────────
    # Per-batch: fan out LLM calls, then atomic write
    # ──────────────────────────────────────────────
    def _process_batch(self, batch, batch_idx, batch_count, opts):
        n = len(batch)
        first, last = batch[0].name, batch[-1].name
        self.stdout.write(
            f"\n  Batch {batch_idx}/{batch_count} — {n} card(s) "
            f"[{first[:32]} … {last[:32]}]"
        )

        def _progress(i, total, card, result):
            mark = self.style.ERROR("X") if result["error"] else self.style.SUCCESS("OK")
            tags = result["function_tags"] + result["theme_tags"]
            label = ", ".join(tags) if tags else "(no tags)"
            self.stdout.write(f"    [{i}/{total}] {mark} {card.name}: {label}")

        # Pass 1 — collect all results without touching the DB.
        results = list(tag_cards_concurrent(
            batch,
            concurrency = opts["concurrency"],
            model       = opts["model"],
            on_progress = _progress,
        ))

        # Pass 2 — single atomic write for the whole batch.
        ok = 0
        errs = 0
        with transaction.atomic():
            for card, result in results:
                if result["error"]:
                    errs += 1
                    self.stderr.write(self.style.ERROR(
                        f"    {card.name}: {result['error']}"
                    ))
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
                ok += 1

        return ok, errs
