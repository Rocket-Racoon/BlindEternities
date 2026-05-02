from django.urls import path
from . import views

app_name = "omenpath"

urlpatterns = [
    path("",                              views.ListingListView.as_view(),   name="listing-list"),
    path("listings/new/",                 views.ListingCreateView.as_view(), name="listing-create"),
    path("listings/<uuid:pk>/",           views.ListingDetailView.as_view(), name="listing-detail"),
    path("listings/<uuid:pk>/edit/",      views.ListingUpdateView.as_view(), name="listing-update"),
    path("listings/<uuid:pk>/delete/",    views.ListingDeleteView.as_view(), name="listing-delete"),
    path("listings/<uuid:listing_pk>/offer/", views.sale_propose,            name="sale-propose"),

    path("trades/",                       views.TransactionInboxView.as_view(), name="transaction-inbox"),
    path("trades/new/",                   views.TradeProposeView.as_view(),     name="trade-propose"),
    path("trades/search-tradable/",       views.tradable_search_json,           name="tradable-search"),
    path("trades/<uuid:pk>/",             views.TransactionDetailView.as_view(), name="transaction-detail"),
    path("trades/<uuid:pk>/counter/",     views.TradeCounterView.as_view(),      name="trade-counter"),
    path("trades/<uuid:pk>/messages/",     views.transaction_message,             name="transaction-message"),
    path("trades/<uuid:pk>/<str:action>/", views.transaction_action,             name="transaction-action"),
]
