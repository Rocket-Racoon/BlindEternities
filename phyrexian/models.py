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


# ═══════════════════════════════════════════════════════════════════════════
# Tournament Bracket Tracking
# ═══════════════════════════════════════════════════════════════════════════

class BracketType(models.TextChoices):
    SINGLE_ELIM = "single_elim", "Single Elimination"
    SWISS       = "swiss",       "Swiss"


class TournamentStatus(models.TextChoices):
    SETUP    = "setup",    "Setup"
    ACTIVE   = "active",   "Active"
    FINISHED = "finished", "Finished"


class Tournament(BaseModel):
    """A tournament grouping multiple rounds of games."""
    name = models.CharField(max_length=200)
    host = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="hosted_tournaments"
    )
    format = models.CharField(
        max_length=20, choices=MagicFormat.choices, default=MagicFormat.COMMANDER,
    )
    bracket_type = models.CharField(
        max_length=20, choices=BracketType.choices, default=BracketType.SWISS,
    )
    status = models.CharField(
        max_length=10, choices=TournamentStatus.choices, default=TournamentStatus.SETUP,
    )
    pod_size = models.PositiveSmallIntegerField(
        default=4,
        help_text="Players per table (2 for 1v1, 3-4 for multiplayer).",
    )
    swiss_rounds = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Number of Swiss rounds (auto-calculated if blank).",
    )
    best_of = models.PositiveSmallIntegerField(
        default=1,
        help_text="Best-of-N games per match (1 = single game, 3 = Bo3).",
    )
    current_round = models.PositiveSmallIntegerField(default=0)
    date = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.name} — {self.get_format_display()} ({self.get_bracket_type_display()})"

    def get_absolute_url(self):
        return reverse("phyrexian:tournament-detail", kwargs={"pk": self.pk})

    @property
    def participant_count(self):
        return self.participants.filter(dropped=False).count()

    @property
    def recommended_rounds(self):
        """ceil(log2(n)) rounds for Swiss."""
        import math
        n = self.participants.count()
        return max(1, math.ceil(math.log2(n))) if n > 1 else 1

    @property
    def total_rounds(self):
        if self.bracket_type == BracketType.SWISS:
            return self.swiss_rounds or self.recommended_rounds
        # Single-elim: number of rounds based on pod_size
        import math
        n = self.participants.count()
        if n <= 1:
            return 0
        return math.ceil(math.log(n) / math.log(self.pod_size))


class TournamentParticipant(BaseModel):
    """A player registered in a tournament."""
    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tournament_entries",
    )
    name = models.CharField(max_length=100)
    deck = models.ForeignKey(
        "tolarian.Deck", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    deck_name = models.CharField(max_length=100, blank=True)
    commanders = models.JSONField(default=list, blank=True)
    seed = models.PositiveSmallIntegerField(default=0)

    # Standing tracking
    match_points = models.PositiveSmallIntegerField(default=0)
    match_wins = models.PositiveSmallIntegerField(default=0)
    match_losses = models.PositiveSmallIntegerField(default=0)
    match_draws = models.PositiveSmallIntegerField(default=0)
    game_win_pct = models.FloatField(default=0.0)
    opp_match_win_pct = models.FloatField(default=0.0)
    opp_game_win_pct = models.FloatField(default=0.0)

    dropped = models.BooleanField(default=False)
    final_standing = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-match_points", "-opp_match_win_pct", "-game_win_pct", "seed"]
        constraints = [
            models.UniqueConstraint(
                fields=["tournament", "user"],
                name="unique_tournament_user",
                condition=models.Q(user__isnull=False),
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.match_points} pts)"

    @property
    def matches_played(self):
        return self.match_wins + self.match_losses + self.match_draws

    @property
    def record_display(self):
        return f"{self.match_wins}-{self.match_losses}" + (
            f"-{self.match_draws}" if self.match_draws else ""
        )


class TournamentRound(BaseModel):
    """A round within a tournament."""
    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name="rounds"
    )
    round_number = models.PositiveSmallIntegerField()
    is_complete = models.BooleanField(default=False)

    class Meta:
        ordering = ["round_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["tournament", "round_number"],
                name="unique_tournament_round",
            ),
        ]

    def __str__(self):
        return f"Round {self.round_number}"


