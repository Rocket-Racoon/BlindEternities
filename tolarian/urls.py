from django.urls import path
from . import views

app_name = "tolarian"

urlpatterns = [
    # Colecciones
    path("",                                    views.CollectionListView.as_view(),   name="collection-list"),
    path("<uuid:pk>/",              views.CollectionDetailView.as_view(), name="collection-detail"),
    path("new/",                    views.CollectionCreateView.as_view(), name="collection-create"),
    path("<uuid:pk>/edit/",         views.CollectionEditView.as_view(),   name="collection-edit"),
    path("<uuid:pk>/delete/",       views.CollectionDeleteView.as_view(), name="collection-delete"),
    path("<uuid:pk>/export/",       views.CollectionExportView.as_view(), name="collection-export"),
    path("<uuid:pk>/import/",       views.CollectionImportView.as_view(), name="collection-import"),

    # Items de colección
    path("<uuid:pk>/add/",          views.CollectionAddCardView.as_view(),    name="collection-add-card"),
    path("<uuid:pk>/bulk-add/",     views.CollectionBulkAddView.as_view(),    name="collection-bulk-add"),
    path("<uuid:pk>/set-cover/",    views.CollectionSetCoverView.as_view(),   name="collection-set-cover"),
    path("items/<uuid:item_pk>/edit/",          views.CollectionItemEditView.as_view(),   name="collection-item-edit"),
    path("items/<uuid:item_pk>/delete/",        views.CollectionItemDeleteView.as_view(), name="collection-item-delete"),
    path("items/<uuid:item_pk>/move/",          views.CollectionItemMoveView.as_view(),   name="collection-item-move"),

    # Decks
    path("decks/",                              views.DeckListView.as_view(),    name="deck-list"),
    path("decks/<uuid:pk>/",                    views.DeckDetailView.as_view(),  name="deck-detail"),
    path("decks/new/",                          views.DeckCreateView.as_view(),  name="deck-create"),
    path("decks/<uuid:pk>/edit/",               views.DeckEditView.as_view(),    name="deck-edit"),
    path("decks/<uuid:pk>/delete/",             views.DeckDeleteView.as_view(),  name="deck-delete"),
    path("decks/<uuid:pk>/export/",             views.DeckExportView.as_view(),  name="deck-export"),
    path("decks/<uuid:pk>/import/",             views.DeckImportView.as_view(),  name="deck-import"),
    path("decks/<uuid:pk>/validate/",           views.DeckValidateView.as_view(),name="deck-validate"),

    # Deck cards
    path("decks/<uuid:pk>/add/",                views.DeckAddCardView.as_view(),      name="deck-add-card"),
    path("deck-cards/<uuid:card_pk>/edit/",     views.DeckCardEditView.as_view(),     name="deck-card-edit"),
    path("deck-cards/<uuid:card_pk>/delete/",   views.DeckCardDeleteView.as_view(),   name="deck-card-delete"),

    # Parciales HTMX
    path("decks/<uuid:pk>/curve/",              views.DeckCurvePartialView.as_view(), name="partial-curve"),
    path("decks/<uuid:pk>/stats/",              views.DeckStatsPartialView.as_view(), name="partial-stats"),

    # API JSON
    path("api/card-search/",                    views.CardSearchJSON.as_view(),       name="card-search"),
]

