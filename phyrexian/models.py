# phyrexian/models.py
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import BaseModel
from core.constants import MagicFormat


class GameResult(models.TextChoices):
    WIN  = "win",  "Win"
    LOSS = "loss", "Loss"
    DRAW = "draw", "Draw"


class EliminationCause(models.TextChoices):
    LIFE             = "life",             "Life (0 or less)"
    POISON           = "poison",           "Poison Counters"
    COMMANDER_DAMAGE = "commander_damage",  "Commander Damage"
    ALT_WINCON       = "alt_wincon",        "Alt. Win Condition"
    FORFEIT          = "forfeit",          "Forfeit"
    ALT_LOSECON      = "alt_losecon",      "Alt. Lose Condition"


class GameRecord(BaseModel):
    """
    Registro de una partida de Magic.
    Vinculada opcionalmente a un deck del usuario.
    """
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="game_records"
    )
    deck = models.ForeignKey(
        "tolarian.Deck",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="game_records",
    )
    format = models.CharField(
        max_length=20,
        choices=MagicFormat.choices,
        default=MagicFormat.COMMANDER,
    )
    result = models.CharField(
        max_length=4,
        choices=GameResult.choices,
    )
    opponent_name = models.CharField(
        max_length=100, blank=True,
        help_text="Nombre del oponente (texto libre).",
    )
    opponent_deck_name = models.CharField(
        max_length=100, blank=True,
        help_text="Nombre o arquetipo del deck oponente.",
    )
    turns = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Número de turnos de la partida.",
    )
    date_played = models.DateField(
        help_text="Fecha en que se jugó la partida.",
    )
    notes = models.TextField(blank=True)

    # Multiplayer / robust tracking
    my_commanders = models.JSONField(
        default=list, blank=True,
        help_text="Commander name(s) for user's deck.",
    )
    my_placement = models.PositiveSmallIntegerField(
        default=0,
        help_text="User's finishing position (1 = winner).",
    )
    elimination_cause = models.CharField(
        max_length=20,
        choices=EliminationCause.choices,
        blank=True,
        help_text="How the user was eliminated (if applicable).",
    )
    elimination_turn = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Turn number when the user was eliminated.",
    )
    eliminator_name = models.CharField(
        max_length=100, blank=True,
        help_text="Name of the player who eliminated the user (own name = forfeit).",
    )

    # Link to live session (if game was tracked live)
    session = models.ForeignKey(
        "GameSession",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="game_records",
    )

    class Meta:
        ordering = ["-date_played", "-created_at"]
        verbose_name = "game record"
        verbose_name_plural = "game records"

    def __str__(self):
        deck_name = self.deck.name if self.deck else "No deck"
        return f"{self.get_result_display()} — {deck_name} vs {self.opponent_name or '?'}"

    def get_absolute_url(self):
        return reverse("phyrexian:game-detail", kwargs={"pk": self.pk})


class GamePlayer(BaseModel):
    """
    An opponent (or participant) in a logged game.
    Stores per-player details for multiplayer game records.
    """
    game = models.ForeignKey(
        GameRecord, on_delete=models.CASCADE, related_name="opponents"
    )
    name = models.CharField(max_length=100)
    deck = models.ForeignKey(
        "tolarian.Deck",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
        help_text="Link to a deck on the site (optional).",
    )
    deck_name = models.CharField(
        max_length=100, blank=True,
        help_text="Deck name or archetype (free text).",
    )
    commanders = models.JSONField(
        default=list, blank=True,
        help_text="Commander name(s).",
    )
    placement = models.PositiveSmallIntegerField(
        default=0,
        help_text="Finishing position (1 = winner).",
    )
    elimination_cause = models.CharField(
        max_length=20,
        choices=EliminationCause.choices,
        blank=True,
    )
    elimination_turn = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Turn number when this opponent was eliminated.",
    )
    eliminator_name = models.CharField(
        max_length=100, blank=True,
        help_text="Name of the player who eliminated this opponent (own name = forfeit).",
    )
    is_winner = models.BooleanField(default=False)

    class Meta:
        ordering = ["placement", "created_at"]
        verbose_name = "game player"
        verbose_name_plural = "game players"

    def __str__(self):
        return f"{self.name} — #{self.placement}" if self.placement else self.name


# ---------------------------------------------------------------------------
# Live Game Session (Lifetap-style)
# ---------------------------------------------------------------------------
FORMAT_STARTING_LIFE = {
    MagicFormat.STANDARD:  20,
    MagicFormat.PIONEER:   20,
    MagicFormat.MODERN:    20,
    MagicFormat.LEGACY:    20,
    MagicFormat.VINTAGE:   20,
    MagicFormat.PAUPER:    20,
    MagicFormat.DRAFT:     20,
    MagicFormat.SEALED:    20,
    MagicFormat.COMMANDER: 40,
    MagicFormat.OATHBREAKER: 20,
    MagicFormat.BRAWL:     25,
    MagicFormat.OTHER:     20,
}


class SessionStatus(models.TextChoices):
    ACTIVE   = "active",   "Active"
    FINISHED = "finished", "Finished"


