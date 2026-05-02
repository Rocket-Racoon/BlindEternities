from datetime import timedelta

from django import forms
from django.contrib.auth.models import User
from django.utils import timezone

from core.constants import CardCondition, CardFinish
from .inventory import available_quantity
from .models import Listing, ListingStatus, ListingType, ListingVisibility


EXPIRES_IN_CHOICES = [
    ("keep",  "Keep current expiration"),
    ("never", "Never expire"),
    ("7",     "7 days"),
    ("30",    "30 days"),
    ("60",    "60 days"),
    ("90",    "90 days"),
]


class ListingForm(forms.ModelForm):
    expires_in_days = forms.ChoiceField(
        choices=EXPIRES_IN_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "input"}),
        help_text="When should this listing auto-close?",
    )

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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # Default: 30 days for new listings, "keep" for edits.
        if not self.instance.pk:
            self.fields["expires_in_days"].initial = "30"
        else:
            self.fields["expires_in_days"].initial = "keep"

    def clean(self):
        cleaned = super().clean()
        # Skip for BUY_WANTED — it's a request, not an offer.
        if cleaned.get("listing_type") != ListingType.SELL:
            return cleaned

        owner = self.instance.owner_id and self.instance.owner or self.user
        card_print = cleaned.get("card_print")
        quantity   = cleaned.get("quantity")
        finish     = cleaned.get("finish")
        condition  = cleaned.get("condition")
        language   = (cleaned.get("language") or "en").strip() or "en"
        if not (owner and card_print and quantity):
            return cleaned

        # When editing, exclude this listing's own reservation so the user
        # isn't blocked by their own current value.
        exclude_listing = self.instance if self.instance.pk else None
        avail = available_quantity(
            user=owner, card_print=card_print, finish=finish,
            condition=condition, language=language,
            exclude_listing=exclude_listing,
        )
        if avail < quantity:
            raise forms.ValidationError(
                f"You have {avail} available of {card_print.card.name} "
                f"({finish}, {condition}, {language}) after pending listings and trades; "
                f"this listing requires {quantity}. "
                f"Add the cards to a Binder or Trade List collection, or reduce the quantity."
            )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        choice = self.cleaned_data.get("expires_in_days") or "keep"
        if choice == "never":
            instance.expires_at = None
        elif choice != "keep":
            try:
                days = int(choice)
                instance.expires_at = timezone.now() + timedelta(days=days)
            except ValueError:
                pass
        # Re-extending an expired listing should reopen it.
        if instance.status == ListingStatus.EXPIRED and not instance.is_expired():
            instance.status = ListingStatus.OPEN
        if commit:
            instance.save()
            self.save_m2m()
        return instance


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


class TransactionMessageForm(forms.Form):
    body = forms.CharField(
        label="",
        widget=forms.Textarea(attrs={
            "class": "input w-full", "rows": 2,
            "placeholder": "Write a message…",
        }),
        max_length=4000,
    )

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise forms.ValidationError("Message can't be empty.")
        return body


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
