# tolarian/models.py
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import BaseModel
from multiverse.models import Card, CardPrint
from core.constants import CardCondition, CardFinish, MagicFormat


class CollectionType(models.TextChoices):
    BINDER    = "binder",    "Binder"
    WISHLIST  = "wishlist",  "Wishlist"
    TRADELIST = "tradelist", "Trade List"
    LOANLIST  = "loanlist",  "Loan List"


class DeckZone(models.TextChoices):
    MAIN        = "main",       "Maindeck"
    SIDEBOARD   = "sideboard",  "Sideboard"
    COMMANDER   = "commander",  "Commander"
    COMPANION   = "companion",  "Companion"
    MAYBEBOARD  = "maybeboard", "Maybeboard"
    RESERVE     = "reserve",    "Reserve"
    EXTRAS      = "extras",     "Tokens & More"


class Collection(BaseModel):
    """
    Binder, Wishlist, Trade List o Loan List de un usuario.
    Un usuario puede tener múltiples colecciones de cada tipo.
    """
    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name="collections")
    name         = models.CharField(max_length=100)
    description  = models.TextField(blank=True)
    collection_type = models.CharField(
        max_length=20,
        choices=CollectionType.choices,
        default=CollectionType.BINDER,
    )
    is_public    = models.BooleanField(default=False)
    cover_card   = models.ForeignKey(
        CardPrint,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )

    class Meta:
        ordering            = ["collection_type", "name"]
        verbose_name        = "collection"
        verbose_name_plural = "collections"

    def __str__(self):
        return f"{self.user.username} — {self.name}"

    def get_absolute_url(self):
        return reverse("tolarian:collection-detail", kwargs={"pk": self.pk})

    @property
    def card_count(self):
        return self.items.aggregate(
            total=models.Sum("quantity")
        )["total"] or 0

    @property
    def total_value(self):
        """Suma del precio USD de todos los prints en la colección."""
        total = 0
        for item in self.items.select_related("print"):
            price = item.print.price_usd if item.print else None
            if price:
                total += float(price) * item.quantity
        return round(total, 2)


class CollectionItem(BaseModel):
    """
    Una entrada en una colección — carta específica con condición, finish y cantidad.
    """
    collection   = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name="items")
    card         = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="collection_items")
    print        = models.ForeignKey(
        CardPrint,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="collection_items",
    )
    quantity     = models.PositiveSmallIntegerField(default=1)
    condition    = models.CharField(
        max_length=5,
        choices=CardCondition.choices,
        default=CardCondition.NEAR_MINT,
    )
    finish       = models.CharField(
        max_length=15,
        choices=CardFinish.choices,
        default=CardFinish.NONFOIL,
    )
    language     = models.CharField(max_length=10, default="en")
    purchase_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        verbose_name="Precio de compra (USD)",
    )
    loan_to_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="loaned_items",
        verbose_name="Prestado a (usuario)",
    )
    loan_to_name = models.CharField(
        max_length=100, blank=True,
        verbose_name="Prestado a (nombre)",
    )
    acquired_from = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="cards_given",
        verbose_name="Adquirida de (usuario)",
    )
    acquired_via = models.ForeignKey(
        "omenpath.Transaction",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="acquired_items",
    )
    notes        = models.TextField(blank=True)

    class Meta:
        ordering            = ["card__name"]
        verbose_name        = "collection item"
        verbose_name_plural = "collection items"
        constraints = [
            models.UniqueConstraint(
                fields=["collection", "card", "print", "condition", "finish", "language"],
                name="unique_collection_item",
            )
        ]

    def __str__(self):
        return f"{self.quantity}x {self.card.name} [{self.condition}]"

    @property
    def unit_price(self):
        """USD price per copy, picking the right variant based on finish."""
        if not self.print:
            return None
        if self.finish == CardFinish.FOIL:
            raw = self.print.price_usd_foil or self.print.price_usd
        elif self.finish == CardFinish.ETCHED:
            raw = self.print.price_usd_etched or self.print.price_usd_foil or self.print.price_usd
        else:
            raw = self.print.price_usd
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def line_value(self):
        """unit_price * quantity, or None if unknown."""
        up = self.unit_price
        return up * self.quantity if up is not None else None


