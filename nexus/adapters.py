# nexus/adapters.py
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class NexusSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Adaptador personalizado para OAuth de Google y GitHub.
    Puebla el Profile con datos del proveedor al momento del registro.
    """

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        self._populate_profile(user, sociallogin)
        return user

    def _populate_profile(self, user, sociallogin):
        from .models import Profile

        profile, _ = Profile.objects.get_or_create(user=user)
        extra = sociallogin.account.extra_data
        provider = sociallogin.account.provider

        if provider == "google":
            if not profile.display_name:
                profile.display_name = extra.get("name", "")
            if not profile.avatar:
                avatar_url = extra.get("picture", "")
                if avatar_url:
                    self._set_avatar_from_url(profile, avatar_url)

        elif provider == "github":
            if not profile.display_name:
                profile.display_name = extra.get("name") or extra.get("login", "")
            if not profile.location:
                profile.location = extra.get("location", "")
            if not profile.bio:
                profile.bio = extra.get("bio", "")
            if not profile.avatar:
                avatar_url = extra.get("avatar_url", "")
                if avatar_url:
                    self._set_avatar_from_url(profile, avatar_url)

        profile.save()

    def _set_avatar_from_url(self, profile, url):
        """Descarga el avatar del proveedor y lo guarda en MEDIA_ROOT."""
        import requests
        from django.core.files.base import ContentFile

        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                filename = f"oauth_{profile.user.id}.jpg"
                profile.avatar.save(filename, ContentFile(response.content), save=False)
        except requests.RequestException:
            pass  # Si falla la descarga, el avatar queda vacío — no es crítico