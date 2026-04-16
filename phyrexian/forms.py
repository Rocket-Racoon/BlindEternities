# phyrexian/forms.py
from django import forms
from django.utils import timezone
from core.constants import MagicFormat
from tolarian.models import Deck
from .models import GameRecord, GameSession, EliminationCause, FORMAT_STARTING_LIFE


class GameRecordForm(forms.ModelForm):
    class Meta:
        model = GameRecord
        fields = [
            "deck", "format", "result",
            "my_placement", "elimination_cause",
            "opponent_name", "opponent_deck_name",
            "turns", "date_played", "notes",
        ]
        widgets = {
            "date_played": forms.DateInput(
                attrs={"type": "date", "class": "input"},
            ),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "input"}),
            "opponent_name": forms.HiddenInput(),
            "opponent_deck_name": forms.HiddenInput(),
            "turns": forms.NumberInput(attrs={"class": "input", "min": 1}),
            "my_placement": forms.NumberInput(attrs={"class": "input", "min": 0}),
        }

    # Hidden field to receive opponents JSON from Alpine.js
    opponents_json = forms.CharField(
        widget=forms.HiddenInput(), required=False,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["deck"].queryset = Deck.objects.filter(
                user=user, is_active=True
            )
        self.fields["deck"].required = False
        self.fields["date_played"].initial = timezone.now().date()
        self.fields["my_placement"].required = False
        self.fields["elimination_cause"].required = False

        for field_name in self.fields:
            field = self.fields[field_name]
            if not isinstance(field.widget, (forms.CheckboxInput, forms.DateInput, forms.Textarea, forms.HiddenInput)):
                field.widget.attrs.setdefault("class", "input")


# ---------------------------------------------------------------------------
# Session Setup
# ---------------------------------------------------------------------------
PLAYER_COUNT_CHOICES = [(i, f"{i} Players") for i in range(2, 7)]

PLAYER_COLORS = [
    "#6366F1",  # Indigo
    "#EF4444",  # Red
    "#22C55E",  # Green
    "#EAB308",  # Yellow
    "#06B6D4",  # Cyan
    "#F97316",  # Orange
]


class SessionSetupForm(forms.Form):
    """Step 1: choose format and player count."""
    format = forms.ChoiceField(
        choices=MagicFormat.choices,
        initial=MagicFormat.COMMANDER,
        widget=forms.Select(attrs={"class": "input"}),
    )
    player_count = forms.ChoiceField(
        choices=PLAYER_COUNT_CHOICES,
        initial=4,
        widget=forms.Select(attrs={"class": "input"}),
    )
    starting_life = forms.IntegerField(
        initial=40,
        min_value=1,
        max_value=999,
        widget=forms.NumberInput(attrs={"class": "input", "min": 1}),
    )

    def clean_player_count(self):
        return int(self.cleaned_data["player_count"])


class PlayerSetupForm(forms.Form):
    """Per-player name and color (rendered dynamically based on player_count)."""
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "Player name",
        }),
    )
    color = forms.CharField(
        max_length=7,
        initial="#6366F1",
        widget=forms.HiddenInput(),
    )
