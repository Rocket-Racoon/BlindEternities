# core/context_processors.py
from core.constants import MagicFormat

def user_profile(request):
    if request.user.is_authenticated:
        return {"user_profile": getattr(request.user, "profile", None)}
    return {"user_profile": None}


def magic_formats(request):
    return {"magic_formats": MagicFormat.choices}


def site_settings(request):
    return {
        "site_name": "Blind Eternities",
        "site_version": "0.1.0",
    }