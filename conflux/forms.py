from django import forms

from tolarian.models import Deck
from core.constants import MagicFormat
from .models import BracketTier, DeckEvaluation


class DeckEvaluationForm(forms.ModelForm):
    """
    Submit either an existing Deck (preferred) OR pasted decklist text.
    `bracket_user` is the owner's self-rated bracket; the AI suggests its own.
    """
    deck = forms.ModelChoiceField(
        queryset=Deck.objects.none(),
        required=False,
        empty_label="— paste a decklist instead —",
        widget=forms.Select(attrs={"class": "input"}),
        help_text="Pick a saved Commander deck, or leave blank and paste below.",
    )

    class Meta:
        model = DeckEvaluation
        fields = ["deck", "commander", "decklist_text", "bracket_user"]
        widgets = {
            "commander":     forms.TextInput(attrs={"class": "input", "placeholder": "e.g. Atraxa, Praetors' Voice"}),
            "decklist_text": forms.Textarea(attrs={"class": "input font-mono", "rows": 18, "placeholder": "1 Sol Ring\n1 Arcane Signet\n..."}),
            "bracket_user":  forms.Select(attrs={"class": "input"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user
        if user is not None:
            self.fields["deck"].queryset = (
                Deck.objects
                .filter(user=user, is_active=True, format=MagicFormat.COMMANDER)
                .order_by("name")
            )
        self.fields["bracket_user"].choices = [("", "— self-rate (optional) —")] + list(BracketTier.choices)

    def clean(self):
        data = super().clean()
        deck = data.get("deck")
        text = (data.get("decklist_text") or "").strip()
        if not deck and not text:
            raise forms.ValidationError(
                "Pick a saved deck or paste a decklist — one of them is required."
            )
        return data
