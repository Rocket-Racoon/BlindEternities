# multiverse/models.py
from django.db import models
from core.models import BaseModel, CreatureType
from core.constants import *

class CardSet(BaseModel):
    # Identifiers
    scryfall_id     = models.UUIDField(unique=True, null=True, blank=True, db_index=True)
    code            = models.CharField(max_length=10, unique=True, db_index=True)
    mtgo_code       = models.CharField(max_length=10, blank=True)
    arena_code      = models.CharField(max_length=10, blank=True)
    tcgplayer_id    = models.IntegerField(null=True, blank=True)
    cardmarket_id   = models.IntegerField(null=True, blank=True)

    # Info
    name            = models.CharField(max_length=200)
    set_type        = models.CharField(max_length=50, choices=CardSetType.choices, blank=True)
    released_at     = models.DateField(null=True, blank=True)
    block_code      = models.CharField(max_length=10, blank=True)
    block           = models.CharField(max_length=100, blank=True)
    parent_set_code = models.CharField(max_length=10, blank=True)

    # Conteos
    card_count      = models.IntegerField(default=0)
    printed_size    = models.IntegerField(null=True, blank=True)

    # Flags
    digital         = models.BooleanField(default=False)
    foil_only       = models.BooleanField(default=False)
    nonfoil_only    = models.BooleanField(default=False)

    # URIs
    icon_svg_uri    = models.URLField(blank=True)
    search_uri      = models.URLField(blank=True)
    scryfall_uri    = models.URLField(blank=True)

    # Custom Data
    is_standard_legal = models.BooleanField(default=False)
    
    class Meta:
        ordering        = ["-released_at"]
        verbose_name    = "set"
        verbose_name_plural = "sets"

    def __str__(self):
        return f"{self.name} ({self.code.upper()})"


class Card(BaseModel):
    # Core identifiers
    oracle_id       = models.UUIDField(unique=True, db_index=True)
    name            = models.CharField(max_length=250, db_index=True)
    lang            = models.CharField(max_length=10, default="en")

    # Layout
    layout          = models.CharField(max_length=50, choices=CardLayout.choices, blank=True)

    # Gameplay — oracle
    type_line       = models.CharField(max_length=250, blank=True)
    oracle_text     = models.TextField(blank=True)
    mana_cost       = models.CharField(max_length=100, blank=True)
    cmc             = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    colors          = models.JSONField(default=list)
    color_identity  = models.JSONField(default=list)
    color_indicator = models.JSONField(default=list)

    # Stats
    power           = models.CharField(max_length=10, blank=True)
    toughness       = models.CharField(max_length=10, blank=True)
    loyalty         = models.CharField(max_length=10, blank=True)
    defense         = models.CharField(max_length=10, blank=True)  # Battle cards
    hand_modifier   = models.CharField(max_length=10, blank=True)  # Vanguard
    life_modifier   = models.CharField(max_length=10, blank=True)  # Vanguard

    # Keywords & extras
    keywords        = models.JSONField(default=list)
    produced_mana   = models.JSONField(default=list)
    all_parts       = models.JSONField(default=list)  # RelatedCard objects

    # Flags de gameplay
    reserved        = models.BooleanField(default=False)
    foil            = models.BooleanField(default=False)
    nonfoil         = models.BooleanField(default=False)
    oversized       = models.BooleanField(default=False)
    edhrec_rank     = models.IntegerField(null=True, blank=True)
    penny_rank      = models.IntegerField(null=True, blank=True)
    can_be_commander = models.BooleanField(default=False)
    has_deck_limit  = models.BooleanField(default=False)
    max_deck_copies = models.IntegerField(null=True, blank=True)
    banned_as_companion = models.BooleanField(default=False)

    # URIs
    scryfall_uri    = models.URLField(blank=True)
    rulings_uri     = models.URLField(blank=True)
    prints_search_uri = models.URLField(blank=True)
    
    # Identifiers externos
    multiverse_ids  = models.JSONField(default=list)
    mtgo_id         = models.IntegerField(null=True, blank=True)
    mtgo_foil_id    = models.IntegerField(null=True, blank=True)
    arena_id        = models.IntegerField(null=True, blank=True)
    tcgplayer_id    = models.IntegerField(null=True, blank=True)
    cardmarket_id   = models.IntegerField(null=True, blank=True)
    
    # Subtipos de criatura — relación dinámica
    creature_types = models.ManyToManyField(
        CreatureType,
        blank=True,
        related_name="cards",
    )

    class Meta:
        ordering        = ["name"]
        verbose_name    = "card"
        verbose_name_plural = "cards"

    def __str__(self):
        return self.name

    @property
    def is_multiface(self):
        return self.faces.exists()

    @property
    def primary_print(self):
        return self.prints.select_related("cardset").order_by("-cardset__released_at").first()


