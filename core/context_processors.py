# core/context_processors.py

MAGIC_FORMATS = [
    "Standard",
    "Pioneer",
    "Modern",
    "Legacy",
    "Vintage",
    "Commander",
    "Pauper",
    "Draft",
    "Sealed",
]


def user_profile(request):
    if request.user.is_authenticated:
        return {"user_profile": getattr(request.user, "profile", None)}
    return {"user_profile": None}


def magic_formats(request):
    return {"magic_formats": MAGIC_FORMATS}


def site_settings(request):
    return {
        "site_name": "BlindEternities",
        "site_version": "0.1.0",
    }