class TournamentMatch(BaseModel):
    """A single match (pod) within a round."""
    round = models.ForeignKey(
        TournamentRound, on_delete=models.CASCADE, related_name="matches"
    )
    table_number = models.PositiveSmallIntegerField(default=1)
    bracket_position = models.PositiveSmallIntegerField(
        default=0, help_text="Position in single-elim bracket.",
    )
    session = models.ForeignKey(
        GameSession, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="tournament_matches",
    )
    current_game = models.PositiveSmallIntegerField(
        default=1, help_text="Current game number in a best-of-N match.",
    )
    is_complete = models.BooleanField(default=False)
    is_bye = models.BooleanField(default=False)

    class Meta:
        ordering = ["table_number"]

    def __str__(self):
        return f"Table {self.table_number}"

    @property
    def wins_needed(self):
        best_of = self.round.tournament.best_of
        return (best_of // 2) + 1


class TournamentMatchPlayer(BaseModel):
    """A participant's entry in a specific match."""
    match = models.ForeignKey(
        TournamentMatch, on_delete=models.CASCADE, related_name="players"
    )
    participant = models.ForeignKey(
        TournamentParticipant, on_delete=models.CASCADE, related_name="match_entries"
    )
    result = models.CharField(
        max_length=4, choices=GameResult.choices, blank=True,
    )
    placement = models.PositiveSmallIntegerField(
        default=0, help_text="1=winner in this match.",
    )
    game_wins = models.PositiveSmallIntegerField(
        default=0, help_text="Games won within this best-of-N match.",
    )

    class Meta:
        ordering = ["placement"]
        constraints = [
            models.UniqueConstraint(
                fields=["match", "participant"],
                name="unique_match_participant",
            ),
        ]

    def __str__(self):
        return f"{self.participant.name} — {self.get_result_display() or 'pending'}"


# ═══════════════════════════════════════════════════════════════════════════
# Tournament Statistics (per-user aggregate)
# ═══════════════════════════════════════════════════════════════════════════

class TournamentStats(BaseModel):
    """Aggregated tournament performance for a user in a given format."""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="tournament_stats"
    )
    format = models.CharField(max_length=20, choices=MagicFormat.choices)

    tournaments_played = models.PositiveIntegerField(default=0)
    tournaments_won = models.PositiveIntegerField(default=0, help_text="1st place finishes.")
    top_4 = models.PositiveIntegerField(default=0)

    match_wins = models.PositiveIntegerField(default=0)
    match_losses = models.PositiveIntegerField(default=0)
    match_draws = models.PositiveIntegerField(default=0)

    game_wins = models.PositiveIntegerField(default=0)
    game_losses = models.PositiveIntegerField(default=0)

    best_placement = models.PositiveSmallIntegerField(
        default=0,
        help_text="Best tournament finish (1 = won). 0 = never finished.",
    )

    class Meta:
        ordering = ["-tournaments_won", "-match_wins"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "format"],
                name="unique_user_format_tstats",
            ),
        ]
        verbose_name = "tournament stats"
        verbose_name_plural = "tournament stats"

    def __str__(self):
        return (
            f"{self.user.username} — {self.get_format_display()} — "
            f"{self.tournaments_won}W / {self.tournaments_played}T"
        )

    @property
    def total_matches(self):
        return self.match_wins + self.match_losses + self.match_draws

    @property
    def match_win_pct(self):
        total = self.total_matches
        return (self.match_wins / total * 100) if total else 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Multiplayer ELO Rating System
# ═══════════════════════════════════════════════════════════════════════════

class EloRating(BaseModel):
    """Per-user, per-format ELO rating."""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="elo_ratings"
    )
    format = models.CharField(max_length=20, choices=MagicFormat.choices)
    rating = models.IntegerField(default=1200)
    matches_played = models.PositiveIntegerField(default=0)
    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    draws = models.PositiveIntegerField(default=0)
    peak_rating = models.IntegerField(default=1200)

    class Meta:
        ordering = ["-rating"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "format"],
                name="unique_user_format_elo",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.get_format_display()} — {self.rating}"


class EloHistory(BaseModel):
    """Log of every rating change for audit / chart purposes."""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="elo_history"
    )
    format = models.CharField(max_length=20, choices=MagicFormat.choices)
    old_rating = models.IntegerField()
    new_rating = models.IntegerField()
    change = models.IntegerField()
    game = models.ForeignKey(
        GameRecord, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="elo_changes",
    )
    tournament_match = models.ForeignKey(
        TournamentMatch, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="elo_changes",
    )
    opponents_snapshot = models.JSONField(
        default=list, blank=True,
        help_text='[{"name": "...", "rating": N, "placement": N}, ...]',
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        sign = "+" if self.change >= 0 else ""
        return f"{self.user.username}: {sign}{self.change} → {self.new_rating}"
