import csv
import io
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    TemplateView, ListView, DetailView,
    CreateView, UpdateView, DeleteView, View,
)
from core.constants import CardCondition, CardFinish
from core.mixins import OwnerRequiredMixin
from core.utils import paginate_queryset
from multiverse.models import Card, CardPrint
from .mixins import CollectionOwnerMixin, DeckOwnerMixin
from .models import (
    Collection, CollectionItem, CollectionType,
    Deck, DeckCard, DeckZone, 
)
from .forms import (
    CollectionForm, CollectionItemForm,
    DeckForm, DeckCardForm,
    DeckImportForm, CollectionImportForm,
)
from .utils import (
    parse_decklist_text,
    parse_collection_csv,
    parse_collection_text,
    deck_to_csv,
    collection_to_csv,
)


# ---------------------------------------------------------------------------
# Colecciones
# ---------------------------------------------------------------------------
class CollectionListView(LoginRequiredMixin, TemplateView):
    template_name = "tolarian/collection_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        collections = (
            Collection.objects
            .filter(user=self.request.user, is_active=True)
            .annotate(
                item_count=Count("items"),
                total_qty=Sum("items__quantity"),
            )
            .order_by("collection_type", "name")
        )
        ctx.update({
            "collections":  collections,
            "binders":      collections.filter(collection_type=CollectionType.BINDER),
            "wishlists":    collections.filter(collection_type=CollectionType.WISHLIST),
            "tradelists":   collections.filter(collection_type=CollectionType.TRADELIST),
            "loanlists":    collections.filter(collection_type=CollectionType.LOANLIST),
        })
        return ctx


class CollectionDetailView(LoginRequiredMixin, TemplateView):
    template_name = "tolarian/collection_detail.html"

    def dispatch(self, request, *args, **kwargs):
        collection = get_object_or_404(Collection, pk=kwargs["pk"])
        if not collection.is_public and collection.user != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx        = super().get_context_data(**kwargs)
        collection = get_object_or_404(Collection, pk=self.kwargs["pk"])
        items      = (
            collection.items
            .select_related("card", "print__cardset")
            .prefetch_related("card__faces")
            .order_by("card__name")
        )
        q = self.request.GET.get("q", "")
        if q:
            items = items.filter(card__name__icontains=q)

        ctx.update({
            "collection":         collection,
            "page_obj":           paginate_queryset(items, self.request.GET.get("page"), per_page=40),
            "is_owner":           collection.user == self.request.user,
            "collection_add_url": reverse("tolarian:collection-add-card", kwargs={"pk": collection.pk}),
            "collection_bulk_add_url": reverse("tolarian:collection-bulk-add", kwargs={"pk": collection.pk}),
            "condition_choices":  CardCondition.choices,
            "finish_choices":     CardFinish.choices,
            "q":                  q,
        })
        return ctx


class CollectionCreateView(LoginRequiredMixin, CreateView):
    model         = Collection
    form_class    = CollectionForm
    template_name = "tolarian/collection_form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Colección creada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("tolarian:collection-detail", kwargs={"pk": self.object.pk})


class CollectionEditView(CollectionOwnerMixin, UpdateView):
    model         = Collection
    form_class    = CollectionForm
    template_name = "tolarian/collection_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Colección actualizada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("tolarian:collection-detail", kwargs={"pk": self.object.pk})


class CollectionDeleteView(CollectionOwnerMixin, DeleteView):
    model        = Collection
    template_name = "tolarian/collection_confirm_delete.html"
    success_url  = reverse_lazy("tolarian:collection-list")

    def form_valid(self, form):
        messages.success(self.request, "Colección eliminada.")
        return super().form_valid(form)


class CollectionAddCardView(CollectionOwnerMixin, View):
    def post(self, request, pk):
        collection = get_object_or_404(Collection, pk=pk)
        form       = CollectionItemForm(request.POST)

        if form.is_valid():
            item = form.save(commit=False)
            item.collection = collection

            # Si ya existe el mismo item (carta+print+condition+finish+lang)
            # incrementa la cantidad en lugar de duplicar
            existing = CollectionItem.objects.filter(
                collection=collection,
                card=item.card,
                print=item.print,
                condition=item.condition,
                finish=item.finish,
                language=item.language,
            ).first()

            if existing:
                existing.quantity += item.quantity
                existing.save(update_fields=["quantity", "updated_at"])
                messages.success(request, f"Cantidad actualizada: {existing}")
            else:
                item.save()
                messages.success(request, f"Carta agregada: {item.card.name}")

        if request.headers.get("HX-Request"):
            return HttpResponse(status=204)
        return redirect("tolarian:collection-detail", pk=pk)


