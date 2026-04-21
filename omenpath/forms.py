from django import forms
from django.contrib.auth.models import User

from core.constants import CardCondition, CardFinish
from .models import Listing, ListingType, ListingVisibility


class ListingForm(forms.ModelForm):
    class Meta:
        model  = Listing
        fields = [
            "listing_type", "card_print", "condition", "finish", "language",
            "quantity", "asking_price", "visibility", "notes",
        ]
        widgets = {
            "listing_type": forms.Select(attrs={"class": "input"}),
            "card_print":   forms.HiddenInput(),
            "condition":    forms.Select(attrs={"class": "input"}),
            "finish":       forms.Select(attrs={"class": "input"}),
            "language":     forms.TextInput(attrs={"class": "input", "placeholder": "en"}),
            "quantity":     forms.NumberInput(attrs={"class": "input", "min": 1}),
            "asking_price": forms.NumberInput(attrs={"class": "input", "step": "0.01", "min": 0}),
            "visibility":   forms.Select(attrs={"class": "input"}),
            "notes":        forms.Textarea(attrs={"class": "input", "rows": 3}),
        }


class TradeProposeForm(forms.Form):
    recipient = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={"class": "input"}),
        label="Propose trade to",
    )
    offered = forms.CharField(widget=forms.HiddenInput(), required=False)
    requested = forms.CharField(widget=forms.HiddenInput(), required=False)
    offered_text = forms.CharField(
        required=False,
        label='Or type cards to offer (format: "4 Lightning Bolt")',
        widget=forms.Textarea(attrs={"class": "input font-mono", "rows": 4}),
    )
    requested_text = forms.CharField(
        required=False,
        label="Or type cards to request",
        widget=forms.Textarea(attrs={"class": "input font-mono", "rows": 4}),
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "input", "rows": 3}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields["recipient"].queryset = (
                user.profile.friends()
                if hasattr(user, "profile") else User.objects.exclude(pk=user.pk)
            )


class SaleProposeForm(forms.Form):
    """Buyer-initiated from a Listing(type=SELL), or seller-initiated from Listing(type=BUY_WANTED)."""
    quantity = forms.IntegerField(min_value=1, initial=1,
                                  widget=forms.NumberInput(attrs={"class": "input"}))
    price_agreed = forms.DecimalField(
        required=False, min_value=0, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "input", "step": "0.01"}),
        help_text="Leave blank to accept the listed asking price.",
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "input", "rows": 3}),
    )
