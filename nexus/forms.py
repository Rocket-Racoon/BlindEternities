# nexus/forms.py
from django import forms
from .models import Profile


class ProfileForm(forms.ModelForm):
    class Meta:
        model  = Profile
        fields = [
            "display_name",
            "avatar",
            "bio",
            "location",
            "preferred_format",
            "is_public",
        ]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
        }