class CollectionBulkAddView(CollectionOwnerMixin, View):
    """Parse a text list of cards (e.g. '4x Lightning Bolt') and add them."""

    def post(self, request, pk):
        collection = get_object_or_404(Collection, pk=pk)
        text = request.POST.get("text", "").strip()

        if not text:
            messages.error(request, "Pega una lista de cartas.")
            return redirect("tolarian:collection-detail", pk=pk)

        results = parse_collection_text(text, collection)

        parts = []
        if results["created"]:
            parts.append(f"{results['created']} nueva(s)")
        if results["updated"]:
            parts.append(f"{results['updated']} actualizada(s)")
        if results["not_found"]:
            parts.append(f"{len(results['not_found'])} no encontrada(s)")

        messages.success(request, f"Lote agregado — {', '.join(parts)}.")

        if results["not_found"]:
            messages.warning(
                request,
                f"No encontradas: {', '.join(results['not_found'][:10])}"
                + (" ..." if len(results["not_found"]) > 10 else ""),
            )

        return redirect("tolarian:collection-detail", pk=pk)


class CollectionItemEditView(LoginRequiredMixin, View):
    def post(self, request, item_pk):
        item = get_object_or_404(CollectionItem, pk=item_pk)
        if item.collection.user != request.user:
            raise PermissionDenied
        form = CollectionItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Item actualizado.")
        if request.headers.get("HX-Request"):
            return HttpResponse(status=204)
        return redirect("tolarian:collection-detail", pk=item.collection.pk)


class CollectionItemDeleteView(LoginRequiredMixin, View):
    def post(self, request, item_pk):
        item = get_object_or_404(CollectionItem, pk=item_pk)
        if item.collection.user != request.user:
            raise PermissionDenied
        collection_pk = item.collection.pk
        item.delete()
        messages.success(request, "Carta eliminada de la colección.")
        if request.headers.get("HX-Request"):
            return HttpResponse(status=204)
        return redirect("tolarian:collection-detail", pk=collection_pk)


class CollectionExportView(CollectionOwnerMixin, View):
    def get(self, request, pk):
        collection = get_object_or_404(Collection, pk=pk)
        content    = collection_to_csv(collection)
        response   = HttpResponse(content, content_type="text/csv")
        filename   = f"{collection.name.replace(' ', '_')}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class CollectionImportView(CollectionOwnerMixin, View):
    def get(self, request, pk):
        collection = get_object_or_404(Collection, pk=pk)
        form       = CollectionImportForm()
        return self._render(request, collection, form)

    def post(self, request, pk):
        collection = get_object_or_404(Collection, pk=pk)
        form       = CollectionImportForm(request.POST, request.FILES)
        if form.is_valid():
            results = parse_collection_csv(
                form.cleaned_data["file"],
                collection,
            )
            messages.success(
                request,
                f"Importación completa — {results['created']} cartas nuevas, "
                f"{results['updated']} actualizadas, {results['errors']} errores."
            )
            return redirect("tolarian:collection-detail", pk=pk)
        return self._render(request, collection, form)

    def _render(self, request, collection, form):
        from django.shortcuts import render
        return render(request, "tolarian/collection_import.html", {
            "collection": collection,
            "form":       form,
        })


# ---------------------------------------------------------------------------
# Decks
# ---------------------------------------------------------------------------
class DeckListView(LoginRequiredMixin, TemplateView):
    template_name = "tolarian/deck_list.html"

    def get_context_data(self, **kwargs):
        ctx   = super().get_context_data(**kwargs)
        decks = (
            Deck.objects
            .filter(user=self.request.user, is_active=True)
            .annotate(card_count=Sum("cards__quantity"))
            .order_by("-updated_at")
        )
        ctx.update({
            "decks":  decks,
            "format": self.request.GET.get("format", ""),
        })
        return ctx


