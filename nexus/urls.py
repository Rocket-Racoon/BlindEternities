# nexus/urls.py
from django.urls import path
from . import views

app_name = "nexus"

urlpatterns = [
    path("",                                views.HomeView.as_view(),               name="home"),
    path("u/<str:username>/",               views.ProfileDetailView.as_view(),      name="profile-detail"),
    path("u/<str:username>/decks/",         views.UserDecksView.as_view(),          name="user-decks"),
    path("u/<str:username>/collection/",    views.UserCollectionView.as_view(),     name="user-collection"),
    path("settings/profile/",               views.ProfileEditView.as_view(),        name="profile-edit"),
    path("settings/avatar/",                views.AvatarUploadView.as_view(),       name="avatar-upload"),
    # Partials HTMX
    path("u/<str:username>/partials/decks/",        views.UserDecksPartialView.as_view(),       name="partial-decks"),
    path("u/<str:username>/partials/collection/",   views.UserCollectionPartialView.as_view(),  name="partial-collection"),
    path("u/<str:username>/partials/overview/",     views.UserOverviewPartialView.as_view(),    name="partial-overview"),
]