class Deck(BaseModel):
    """
    Deck de Magic de un usuario.
    """
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name="decks")
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    format      = models.CharField(
        max_length=20,
        choices=MagicFormat.choices,
        default=MagicFormat.COMMANDER,
    )
    is_public   = models.BooleanField(default=False)
    cover_card  = models.ForeignKey(
        CardPrint,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )
    # Sharing
    share_token = models.CharField(
        max_length=32, unique=True, null=True, blank=True, db_index=True,
    )
    # Metadata de builds
    featured    = models.BooleanField(default=False)
    notes       = models.TextField(blank=True)

    class Meta:
        ordering            = ["-created_at"]
        verbose_name        = "deck"
        verbose_name_plural = "decks"

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    def get_absolute_url(self):
        return reverse("tolarian:deck-detail", kwargs={"pk": self.pk})

    @property
    def main_cards(self):
        return self.cards.filter(zone=DeckZone.MAIN)

    @property
    def sideboard_cards(self):
        return self.cards.filter(zone=DeckZone.SIDEBOARD)

    @property
    def commander_cards(self):
        return self.cards.filter(zone=DeckZone.COMMANDER)

    @property
    def companion_cards(self):
        return self.cards.filter(zone=DeckZone.COMPANION)

    @property
    def maybeboard_cards(self):
        return self.cards.filter(zone=DeckZone.MAYBEBOARD)

    @property
    def reserve_cards(self):
        return self.cards.filter(zone=DeckZone.RESERVE)
    
    @property
    def extras_cards(self):
        return self.cards.filter(zone=DeckZone.EXTRAS)

    @property
    def main_count(self):
        return self.main_cards.aggregate(
            total=models.Sum("quantity")
        )["total"] or 0

    @property
    def sideboard_count(self):
        return self.sideboard_cards.aggregate(
            total=models.Sum("quantity")
        )["total"] or 0

    @property
    def total_value(self):
        """Valor total del deck en USD."""
        total = 0
        for entry in self.cards.exclude(
            zone__in=[DeckZone.MAYBEBOARD, DeckZone.RESERVE, DeckZone.EXTRAS]
        ).select_related("card", "print"):
            card_print = entry.print or entry.card.primary_print
            if card_print and card_print.price_usd:
                total += float(card_print.price_usd) * entry.quantity
        return round(total, 2)

    @property
    def mana_curve(self):
        """
        Retorna un dict {cmc: cantidad} para maindeck + commander.
        Lands are excluded — they don't have a mana value.
        Each CMC shown individually (no 7+ grouping).
        """
        curve = {}
        for entry in self.cards.filter(
            zone__in=[DeckZone.MAIN, DeckZone.COMMANDER, DeckZone.COMPANION]
        ).select_related("card"):
            card = entry.card
            if "land" in card.type_line.lower():
                continue
            cmc = int(card.cmc or 0)
            curve[cmc] = curve.get(cmc, 0) + entry.quantity
        return dict(sorted(curve.items()))

    def create_snapshot(self):
        """Build a JSON snapshot dict of the current deck state."""
        cards_data = []
        for entry in self.cards.select_related("card").prefetch_related("categories"):
            cards_data.append({
                "card_id": str(entry.card_id),
                "card_name": entry.card.name,
                "print_id": str(entry.print_id) if entry.print_id else None,
                "zone": entry.zone,
                "quantity": entry.quantity,
                "is_game_changer": entry.is_game_changer,
                "categories": [c.name for c in entry.categories.all()],
            })
        categories_data = [
            {"name": c.name, "position": c.position}
            for c in self.deck_categories.all()
        ]
        return {
            "cards": cards_data,
            "categories": categories_data,
            "total_cards": sum(c["quantity"] for c in cards_data),
            "format": self.format,
        }

    def restore_from_snapshot(self, snapshot):
        """Overwrite current deck cards and categories from a snapshot dict."""
        self.cards.all().delete()
        self.deck_categories.all().delete()

        # Recreate categories
        cat_map = {}
        for cat_data in snapshot.get("categories", []):
            cat = DeckCategory.objects.create(
                deck=self, name=cat_data["name"], position=cat_data["position"]
            )
            cat_map[cat_data["name"]] = cat

        # Recreate cards
        for card_data in snapshot.get("cards", []):
            try:
                card = Card.objects.get(pk=card_data["card_id"])
            except Card.DoesNotExist:
                continue
            print_obj = None
            if card_data.get("print_id"):
                print_obj = CardPrint.objects.filter(pk=card_data["print_id"]).first()

            entry = DeckCard.objects.create(
                deck=self,
                card=card,
                print=print_obj,
                zone=card_data["zone"],
                quantity=card_data["quantity"],
                is_game_changer=card_data.get("is_game_changer", False),
            )
            for cat_name in card_data.get("categories", []):
                if cat_name in cat_map:
                    entry.categories.add(cat_map[cat_name])

    def validate_format(self):
        """
        Valida que todas las cartas del deck sean legales en el formato.
        Retorna lista de cartas ilegales.
        """
        illegal = []
        format_key = self.format

        for entry in self.cards.exclude(
            zone__in=[DeckZone.MAYBEBOARD, DeckZone.RESERVE, DeckZone.EXTRAS]
        ).select_related("card__legality"):
            try:
                legality = entry.card.legality
                status = legality.get_status(format_key)
                if status not in ("legal", "restricted"):
                    illegal.append({
                        "card":   entry.card,
                        "status": status,
                        "zone":   entry.zone,
                    })
            except Exception:
                pass

        return illegal