class CardFace(BaseModel):
    card            = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="faces")
    face_index      = models.PositiveSmallIntegerField(default=0)  # 0 = frontal, 1 = trasera

    # Oracle
    name            = models.CharField(max_length=250)
    printed_name    = models.CharField(max_length=250, blank=True)
    type_line       = models.CharField(max_length=250, blank=True)
    printed_type_line = models.CharField(max_length=250, blank=True)
    oracle_text     = models.TextField(blank=True)
    printed_text    = models.TextField(blank=True)
    mana_cost       = models.CharField(max_length=100, blank=True)
    cmc             = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    colors          = models.JSONField(default=list)
    color_indicator = models.JSONField(default=list)

    # Stats
    power           = models.CharField(max_length=10, blank=True)
    toughness       = models.CharField(max_length=10, blank=True)
    loyalty         = models.CharField(max_length=10, blank=True)
    defense         = models.CharField(max_length=10, blank=True)

    # Print info por cara
    artist          = models.CharField(max_length=200, blank=True)
    artist_id       = models.UUIDField(null=True, blank=True)
    illustration_id = models.UUIDField(null=True, blank=True)
    image_uris      = models.JSONField(default=dict)
    flavor_text     = models.TextField(blank=True)
    flavor_name     = models.CharField(max_length=250, blank=True)
    watermark       = models.CharField(max_length=50, blank=True)

    # Layout propio de la cara (reversible_card)
    layout          = models.CharField(max_length=50, blank=True)
    oracle_id       = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering        = ["card", "face_index"]
        verbose_name    = "card face"
        verbose_name_plural = "card faces"

    def __str__(self):
        return f"{self.card.name} — face {self.face_index} ({self.name})"