class DeckDetailView(LoginRequiredMixin, TemplateView):
    template_name = "tolarian/deck_detail.html"

    def dispatch(self, request, *args, **kwargs):
        deck = get_object_or_404(Deck, pk=kwargs["pk"])
        if not deck.is_public and deck.user != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        deck = get_object_or_404(
            Deck.objects.prefetch_related(
                "cards__card__faces",
                "cards__print__cardset",
            ),
            pk=self.kwargs["pk"],
        )

        # Agrupar cartas por zona
        zones = {}
        for zone in DeckZone:
            entries = [c for c in deck.cards.all() if c.zone == zone.value]
            if entries:
                zones[zone] = entries

        ctx.update({
            "deck":      deck,
            "zones":     zones,
            "is_owner":  deck.user == self.request.user,
            "illegal":   deck.validate_format(),
            "curve":     deck.mana_curve,
        })
        return ctx


class DeckCreateView(LoginRequiredMixin, CreateView):
    model         = Deck
    form_class    = DeckForm
    template_name = "tolarian/deck_form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Deck creado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("tolarian:deck-detail", kwargs={"pk": self.object.pk})


class DeckEditView(DeckOwnerMixin, UpdateView):
    model         = Deck
    form_class    = DeckForm
    template_name = "tolarian/deck_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Deck actualizado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("tolarian:deck-detail", kwargs={"pk": self.object.pk})


class DeckDeleteView(DeckOwnerMixin, DeleteView):
    model         = Deck
    template_name = "tolarian/deck_confirm_delete.html"
    success_url   = reverse_lazy("tolarian:deck-list")

    def form_valid(self, form):
        messages.success(self.request, "Deck eliminado.")
        return super().form_valid(form)


class DeckAddCardView(DeckOwnerMixin, View):
    def post(self, request, pk):
        deck = get_object_or_404(Deck, pk=pk)
        form = DeckCardForm(request.POST)

        if form.is_valid():
            entry = form.save(commit=False)
            entry.deck = deck

            existing = DeckCard.objects.filter(
                deck=deck,
                card=entry.card,
                zone=entry.zone,
            ).first()

            if existing:
                existing.quantity += entry.quantity
                existing.save(update_fields=["quantity", "updated_at"])
                messages.success(request, f"Cantidad actualizada: {existing.card.name}")
            else:
                entry.save()
                messages.success(request, f"Carta agregada: {entry.card.name}")

        if request.headers.get("HX-Request"):
            return HttpResponse(status=204)
        return redirect("tolarian:deck-detail", pk=pk)


class DeckCardEditView(LoginRequiredMixin, View):
    def post(self, request, card_pk):
        entry = get_object_or_404(DeckCard, pk=card_pk)
        if entry.deck.user != request.user:
            raise PermissionDenied
        form = DeckCardForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, "Carta actualizada.")
        if request.headers.get("HX-Request"):
            return HttpResponse(status=204)
        return redirect("tolarian:deck-detail", pk=entry.deck.pk)


class DeckCardDeleteView(LoginRequiredMixin, View):
    def post(self, request, card_pk):
        entry   = get_object_or_404(DeckCard, pk=card_pk)
        if entry.deck.user != request.user:
            raise PermissionDenied
        deck_pk = entry.deck.pk
        entry.delete()
        messages.success(request, "Carta eliminada del deck.")
        if request.headers.get("HX-Request"):
            return HttpResponse(status=204)
        return redirect("tolarian:deck-detail", pk=deck_pk)


class DeckExportView(DeckOwnerMixin, View):
    def get(self, request, pk):
        deck     = get_object_or_404(Deck, pk=pk)
        fmt      = request.GET.get("format", "csv")

        if fmt == "txt":
            content  = self._to_text(deck)
            mimetype = "text/plain"
            ext      = "txt"
        else:
            content  = deck_to_csv(deck)
            mimetype = "text/csv"
            ext      = "csv"

        response  = HttpResponse(content, content_type=mimetype)
        filename  = f"{deck.name.replace(' ', '_')}.{ext}"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def _to_text(self, deck):
        """Exporta el deck en formato texto plano (1x Lightning Bolt)."""
        lines = []
        zone_order = [
            DeckZone.COMMANDER, DeckZone.COMPANION,
            DeckZone.MAIN, DeckZone.SIDEBOARD,
            DeckZone.MAYBEBOARD, DeckZone.RESERVE, DeckZone.EXTRAS,
        ]
        for zone in zone_order:
            entries = list(deck.cards.filter(zone=zone.value).select_related("card"))
            if not entries:
                continue
            lines.append(f"// {zone.label}")
            for e in entries:
                lines.append(f"{e.quantity} {e.card.name}")
            lines.append("")
        return "\n".join(lines)


