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
    path("prices/", views.PriceAnalyticsView.as_view(), name="price-analytics"),

    # Game records CRUD
    path("games/", views.GameRecordListView.as_view(), name="game-list"),
    path("games/new/", views.GameRecordCreateView.as_view(), name="game-create"),
    path("games/<uuid:pk>/edit/", views.GameRecordUpdateView.as_view(), name="game-edit"),
    path("games/<uuid:pk>/delete/", views.GameRecordDeleteView.as_view(), name="game-delete"),

    # Live game sessions
    path("session/new/", views.SessionSetupView.as_view(), name="session-setup"),
    path("session/<uuid:pk>/", views.SessionLiveView.as_view(), name="session-live"),
    path("session/<uuid:pk>/end/", views.SessionEndView.as_view(), name="session-end"),
    path("session/<uuid:pk>/summary/", views.SessionSummaryView.as_view(), name="session-summary"),
    path("session/<uuid:pk>/next-turn/", views.SessionNextTurnView.as_view(), name="session-next-turn"),
    path("session/<uuid:pk>/reset/", views.SessionResetView.as_view(), name="session-reset"),
    path("session/<uuid:pk>/auto-finish/", views.SessionAutoFinishView.as_view(), name="session-auto-finish"),
    path("session/<uuid:pk>/log-turn/", views.SessionLogTurnView.as_view(), name="session-log-turn"),
    path("session/<uuid:pk>/log/", views.SessionLogPartialView.as_view(), name="session-log"),

    # Session HTMX endpoints (per-player)
    path("session/<uuid:player_pk>/life/", views.SessionLifeChangeView.as_view(), name="session-life"),
    path("session/<uuid:player_pk>/counter/", views.SessionCounterChangeView.as_view(), name="session-counter"),
    path("session/<uuid:player_pk>/toggle/", views.SessionToggleStatusView.as_view(), name="session-toggle"),
    path("session/<uuid:player_pk>/cmdr-damage/", views.SessionCommanderDamageView.as_view(), name="session-cmdr-damage"),
    path("session/<uuid:player_pk>/cmdr-tax/", views.SessionCommanderTaxView.as_view(), name="session-cmdr-tax"),
    path("session/<uuid:player_pk>/eliminate/", views.PlayerEliminateView.as_view(), name="session-eliminate"),

    # Tournaments
    path("tournaments/", views.TournamentListView.as_view(), name="tournament-list"),
    path("tournaments/new/", views.TournamentCreateView.as_view(), name="tournament-create"),
    path("tournaments/<uuid:pk>/", views.TournamentDetailView.as_view(), name="tournament-detail"),
    path("tournaments/<uuid:pk>/add-player/", views.TournamentAddParticipantView.as_view(), name="tournament-add-participant"),
    path("tournaments/<uuid:pk>/drop/<uuid:participant_pk>/", views.TournamentDropParticipantView.as_view(), name="tournament-drop-participant"),
    path("tournaments/<uuid:pk>/generate-round/", views.TournamentGenerateRoundView.as_view(), name="tournament-generate-round"),
    path("tournaments/match/<uuid:match_pk>/result/", views.TournamentRecordResultView.as_view(), name="tournament-record-result"),
    path("tournaments/match/<uuid:match_pk>/game/", views.TournamentRecordGameView.as_view(), name="tournament-record-game"),

    # ELO
    path("elo/", views.EloLeaderboardView.as_view(), name="elo-leaderboard"),
    path("elo/profile/<int:user_pk>/", views.EloProfileView.as_view(), name="elo-profile"),

    # API
    path("api/deck-search/", views.DeckSearchJSON.as_view(), name="deck-search"),
    path("api/user-search/", views.UserSearchJSON.as_view(), name="user-search"),
    path("api/user-decks/<int:user_pk>/", views.UserDecksJSON.as_view(), name="user-decks"),

    # HTMX partials
    path("partials/stats/", views.DashboardStatsPartialView.as_view(), name="partial-stats"),
]
