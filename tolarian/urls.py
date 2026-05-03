from django.urls import path
from . import views
from . import suggest_views as suggest

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

    path("decks/<uuid:pk>/set-cover/",            views.DeckSetCoverView.as_view(),     name="deck-set-cover"),
    path("decks/<uuid:pk>/clone/",               views.DeckCloneView.as_view(),        name="deck-clone"),
    path("decks/<uuid:pk>/share/",               views.DeckShareView.as_view(),        name="deck-share"),

    # Deck versioning
    path("decks/<uuid:pk>/versions/",            views.DeckVersionListView.as_view(),   name="deck-version-list"),
    path("decks/<uuid:pk>/versions/create/",     views.DeckVersionCreateView.as_view(), name="deck-version-create"),
    path("deck-versions/<uuid:version_pk>/",     views.DeckVersionDetailView.as_view(), name="deck-version-detail"),
    path("deck-versions/<uuid:version_pk>/restore/", views.DeckVersionRestoreView.as_view(), name="deck-version-restore"),

    # Deck comparison
    path("decks/compare/",                       views.DeckCompareView.as_view(),      name="deck-compare"),

    # Shared deck (public, no login)
    path("shared/<str:token>/",                  views.DeckSharedView.as_view(),       name="deck-shared"),

    # Deck cards
    path("decks/<uuid:pk>/add/",                views.DeckAddCardView.as_view(),      name="deck-add-card"),

    # Suggest modal — tag-based recommendations
    path("decks/<uuid:pk>/suggest/",                          suggest.DeckSuggestModalView.as_view(),   name="deck-suggest"),
    path("decks/<uuid:pk>/suggest/results/",                  suggest.DeckSuggestResultsView.as_view(), name="deck-suggest-results"),
    path("decks/<uuid:pk>/suggest/row/<uuid:card_pk>/",       suggest.DeckSuggestRowView.as_view(),     name="deck-suggest-row"),
    path("decks/<uuid:pk>/suggest/prints/<uuid:card_pk>/",    suggest.DeckSuggestPrintsView.as_view(),  name="deck-suggest-prints"),
    path("decks/<uuid:pk>/suggest/add/<uuid:card_pk>/",       suggest.DeckSuggestAddView.as_view(),     name="deck-suggest-add"),
    path("decks/<uuid:pk>/suggest/dec/<uuid:card_pk>/",       suggest.DeckSuggestDecView.as_view(),     name="deck-suggest-dec"),
    path("deck-cards/<uuid:card_pk>/edit/",     views.DeckCardEditView.as_view(),     name="deck-card-edit"),
    path("deck-cards/<uuid:card_pk>/qty/",      views.DeckCardQtyView.as_view(),      name="deck-card-qty"),
    path("deck-cards/<uuid:card_pk>/delete/",   views.DeckCardDeleteView.as_view(),   name="deck-card-delete"),

    # Deck categories
    path("decks/<uuid:pk>/categories/create/",     views.DeckCategoryCreateView.as_view(),  name="deck-category-create"),
    path("deck-categories/<uuid:cat_pk>/rename/",  views.DeckCategoryRenameView.as_view(),  name="deck-category-rename"),
    path("deck-categories/<uuid:cat_pk>/delete/",  views.DeckCategoryDeleteView.as_view(),  name="deck-category-delete"),

    # Deck card organisation
    path("deck-cards/<uuid:card_pk>/move-category/",       views.DeckCardMoveCategoryView.as_view(),         name="deck-card-move-category"),
    path("deck-cards/<uuid:card_pk>/toggle-game-changer/", views.DeckCardToggleGameChangerView.as_view(),    name="deck-card-toggle-gc"),
    path("decks/<uuid:pk>/bulk-move-category/",            views.DeckCardBulkMoveCategoryView.as_view(),     name="deck-bulk-move-category"),

    # Parciales HTMX
    path("decks/<uuid:pk>/content/",            views.DeckContentPartialView.as_view(), name="deck-content"),
    path("decks/<uuid:pk>/curve/",              views.DeckCurvePartialView.as_view(), name="partial-curve"),
    path("decks/<uuid:pk>/stats/",              views.DeckStatsPartialView.as_view(), name="partial-stats"),

    # API JSON
    path("api/card-search/",                    views.CardSearchJSON.as_view(),       name="card-search"),
]

