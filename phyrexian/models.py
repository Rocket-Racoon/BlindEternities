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

    class Meta:
        ordering = ["-date_played", "-created_at"]
        verbose_name = "game record"
        verbose_name_plural = "game records"

    def __str__(self):
        deck_name = self.deck.name if self.deck else "No deck"
        return f"{self.get_result_display()} — {deck_name} vs {self.opponent_name or '?'}"

    def get_absolute_url(self):
        return reverse("phyrexian:game-detail", kwargs={"pk": self.pk})
