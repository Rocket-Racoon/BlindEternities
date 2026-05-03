from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse

from core.models import BaseModel
from multiverse.models import Card
from tolarian.models import Deck


class BracketTier(models.TextChoices):
    """WotC Commander Bracket System (1–5)."""
    EXHIBITION = "1", "1 — Exhibition"
    CORE       = "2", "2 — Core"
    UPGRADED   = "3", "3 — Upgraded"
    OPTIMIZED  = "4", "4 — Optimized"
    CEDH       = "5", "5 — cEDH"


class HonestTier(models.TextChoices):
    """Buckets derived from the Honest Scale final score."""
    JANK   = "jank",   "Jank"
    CASUAL = "casual", "Casual"
    MID    = "mid",    "Mid Power"
    HIGH   = "high",   "High Power"
    CEDH   = "cedh",   "cEDH"


class IntentLabel(models.TextChoices):
    COMPETITIVE = "competitive", "Competitive"
    OPTIMIZED   = "optimized",   "Optimized"
    CASUAL      = "casual",      "Casual"
    JANK        = "jank",        "Jank / Meme"


class EvaluationStatus(models.TextChoices):
    PENDING   = "pending",   "Pending"
    RUNNING   = "running",   "Running"
    COMPLETED = "completed", "Completed"
    FAILED    = "failed",    "Failed"


class DeckEvaluation(BaseModel):
    """
    One AI-generated evaluation of an EDH deck against the Honest Scale rubric
    and the WotC Commander Bracket System. Either references a saved Deck or
    captures a pasted decklist snapshot.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="deck_evaluations")
    deck = models.ForeignKey(
        Deck, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="evaluations",
    )
    commander      = models.CharField(max_length=200, blank=True)
    decklist_text  = models.TextField(blank=True, help_text="Snapshot of the decklist evaluated.")

    # WotC bracket (Python-derived from final_score; may also be model-suggested as fallback).
    bracket        = models.CharField(max_length=2, choices=BracketTier.choices, blank=True)
    bracket_user   = models.CharField(
        max_length=2, choices=BracketTier.choices, blank=True,
        help_text="Owner's self-rated bracket tier.",
    )

    # Honest Scale outputs
    honest_scores  = models.JSONField(default=dict, blank=True,
                                      help_text="Per-axis scores returned by the LLM.")
    final_score    = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        help_text="Weighted final score 0.00–10.00, computed in Python from honest_scores.",
    )
    honest_tier    = models.CharField(max_length=10, choices=HonestTier.choices, blank=True)

    # Intent / qualitative
    intent_label   = models.CharField(max_length=20, choices=IntentLabel.choices, blank=True)
    intent_reason  = models.TextField(blank=True)
    narrative      = models.TextField(blank=True)

    # Algorithm-side data
    card_tags      = models.JSONField(default=list, blank=True,
                                      help_text="[{name, tags: [...]}, ...] from the preprocessing step.")
    combos         = models.JSONField(default=list, blank=True,
                                      help_text="[{pieces, type, interactable, resilient}, ...]")

    # Run metadata
    model_name     = models.CharField(max_length=100, blank=True)
    status         = models.CharField(
        max_length=15, choices=EvaluationStatus.choices,
        default=EvaluationStatus.PENDING,
    )
    error          = models.TextField(blank=True)
    prompt         = models.TextField(blank=True)
    raw_response   = models.JSONField(default=dict, blank=True)
    duration_ms    = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering            = ["-created_at"]
        verbose_name        = "deck evaluation"
        verbose_name_plural = "deck evaluations"
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["deck", "-created_at"]),
        ]

    def __str__(self):
        label = self.deck.name if self.deck_id else (self.commander or "pasted decklist")
        return f"{label} → {self.get_honest_tier_display() or self.status}"

    def get_absolute_url(self):
        return reverse("conflux:evaluation-detail", kwargs={"pk": self.pk})

    @property
    def is_terminal(self):
        return self.status in {EvaluationStatus.COMPLETED, EvaluationStatus.FAILED}


class CardTag(BaseModel):
    """
    Functional + thematic classification of a single Magic card, generated
    by the Ollama tagger (`conflux/tagger.py`). One canonical tag set per
    card; re-tagging overwrites. `vocabulary_version` lets us invalidate
    rows in bulk when the tag taxonomy itself changes.

    Used by:
      - the deck evaluator to enrich the prompt with tag-derived counts
        (ramp, tutors, removal, etc.) instead of asking the LLM to estimate
      - future deck-building suggestion features (find cards with matching
        function/theme tags for a given strategy).
    """
    card           = models.OneToOneField(
        Card, on_delete=models.CASCADE, related_name="conflux_tags",
    )
    function_tags  = models.JSONField(default=list, blank=True)
    theme_tags     = models.JSONField(default=list, blank=True)
    reasoning      = models.TextField(blank=True)
    model_name     = models.CharField(max_length=100, blank=True)
    vocabulary_version = models.PositiveSmallIntegerField(default=1)
    error          = models.TextField(blank=True)

    class Meta:
        ordering            = ["-updated_at"]
        verbose_name        = "card tag"
        verbose_name_plural = "card tags"
        indexes = [
            models.Index(fields=["model_name", "vocabulary_version"]),
        ]

    def __str__(self):
        tag_count = len(self.function_tags or []) + len(self.theme_tags or [])
        return f"{self.card.name} — {tag_count} tag(s)"

    @property
    def all_tags(self) -> list:
        return list(self.function_tags or []) + list(self.theme_tags or [])

    def has(self, tag: str) -> bool:
        return tag in (self.function_tags or []) or tag in (self.theme_tags or [])
