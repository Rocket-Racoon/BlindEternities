# tolarian/forms.py
from django import forms
from core.constants import (
    MagicFormat, CardCondition, CardFinish, CollectionType, DeckZone,
)
from .models import (
    Collection, CollectionItem,
    Deck, DeckCard,
)


class CollectionForm(forms.ModelForm):
    class Meta:
        model  = Collection
        fields = ["name", "description", "collection_type", "is_public", "cover_card"]
        widgets = {
            "name":            forms.TextInput(attrs={"class": "input"}),
            "description":     forms.Textarea(attrs={"class": "input", "rows": 3}),
            "collection_type": forms.Select(attrs={"class": "input"}),
            "cover_card":      forms.HiddenInput(),
        }


class CollectionItemForm(forms.ModelForm):
    class Meta:
        model  = CollectionItem
        fields = [
            "card", "print", "quantity", "condition",
            "finish", "language", "purchase_price",
            "loan_to_user", "loan_to_name", "notes",
        ]
        widgets = {
            "card":           forms.HiddenInput(),
            "print":          forms.HiddenInput(),
            "quantity":       forms.NumberInput(attrs={"class": "input", "min": 1}),
            "condition":      forms.Select(attrs={"class": "input"}),
            "finish":         forms.Select(attrs={"class": "input"}),
            "language":       forms.TextInput(attrs={"class": "input", "placeholder": "en"}),
            "purchase_price": forms.NumberInput(attrs={"class": "input", "step": "0.01"}),
            "loan_to_user":   forms.HiddenInput(),
            "loan_to_name":   forms.TextInput(attrs={"class": "input", "placeholder": "Nombre de la persona"}),
            "notes":          forms.Textarea(attrs={"class": "input", "rows": 2}),
        }


class CollectionImportForm(forms.Form):
    file = forms.FileField(
        label="Archivo CSV",
        help_text="Formatos soportados: Moxfield, Archidekt, DragonShield, TCGPlayer",
        widget=forms.FileInput(attrs={"class": "input", "accept": ".csv"}),
    )


class DeckForm(forms.ModelForm):
    class Meta:
        model  = Deck
        fields = ["name", "description", "format", "is_public", "cover_card", "notes"]
        widgets = {
            "name":        forms.TextInput(attrs={"class": "input"}),
            "description": forms.Textarea(attrs={"class": "input", "rows": 3}),
            "format":      forms.Select(attrs={"class": "input"}),
            "cover_card":  forms.HiddenInput(),
            "notes":       forms.Textarea(attrs={"class": "input", "rows": 4}),
        }


class DeckCardForm(forms.ModelForm):
    class Meta:
        model  = DeckCard
        fields = ["card", "print", "zone", "quantity", "owned", "notes"]
        widgets = {
            "card":     forms.HiddenInput(),
            "print":    forms.HiddenInput(),
            "zone":     forms.Select(attrs={"class": "input"}),
            "quantity": forms.NumberInput(attrs={"class": "input", "min": 1}),
            "notes":    forms.Textarea(attrs={"class": "input", "rows": 2}),
        }


class DeckImportForm(forms.Form):
    text = forms.CharField(
        required=False,
        label="Lista de cartas",
        help_text="Formato: 1x Lightning Bolt o 1 Lightning Bolt",
        widget=forms.Textarea(attrs={
            "class":       "input font-mono",
            "rows":        15,
            "placeholder": "1x Lightning Bolt\n4x Counterspell\n...",
        }),
    )
    file = forms.FileField(
        required=False,
        label="O importar desde archivo",
        help_text="CSV de Moxfield, Archidekt, etc.",
        widget=forms.FileInput(attrs={"class": "input", "accept": ".csv,.txt"}),
    )

    def clean(self):
        cleaned = super().clean()
        text    = cleaned.get("text", "").strip()
        file    = cleaned.get("file")
        if not text and not file:
            raise forms.ValidationError(
                "Debes pegar una lista de cartas o subir un archivo."
            )
        return cleaned