class CardPrint(BaseModel):
    scryfall_id         = models.UUIDField(unique=True, db_index=True)
    card                = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="prints")
    cardset             = models.ForeignKey(CardSet, on_delete=models.CASCADE, related_name="prints")

    # Identifiers
    collector_number    = models.CharField(max_length=20, blank=True)
    lang                = models.CharField(max_length=10, default="en")
    mtgo_id             = models.IntegerField(null=True, blank=True)
    mtgo_foil_id        = models.IntegerField(null=True, blank=True)
    arena_id            = models.IntegerField(null=True, blank=True)
    tcgplayer_id        = models.IntegerField(null=True, blank=True)
    tcgplayer_etched_id = models.IntegerField(null=True, blank=True)
    cardmarket_id       = models.IntegerField(null=True, blank=True)
    multiverse_ids      = models.JSONField(default=list)
    illustration_id     = models.UUIDField(null=True, blank=True)

    # Imágenes
    image_uris          = models.JSONField(default=dict)
    image_status        = models.CharField(max_length=20, blank=True)

    # Print info
    rarity              = models.CharField(max_length=20, choices=CardRarity.choices, blank=True)
    flavor_text         = models.TextField(blank=True)
    flavor_name         = models.CharField(max_length=250, blank=True)
    printed_name        = models.CharField(max_length=250, blank=True)
    printed_type_line   = models.CharField(max_length=250, blank=True)
    printed_text        = models.TextField(blank=True)
    artist              = models.CharField(max_length=200, blank=True)
    artist_id           = models.UUIDField(null=True, blank=True)
    border_color        = models.CharField(max_length=20, choices=BorderColor.choices, blank=True)
    frame               = models.CharField(max_length=20, blank=True)
    frame_effects       = models.JSONField(default=list)
    security_stamp      = models.CharField(max_length=20, blank=True)
    watermark           = models.CharField(max_length=50, blank=True)
    set_type            = models.CharField(max_length=50, choices=CardSetType.choices, blank=True)

    # Finishes (reemplaza foil/nonfoil en API moderna)
    finishes            = models.JSONField(default=list)  # ["foil", "nonfoil", "etched"]
    foil                = models.BooleanField(default=False)     # deprecated, mantener compatibilidad
    nonfoil             = models.BooleanField(default=False)     # deprecated

    # Flags
    full_art            = models.BooleanField(default=False)
    textless            = models.BooleanField(default=False)
    booster             = models.BooleanField(default=False)
    digital             = models.BooleanField(default=False)
    promo               = models.BooleanField(default=False)
    reprint             = models.BooleanField(default=False)
    variation           = models.BooleanField(default=False)
    oversized           = models.BooleanField(default=False)
    story_spotlight     = models.BooleanField(default=False)
    content_warning     = models.BooleanField(default=False)
    reserved            = models.BooleanField(default=False)
    promo_types         = models.JSONField(default=list)
    games               = models.JSONField(default=list)  # ["paper", "mtgo", "arena"]
    variation_of        = models.UUIDField(null=True, blank=True)

    # Precios
    prices              = models.JSONField(default=dict)
    purchase_uris       = models.JSONField(default=dict)
    related_uris        = models.JSONField(default=dict)

    # Fechas
    released_at         = models.DateField(null=True, blank=True)
    preview             = models.JSONField(default=dict)

    class Meta:
        ordering        = ["-cardset__released_at", "collector_number"]
        verbose_name    = "card print"
        verbose_name_plural = "card prints"

    def __str__(self):
        return f"{self.card.name} [{self.cardset.code.upper()}] #{self.collector_number}"

    @property
    def image_normal(self):
        return self.image_uris.get("normal", "")

    @property
    def image_large(self):
        return self.image_uris.get("large", "")

    @property
    def image_art_crop(self):
        return self.image_uris.get("art_crop", "")

    @property
    def image_png(self):
        return self.image_uris.get("png", "")

    @property
    def price_usd(self):
        return self.prices.get("usd")

    @property
    def price_usd_foil(self):
        return self.prices.get("usd_foil")

    @property
    def price_usd_etched(self):
        return self.prices.get("usd_etched")

    @property
    def price_eur(self):
        return self.prices.get("eur")

    @property
    def price_eur_foil(self):
        return self.prices.get("eur_foil")

    @property
    def price_tix(self):
        return self.prices.get("tix")


class CardLegality(BaseModel):
    card    = models.OneToOneField(Card, on_delete=models.CASCADE, related_name="legality")
    data    = models.JSONField(default=dict)
    # data = {"standard": "legal", "modern": "legal", "legacy": "banned", ...}

    class Meta:
        verbose_name     = "card legality"
        verbose_name_plural = "card legalities"

    def __str__(self):
        return f"{self.card.name} — legality"

    def is_legal(self, format_key):
        return self.data.get(format_key) == "legal"

    def get_status(self, format_key):
        return self.data.get(format_key, "not_legal")


class Ruling(BaseModel):
    card       = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="rulings")
    source     = models.CharField(max_length=20, blank=True)  # "wotc" o "scryfall"
    published_at = models.DateField()
    comment    = models.TextField()

    class Meta:
        ordering = ["published_at"]
        verbose_name     = "ruling"
        verbose_name_plural = "rulings"

    def __str__(self):
        return f"{self.card.name} — {self.published_at}"