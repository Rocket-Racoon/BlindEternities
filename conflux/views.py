from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView

from core.mixins import OwnerRequiredMixin
from core.utils import paginate_queryset

from .forms import DeckEvaluationForm
from .models import DeckEvaluation, EvaluationStatus
from .services import evaluate_async, serialize_deck


class EvaluationListView(LoginRequiredMixin, ListView):
    template_name = "conflux/evaluation_list.html"
    paginate_by = 20

    def get_queryset(self):
        return (
            DeckEvaluation.objects
            .filter(user=self.request.user, is_active=True)
            .select_related("deck")
        )


class EvaluationCreateView(LoginRequiredMixin, CreateView):
    model         = DeckEvaluation
    form_class    = DeckEvaluationForm
    template_name = "conflux/evaluation_create.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        deck_pk = self.request.GET.get("deck")
        if deck_pk:
            from tolarian.models import Deck
            try:
                deck = Deck.objects.get(pk=deck_pk, user=self.request.user, is_active=True)
                initial["deck"] = deck.pk
                initial["commander"] = ", ".join(
                    dc.card.name for dc in deck.commander_cards.select_related("card")
                )
            except (Deck.DoesNotExist, ValueError):
                pass
        return initial

    def form_valid(self, form):
        ev: DeckEvaluation = form.save(commit=False)
        ev.user = self.request.user

        if ev.deck and not ev.decklist_text.strip():
            commander, decklist = serialize_deck(ev.deck)
            ev.commander     = ev.commander or commander
            ev.decklist_text = decklist

        ev.status = EvaluationStatus.PENDING
        ev.save()

        evaluate_async(ev.pk)
        messages.success(self.request, "Evaluation queued — refreshing while the model runs.")
        return redirect(ev.get_absolute_url())


class EvaluationDetailView(OwnerRequiredMixin, DetailView):
    model         = DeckEvaluation
    template_name = "conflux/evaluation_detail.html"
    context_object_name = "evaluation"

    def render_to_response(self, context, **kwargs):
        if self.request.headers.get("HX-Request") == "true":
            self.template_name = "conflux/partials/result_panel.html"
        return super().render_to_response(context, **kwargs)


class EvaluationDeleteView(OwnerRequiredMixin, DeleteView):
    model         = DeckEvaluation
    template_name = "conflux/evaluation_confirm_delete.html"
    success_url   = reverse_lazy("conflux:evaluation-list")
