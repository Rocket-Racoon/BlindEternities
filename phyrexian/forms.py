# phyrexian/forms.py
from django import forms
from django.utils import timezone
from tolarian.models import Deck
from .models import GameRecord


class GameRecordForm(forms.ModelForm):
    class Meta:
        model = GameRecord
        fields = [
            "deck", "format", "result", "opponent_name",
            "opponent_deck_name", "turns", "date_played", "notes",
        ]
        widgets = {
            "date_played": forms.DateInput(
                attrs={"type": "date", "class": "input"},
            ),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "input"}),
            "opponent_name": forms.TextInput(attrs={"class": "input"}),
            "opponent_deck_name": forms.TextInput(attrs={"class": "input"}),
            "turns": forms.NumberInput(attrs={"class": "input", "min": 1}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["deck"].queryset = Deck.objects.filter(
                user=user, is_active=True
            )
        self.fields["deck"].required = False
        self.fields["date_played"].initial = timezone.now().date()

        for field_name in self.fields:
            field = self.fields[field_name]
            if not isinstance(field.widget, (forms.CheckboxInput, forms.DateInput, forms.Textarea)):
                field.widget.attrs.setdefault("class", "input")
