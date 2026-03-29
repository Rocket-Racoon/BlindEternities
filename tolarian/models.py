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
        ).select_related("card__prints"):
            print = entry.card.primary_print
            if print and print.price_usd:
                total += float(print.price_usd) * entry.quantity
        return round(total, 2)

    @property
    def mana_curve(self):
        """
        Retorna un dict {cmc: cantidad} para las cartas del maindeck.
        Solo cartas que no son tierras.
        """
        curve = {}
        for entry in self.main_cards.select_related("card"):
            card = entry.card
            if "Land" in card.type_line:
                continue
            cmc = int(card.cmc or 0)
            cmc = min(cmc, 7)  # Agrupar 7+ juntos
            curve[cmc] = curve.get(cmc, 0) + entry.quantity
        return dict(sorted(curve.items()))

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
                fields=["deck", "card", "zone"],
                name="unique_deck_card_zone",
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