class GameSession(BaseModel):
    """
    A live game session — real-time life counter and game tracker.
    Created by the host user; supports 2-6 players.
    """
    host = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="hosted_sessions"
    )
    format = models.CharField(
        max_length=20,
        choices=MagicFormat.choices,
        default=MagicFormat.COMMANDER,
    )
    starting_life = models.PositiveSmallIntegerField(default=40)
    status = models.CharField(
        max_length=10,
        choices=SessionStatus.choices,
        default=SessionStatus.ACTIVE,
    )
    current_turn = models.PositiveSmallIntegerField(default=1)
    winner = models.ForeignKey(
        "PlayerSlot",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "game session"
        verbose_name_plural = "game sessions"

    def __str__(self):
        return f"Game #{self.pk.__str__()[:8]} — {self.get_format_display()} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("phyrexian:session-live", kwargs={"pk": self.pk})

    @property
    def player_count(self):
        return self.players.count()

    def reset_life(self):
        """Reset all players to starting life for a new game within the session."""
        self.players.update(
            life=self.starting_life, poison=0, energy=0, experience=0,
            commander_tax=0, treasure=0, rad=0, storm_count=0,
            commander_damage={}, commander_taxes={}, is_monarch=False, has_initiative=False,
            has_citys_blessing=False, speed=0, the_ring=0, is_day=True, placement=0,
            elimination_cause="", elimination_turn=None, eliminator=None,
        )
        self.current_turn = 1
        self.status = SessionStatus.ACTIVE
        self.winner = None
        self.save(update_fields=["current_turn", "status", "winner", "updated_at"])


class PlayerSlot(BaseModel):
    """
    A player seat in a game session.
    Can be linked to a registered user or just have a name (guests).
    """
    session = models.ForeignKey(
        GameSession, on_delete=models.CASCADE, related_name="players"
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="game_slots",
    )
    name = models.CharField(max_length=100)
    position = models.PositiveSmallIntegerField(default=0)

    # Life & counters
    life = models.IntegerField(default=40)
    poison = models.PositiveSmallIntegerField(default=0)
    energy = models.PositiveSmallIntegerField(default=0)
    experience = models.PositiveSmallIntegerField(default=0)
    commander_tax = models.PositiveSmallIntegerField(default=0)
    treasure = models.PositiveSmallIntegerField(default=0)
    rad = models.PositiveSmallIntegerField(default=0)
    storm_count = models.PositiveSmallIntegerField(default=0)

    # Commander damage received (JSON: {"<player_slot_pk>": amount})
    commander_damage = models.JSONField(default=dict, blank=True)

    # Per-commander tax (JSON: {"Commander Name": tax_count})
    commander_taxes = models.JSONField(default=dict, blank=True)

    # Custom commander names (used when no deck is linked). JSON list of names.
    commanders = models.JSONField(default=list, blank=True)

    # Level-based mechanics (0-4)
    speed = models.PositiveSmallIntegerField(default=0)
    the_ring = models.PositiveSmallIntegerField(default=0)

    # Status flags
    is_monarch = models.BooleanField(default=False)
    has_initiative = models.BooleanField(default=False)
    has_citys_blessing = models.BooleanField(default=False)
    is_day = models.BooleanField(default=True, help_text="Day/Night cycle: True=Day, False=Night")

    # Display
    color = models.CharField(
        max_length=7, default="#6366F1",
        help_text="Hex color for player panel.",
    )
    background_image = models.URLField(
        blank=True,
        help_text="Card art URL for player panel background.",
    )

    # Placement (1 = winner, 2 = second, etc. 0 = not yet placed)
    placement = models.PositiveSmallIntegerField(default=0)

    # Elimination tracking
    elimination_cause = models.CharField(
        max_length=20,
        choices=EliminationCause.choices,
        blank=True,
    )
    elimination_turn = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Turn number when this player was eliminated.",
    )
    eliminator = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="eliminations",
        help_text="Player slot that eliminated this one (self = forfeit).",
    )

    # Deck link (optional)
    deck = models.ForeignKey(
        "tolarian.Deck",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["position"]
        verbose_name = "player slot"
        verbose_name_plural = "player slots"
        constraints = [
            models.UniqueConstraint(
                fields=["session", "position"],
                name="unique_session_position",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.life} life)"

    @property
    def is_dead(self):
        return self.life <= 0 or self.poison >= 10 or self.max_commander_damage >= 21

    @property
    def total_commander_damage(self):
        return sum(self.commander_damage.values()) if self.commander_damage else 0

    @property
    def max_commander_damage(self):
        return max(self.commander_damage.values()) if self.commander_damage else 0


class LifeChange(BaseModel):
    """
    A single life change event — the turn-by-turn log.
    """
    session = models.ForeignKey(
        GameSession, on_delete=models.CASCADE, related_name="life_changes"
    )
    player = models.ForeignKey(
        PlayerSlot, on_delete=models.CASCADE, related_name="life_changes"
    )
    delta = models.IntegerField(help_text="Positive = gain, negative = loss.")
    life_after = models.IntegerField()
    turn = models.PositiveSmallIntegerField(default=1)
    source = models.CharField(
        max_length=50, blank=True,
        help_text="What caused the change (combat, spell, etc.).",
    )

    class Meta:
        ordering = ["created_at"]
        verbose_name = "life change"
        verbose_name_plural = "life changes"

    def __str__(self):
        sign = "+" if self.delta > 0 else ""
        return f"{self.player.name}: {sign}{self.delta} → {self.life_after} (turn {self.turn})"