class DeckCategory(BaseModel):
    """
    Custom user-defined category within a deck (e.g. Draw, Ramp, Removal).
    Archidekt-style organisation layer on top of zones.
    """
    deck     = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name="deck_categories")
    name     = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering            = ["position", "name"]
        verbose_name        = "deck category"
        verbose_name_plural = "deck categories"
        constraints = [
            models.UniqueConstraint(
                fields=["deck", "name"],
                name="unique_deck_category_name",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.deck.name})"

    # Default categories created for every new deck
    DEFAULT_CATEGORIES = [
        "Commander", "Draw", "Ramp", "Removal", "Board Wipe", "Tutor",
        "Finisher", "Protection", "Recursion", "Utility",
    ]

    @classmethod
    def ensure_defaults(cls, deck):
        """Create the default set of categories if the deck has none yet."""
        if deck.deck_categories.exists():
            return
        objs = [
            cls(deck=deck, name=name, position=i)
            for i, name in enumerate(cls.DEFAULT_CATEGORIES)
        ]
        cls.objects.bulk_create(objs, ignore_conflicts=True)


class DeckCard(BaseModel):
    """
    Entrada de una carta en un deck con zona y cantidad.
    Rastrea si la copia física está en la colección del usuario.
    """
    deck     = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name="cards")
    card     = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="deck_entries")
    print    = models.ForeignKey(
        CardPrint,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="deck_entries",
    )
    zone     = models.CharField(
        max_length=15,
        choices=DeckZone.choices,
        default=DeckZone.MAIN,
    )
    quantity = models.PositiveSmallIntegerField(default=1)

    # Custom category assignment (Archidekt-style) — a card can belong to multiple categories
    categories = models.ManyToManyField(
        DeckCategory,
        blank=True,
        related_name="cards",
    )

    # Game Changer — highlight key cards in the deck
    is_game_changer = models.BooleanField(default=False)

    # ¿Tengo la copia física en mi colección?
    owned    = models.BooleanField(default=False)

    # Notas por carta en el deck (estrategia, sinergias, etc.)
    notes    = models.TextField(blank=True)

    class Meta:
        ordering            = ["zone", "card__name"]
        verbose_name        = "deck card"
        verbose_name_plural = "deck cards"
        constraints = [
            models.UniqueConstraint(
                fields=["deck", "card", "zone", "print"],
                name="unique_deck_card_zone_print",
            )
        ]

    def __str__(self):
        return f"{self.quantity}x {self.card.name} ({self.get_zone_display()})"

    def is_in_other_decks(self):
        """
        Retorna lista de otros decks del mismo usuario que tienen esta carta.
        """
        return (
            DeckCard.objects
            .filter(
                card=self.card,
                deck__user=self.deck.user,
                deck__is_active=True,
            )
            .exclude(deck=self.deck)
            .select_related("deck")
        )


class DeckVersion(BaseModel):
    """Point-in-time snapshot of a deck's state."""
    deck    = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    label   = models.CharField(max_length=100, blank=True)
    notes   = models.TextField(blank=True)
    snapshot = models.JSONField()

    class Meta:
        ordering            = ["-version"]
        verbose_name        = "deck version"
        verbose_name_plural = "deck versions"
        constraints = [
            models.UniqueConstraint(
                fields=["deck", "version"],
                name="unique_deck_version_number",
            )
        ]

    def __str__(self):
        label = f" — {self.label}" if self.label else ""
        return f"v{self.version}{label} ({self.deck.name})"