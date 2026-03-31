from django.urls import path
from . import views

app_name = "phyrexian"

urlpatterns = [
    # Dashboard
    path("", views.DashboardView.as_view(), name="dashboard"),

    # Stat pages
    path("collection/", views.CollectionStatsView.as_view(), name="collection-stats"),
    path("decks/", views.DeckStatsView.as_view(), name="deck-stats"),
    path("winrate/", views.WinRateView.as_view(), name="win-rate"),

    # Game records CRUD
    path("games/", views.GameRecordListView.as_view(), name="game-list"),
    path("games/new/", views.GameRecordCreateView.as_view(), name="game-create"),
    path("games/<uuid:pk>/edit/", views.GameRecordUpdateView.as_view(), name="game-edit"),
    path("games/<uuid:pk>/delete/", views.GameRecordDeleteView.as_view(), name="game-delete"),
]
