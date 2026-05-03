from django.urls import path

from . import views

app_name = "conflux"

urlpatterns = [
    path("",                        views.EvaluationListView.as_view(),   name="evaluation-list"),
    path("new/",                    views.EvaluationCreateView.as_view(), name="evaluation-create"),
    path("<uuid:pk>/",              views.EvaluationDetailView.as_view(), name="evaluation-detail"),
    path("<uuid:pk>/delete/",       views.EvaluationDeleteView.as_view(), name="evaluation-delete"),
]
