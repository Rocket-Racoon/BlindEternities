from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse

from core.models import BaseModel
from core.constants import CardCondition, CardFinish
from multiverse.models import CardPrint


class ListingType(models.TextChoices):
    SELL       = "sell",       "For sale"
    BUY_WANTED = "buy_wanted", "Wanted to buy"


class ListingVisibility(models.TextChoices):
    PUBLIC  = "public",  "Public"
    FRIENDS = "friends", "Friends only"


class ListingStatus(models.TextChoices):
    OPEN      = "open",      "Open"
    CLOSED    = "closed",    "Closed"
    COMPLETED = "completed", "Completed"


class TransactionKind(models.TextChoices):
    TRADE = "trade", "Trade"
    SALE  = "sale",  "Sale"


class TransactionStatus(models.TextChoices):
    PROPOSED         = "proposed",         "Proposed"
    COUNTER_PROPOSED = "counter_proposed", "Counter-proposed"
    ACCEPTED         = "accepted",         "Accepted"
    REJECTED         = "rejected",         "Rejected"
    CANCELLED        = "cancelled",        "Cancelled"
    COMPLETED        = "completed",        "Completed"


class TransactionSide(models.TextChoices):
    FROM_A = "from_a", "From initiator"
    FROM_B = "from_b", "From recipient"


class PriceSource(models.TextChoices):
    SCRYFALL   = "scryfall",   "Scryfall"
    TCGPLAYER  = "tcgplayer",  "TCGPlayer"
    CARDMARKET = "cardmarket", "Cardmarket"
    USER       = "user",       "User-set"


class Listing(BaseModel):
    """
    A public or friends-only offer to sell cards, or a wanted-to-buy post.
    """
    owner        = models.ForeignKey(User, on_delete=models.CASCADE, related_name="listings")
    listing_type = models.CharField(max_length=15, choices=ListingType.choices, default=ListingType.SELL)
    card_print   = models.ForeignKey(CardPrint, on_delete=models.PROTECT, related_name="listings")
    condition    = models.CharField(max_length=5, choices=CardCondition.choices, default=CardCondition.NEAR_MINT)
    finish       = models.CharField(max_length=15, choices=CardFinish.choices, default=CardFinish.NONFOIL)
    language     = models.CharField(max_length=10, default="en")
    quantity     = models.PositiveSmallIntegerField(default=1)
    asking_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes        = models.TextField(blank=True)
    visibility   = models.CharField(max_length=10, choices=ListingVisibility.choices, default=ListingVisibility.PUBLIC)
    status       = models.CharField(max_length=15, choices=ListingStatus.choices, default=ListingStatus.OPEN)

    class Meta:
        ordering            = ["-created_at"]
        verbose_name        = "listing"
        verbose_name_plural = "listings"
        indexes = [
            models.Index(fields=["status", "listing_type"]),
            models.Index(fields=["visibility", "status"]),
        ]

    def __str__(self):
        return f"{self.get_listing_type_display()} — {self.card_print} x{self.quantity}"

    def get_absolute_url(self):
        return reverse("omenpath:listing-detail", kwargs={"pk": self.pk})


class Transaction(BaseModel):
    """
    A two-party exchange: trade (items both sides) or sale (items + price).
    Completion is mutual — both parties must confirm before inventory moves.
    """
    kind           = models.CharField(max_length=10, choices=TransactionKind.choices)
    party_a        = models.ForeignKey(User, on_delete=models.PROTECT, related_name="transactions_initiated")
    party_b        = models.ForeignKey(User, on_delete=models.PROTECT, related_name="transactions_received")
    listing        = models.ForeignKey(Listing, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")
    price_agreed   = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status         = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.PROPOSED)
    confirmed_by_a = models.BooleanField(default=False)
    confirmed_by_b = models.BooleanField(default=False)
    completed_at   = models.DateTimeField(null=True, blank=True)
    note           = models.TextField(blank=True)

    class Meta:
        ordering            = ["-created_at"]
        verbose_name        = "transaction"
        verbose_name_plural = "transactions"
        indexes = [
            models.Index(fields=["status", "kind"]),
            models.Index(fields=["party_a", "status"]),
            models.Index(fields=["party_b", "status"]),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.party_a.username} ↔ {self.party_b.username} ({self.status})"

    def get_absolute_url(self):
        return reverse("omenpath:transaction-detail", kwargs={"pk": self.pk})

    def items_from_a(self):
        return self.items.filter(side=TransactionSide.FROM_A)

    def items_from_b(self):
        return self.items.filter(side=TransactionSide.FROM_B)

    @staticmethod
    def _sum_line_values(items):
        total = Decimal("0")
        has_any = False
        for item in items:
            if item.unit_value is None:
                continue
            has_any = True
            total += item.unit_value * item.quantity
        return total if has_any else None

    def total_from_a(self):
        return self._sum_line_values(self.items_from_a())

    def total_from_b(self):
        return self._sum_line_values(self.items_from_b())

    def value_difference(self):
        a, b = self.total_from_a(), self.total_from_b()
        if a is None or b is None:
            return None
        return a - b

    def other_party(self, user):
        return self.party_b if user == self.party_a else self.party_a

    def is_party(self, user):
        return user == self.party_a or user == self.party_b

    def confirmation_for(self, user):
        if user == self.party_a:
            return self.confirmed_by_a
        if user == self.party_b:
            return self.confirmed_by_b
        return False


class TransactionItem(BaseModel):
    """
    One line-item of cards on one side of a Transaction.
    """
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="items")
    side        = models.CharField(max_length=10, choices=TransactionSide.choices)
    card_print  = models.ForeignKey(CardPrint, on_delete=models.PROTECT, related_name="transaction_items")
    condition   = models.CharField(max_length=5, choices=CardCondition.choices, default=CardCondition.NEAR_MINT)
    finish      = models.CharField(max_length=15, choices=CardFinish.choices, default=CardFinish.NONFOIL)
    language    = models.CharField(max_length=10, default="en")
    quantity    = models.PositiveSmallIntegerField(default=1)
    unit_value  = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Snapshot of market value at proposal time (USD).",
    )

    class Meta:
        ordering            = ["side", "card_print__card__name"]
        verbose_name        = "transaction item"
        verbose_name_plural = "transaction items"

    def __str__(self):
        return f"{self.quantity}x {self.card_print} ({self.side})"

    @property
    def line_value(self):
        if self.unit_value is None:
            return None
        return self.unit_value * self.quantity


class PriceQuote(BaseModel):
    """
    Cached price fetched from an external source for a specific print+finish.
    Refresh via `sync_market_prices` management command.
    """
    card_print = models.ForeignKey(CardPrint, on_delete=models.CASCADE, related_name="price_quotes")
    source     = models.CharField(max_length=15, choices=PriceSource.choices)
    finish     = models.CharField(max_length=15, choices=CardFinish.choices, default=CardFinish.NONFOIL)
    currency   = models.CharField(max_length=5, default="USD")
    price      = models.DecimalField(max_digits=10, decimal_places=2)
    fetched_at = models.DateTimeField(auto_now=True)
    raw        = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering            = ["-fetched_at"]
        verbose_name        = "price quote"
        verbose_name_plural = "price quotes"
        constraints = [
            models.UniqueConstraint(
                fields=["card_print", "source", "finish", "currency"],
                name="unique_price_quote",
            )
        ]
        indexes = [
            models.Index(fields=["card_print", "source", "finish"]),
        ]

    def __str__(self):
        return f"{self.card_print} [{self.source}/{self.finish}] {self.price} {self.currency}"