class DeckImportView(DeckOwnerMixin, View):
    def get(self, request, pk):
        deck = get_object_or_404(Deck, pk=pk)
        form = DeckImportForm()
        return self._render(request, deck, form)

    def post(self, request, pk):
        deck = get_object_or_404(Deck, pk=pk)
        form = DeckImportForm(request.POST, request.FILES)
        if form.is_valid():
            source = form.cleaned_data.get("file") or form.cleaned_data.get("text")
            results = parse_decklist_text(source, deck)
            messages.success(
                request,
                f"Importación completa — {results['created']} cartas nuevas, "
                f"{results['not_found']} no encontradas."
            )
            return redirect("tolarian:deck-detail", pk=pk)
        return self._render(request, deck, form)

    def _render(self, request, deck, form):
        from django.shortcuts import render
        return render(request, "tolarian/deck_import.html", {
            "deck": deck,
            "form": form,
        })


class DeckValidateView(LoginRequiredMixin, View):
    def get(self, request, pk):
        deck    = get_object_or_404(Deck, pk=pk)
        if not deck.is_public and deck.user != request.user:
            raise PermissionDenied
        illegal = deck.validate_format()
        if request.headers.get("HX-Request"):
            from django.shortcuts import render
            return render(request, "tolarian/partials/deck_validation.html", {
                "deck":    deck,
                "illegal": illegal,
            })
        return redirect("tolarian:deck-detail", pk=pk)
    
    
# ---------------------------------------------------------------------------
# Parciales HTMX
# ---------------------------------------------------------------------------
class DeckCurvePartialView(LoginRequiredMixin, TemplateView):
    template_name = "tolarian/partials/mana_curve.html"

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs["pk"])
        if not deck.is_public and deck.user != self.request.user:
            raise PermissionDenied
        ctx.update({
            "deck":  deck,
            "curve": deck.mana_curve,
        })
        return ctx


class DeckStatsPartialView(LoginRequiredMixin, TemplateView):
    template_name = "tolarian/partials/deck_stats.html"

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs["pk"])
        if not deck.is_public and deck.user != self.request.user:
            raise PermissionDenied

        # Cartas en otros decks del mismo usuario
        shared = {}
        for entry in deck.cards.filter(
            zone__in=[DeckZone.MAIN, DeckZone.COMMANDER, DeckZone.COMPANION]
        ).select_related("card"):
            others = entry.is_in_other_decks()
            if others.exists():
                shared[entry.card.name] = [o.deck.name for o in others]

        ctx.update({
            "deck":        deck,
            "total_value": deck.total_value,
            "main_count":  deck.main_count,
            "side_count":  deck.sideboard_count,
            "shared":      shared,
        })
        return ctx


# ---------------------------------------------------------------------------
# API JSON — búsqueda de cartas
# ---------------------------------------------------------------------------
class CardSearchJSON(LoginRequiredMixin, View):
    """Return up to 10 cards matching a name query, with their prints."""

    def get(self, request):
        q = request.GET.get("q", "").strip()
        if len(q) < 2:
            return JsonResponse([], safe=False)

        cards = (
            Card.objects
            .filter(is_active=True, name__icontains=q)
            .prefetch_related("prints__cardset")
            .order_by("name")[:10]
        )

        results = []
        for card in cards:
            prints = [
                {
                    "id": str(p.pk),
                    "set_code": p.cardset.code if p.cardset else "",
                    "set_name": p.cardset.name if p.cardset else "",
                    "collector_number": p.collector_number,
                    "image": p.image_uris.get("small", ""),
                    "price_usd": p.prices.get("usd"),
                }
                for p in card.prints.all()[:20]
            ]
            results.append({
                "id": str(card.pk),
                "oracle_id": str(card.oracle_id),
                "name": card.name,
                "type_line": card.type_line,
                "prints": prints,
            })

        return JsonResponse(results, safe=False)