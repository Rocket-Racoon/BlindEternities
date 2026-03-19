from django.urls import path
from . import views

app_name = "multiverse"

urlpatterns = [
    path("",                            views.CardListView.as_view(),    name="card-list"),
    path("<uuid:oracle_id>/",           views.CardDetailView.as_view(),  name="card-detail"),
    path("sets/",                       views.SetListView.as_view(),     name="set-list"),
    path("sets/<str:code>/",            views.SetDetailView.as_view(),   name="set-detail"),
    # Parciales HTMX
    path("<uuid:oracle_id>/rulings/",   views.CardRulingsPartialView.as_view(),   name="partial-rulings"),
    path("<uuid:oracle_id>/prints/",    views.CardPrintsPartialView.as_view(),    name="partial-prints"),
    path("<uuid:oracle_id>/legality/",  views.CardLegalityPartialView.as_view(),  name="partial-legality"),
]
