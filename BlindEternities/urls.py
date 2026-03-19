"""
URL configuration for BlindEternities project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # Allauth — login, signup, OAuth callbacks
    path("accounts/", include("allauth.urls")),
    # Apps
    path("",           include("nexus.urls",      namespace="nexus")),
    path("cards/",     include("multiverse.urls",  namespace="multiverse")),
    path("collection/",include("tolarian.urls",    namespace="tolarian")),
    path("stats/",     include("phyrexian.urls",   namespace="phyrexian")),
    path("market/",    include("omenpath.urls",   namespace="omenpath")),
]


if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)