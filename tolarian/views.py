import csv
import io
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db import models
from django.db.models import Sum, Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    TemplateView, ListView, DetailView,
    CreateView, UpdateView, DeleteView, View,
)
from core.constants import CardCondition, CardFinish, MagicFormat
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
        type_order = [
            CollectionType.BINDER,
            CollectionType.LOANLIST,
            CollectionType.TRADELIST,
            CollectionType.WISHLIST,
        ]
        ordering = models.Case(
            *[models.When(collection_type=ct, then=i) for i, ct in enumerate(type_order)]
        )
        collections = (
            Collection.objects
            .filter(user=self.request.user, is_active=True)
            .annotate(
                item_count=Count("items"),
                total_qty=Sum("items__quantity"),
                type_order=ordering,
            )
            .select_related("cover_card__cardset", "cover_card__card")
            .order_by("type_order", "name")
        )
        ctx.update({
            "collections": collections,
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
            "is_loan":            collection.collection_type == CollectionType.LOANLIST,
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
        response = super().form_valid(form)

        bulk_text = self.request.POST.get("bulk_text", "").strip()
        if bulk_text:
            results = parse_collection_text(bulk_text, self.object)
            parts = []
            if results["created"]:
                parts.append(f"{results['created']} nueva(s)")
            if results["updated"]:
                parts.append(f"{results['updated']} actualizada(s)")
            if results["not_found"]:
                parts.append(f"{len(results['not_found'])} no encontrada(s)")
            messages.success(self.request, f"Colección creada — lote: {', '.join(parts)}.")
            if results["not_found"]:
                messages.warning(
                    self.request,
                    f"No encontradas: {', '.join(results['not_found'][:10])}"
                    + (" ..." if len(results["not_found"]) > 10 else ""),
                )
        else:
            messages.success(self.request, "Colección creada.")

        return response

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


class CollectionSetCoverView(CollectionOwnerMixin, View):
    """Set or clear the cover card for a collection via HTMX."""

    def post(self, request, pk):
        collection = get_object_or_404(Collection, pk=pk)
        print_id = request.POST.get("print_id", "").strip()

        if print_id:
            card_print = get_object_or_404(CardPrint, pk=print_id)
            collection.cover_card = card_print
        else:
            collection.cover_card = None
        collection.save(update_fields=["cover_card"])

        return render(
            request,
            "tolarian/partials/collection_card.html",
            {"collection": collection},
        )


class CollectionItemEditView(LoginRequiredMixin, View):
    def get(self, request, item_pk):
        item = get_object_or_404(
            CollectionItem.objects.select_related("card", "print__cardset", "collection")
                .prefetch_related("card__faces", "card__prints__cardset"),
            pk=item_pk,
        )
        if item.collection.user != request.user:
            raise PermissionDenied

        form   = CollectionItemForm(instance=item)
        prints = item.card.prints.select_related("cardset").order_by("-cardset__released_at")
        faces  = list(item.card.faces.order_by("face_index"))
        is_loan = item.collection.collection_type == CollectionType.LOANLIST

        # Other collections to move to (exclude current)
        move_targets = (
            Collection.objects
            .filter(user=request.user, is_active=True)
            .exclude(pk=item.collection.pk)
            .order_by("collection_type", "name")
        )
        # Block Wishlist ↔ Loan
        if item.collection.collection_type == CollectionType.WISHLIST:
            move_targets = move_targets.exclude(collection_type=CollectionType.LOANLIST)
        elif item.collection.collection_type == CollectionType.LOANLIST:
            move_targets = move_targets.exclude(collection_type=CollectionType.WISHLIST)

        return render(request, "tolarian/partials/collection_item_modal.html", {
            "item":         item,
            "form":         form,
            "prints":       prints,
            "faces":        faces,
            "is_loan":      is_loan,
            "move_targets": move_targets,
        })

    def post(self, request, item_pk):
        item = get_object_or_404(
            CollectionItem.objects.select_related("card", "print__cardset")
                .prefetch_related("card__faces", "card__prints__cardset"),
            pk=item_pk,
        )
        if item.collection.user != request.user:
            raise PermissionDenied
        form = CollectionItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Item actualizado.")
            if request.headers.get("HX-Request"):
                return HttpResponse(status=204)
            return redirect("tolarian:collection-detail", pk=item.collection.pk)

        # Validation failed — re-render modal with errors
        prints = item.card.prints.select_related("cardset").order_by("-cardset__released_at")
        faces  = list(item.card.faces.order_by("face_index"))
        return render(request, "tolarian/partials/collection_item_modal.html", {
            "item":   item,
            "form":   form,
            "prints": prints,
            "faces":  faces,
        })


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


class CollectionItemMoveView(LoginRequiredMixin, View):
    """Move a collection item to a different collection of the same user."""

    def post(self, request, item_pk):
        item = get_object_or_404(
            CollectionItem.objects.select_related("collection"),
            pk=item_pk,
        )
        if item.collection.user != request.user:
            raise PermissionDenied

        target_pk = request.POST.get("target_collection", "")
        target = get_object_or_404(Collection, pk=target_pk, user=request.user)

        # Block Wishlist ↔ Loan
        src_type = item.collection.collection_type
        dst_type = target.collection_type
        if ((src_type == CollectionType.WISHLIST and dst_type == CollectionType.LOANLIST)
                or (src_type == CollectionType.LOANLIST and dst_type == CollectionType.WISHLIST)):
            messages.error(request, "No se puede mover entre Wishlist y Loan List.")
            if request.headers.get("HX-Request"):
                return HttpResponse(status=422)
            return redirect("tolarian:collection-detail", pk=item.collection.pk)

        try:
            move_qty = int(request.POST.get("move_quantity", item.quantity))
        except (ValueError, TypeError):
            move_qty = item.quantity
        move_qty = max(1, min(move_qty, item.quantity))

        source_pk = item.collection.pk

        # Check if the same item already exists in target
        existing = CollectionItem.objects.filter(
            collection=target,
            card=item.card,
            print=item.print,
            condition=item.condition,
            finish=item.finish,
            language=item.language,
        ).first()

        if move_qty >= item.quantity:
            # Move the entire item
            if existing:
                existing.quantity += item.quantity
                existing.save(update_fields=["quantity", "updated_at"])
                item.delete()
            else:
                item.collection = target
                item.save(update_fields=["collection"])
        else:
            # Partial move: reduce source, add to target
            item.quantity -= move_qty
            item.save(update_fields=["quantity", "updated_at"])
            if existing:
                existing.quantity += move_qty
                existing.save(update_fields=["quantity", "updated_at"])
            else:
                CollectionItem.objects.create(
                    collection=target,
                    card=item.card,
                    print=item.print,
                    quantity=move_qty,
                    condition=item.condition,
                    finish=item.finish,
                    language=item.language,
                    purchase_price=item.purchase_price,
                    loan_to_user=item.loan_to_user,
                    loan_to_name=item.loan_to_name,
                    notes=item.notes,
                )

        messages.success(request, f"{move_qty}x {item.card.name} movida(s) a {target.name}.")
        if request.headers.get("HX-Request"):
            return HttpResponse(status=204)
        return redirect("tolarian:collection-detail", pk=source_pk)


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

    @staticmethod
    def _card_category(type_line):
        """Classify a card into an Archidekt-style category by type_line."""
        tl = type_line.lower()
        if "land" in tl:
            return "Lands"
        if "creature" in tl:
            return "Creatures"
        if "planeswalker" in tl:
            return "Planeswalkers"
        if "instant" in tl:
            return "Instants"
        if "sorcery" in tl:
            return "Sorceries"
        if "enchantment" in tl:
            return "Enchantments"
        if "artifact" in tl:
            return "Artifacts"
        if "battle" in tl:
            return "Battles"
        return "Other"

    CATEGORY_ORDER = [
        "Creatures", "Planeswalkers", "Instants", "Sorceries",
        "Enchantments", "Artifacts", "Battles", "Lands", "Other",
    ]

    COLOR_MAP = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}

    @staticmethod
    def _entry_price(entry):
        """Get USD price for a deck entry from its print."""
        p = entry.print or entry.card.primary_print
        if p and p.price_usd:
            return float(p.price_usd)
        return 0.0

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        deck = get_object_or_404(
            Deck.objects.prefetch_related(
                "cards__card__faces",
                "cards__print__cardset",
            ),
            pk=self.kwargs["pk"],
        )

        all_entries = list(deck.cards.all())
        counted_zones = {DeckZone.MAYBEBOARD, DeckZone.RESERVE, DeckZone.EXTRAS}

        # Agrupar cartas por zona, y dentro del main por categoría
        zones = {}
        total_cards = 0
        type_breakdown = {}   # {category_name: qty}
        color_counts = {}     # {color_code: qty}

        for zone in DeckZone:
            entries = [c for c in all_entries if c.zone == zone.value]
            if not entries:
                continue

            if zone == DeckZone.MAIN:
                categories = {}
                for entry in entries:
                    cat = self._card_category(entry.card.type_line)
                    categories.setdefault(cat, []).append(entry)
                ordered = {}
                for cat in self.CATEGORY_ORDER:
                    if cat in categories:
                        cat_entries = sorted(categories[cat], key=lambda e: e.card.name)
                        cat_qty = sum(e.quantity for e in cat_entries)
                        cat_price = sum(
                            self._entry_price(e) * e.quantity
                            for e in cat_entries
                        )
                        ordered[cat] = {
                            "entries": cat_entries,
                            "qty": cat_qty,
                            "price": round(cat_price, 2),
                        }
                        type_breakdown[cat] = cat_qty
                zones[zone] = {"categories": ordered}
            else:
                zone_price = sum(
                    self._entry_price(e) * e.quantity for e in entries
                )
                zones[zone] = {
                    "entries": sorted(entries, key=lambda e: e.card.name),
                    "qty": sum(e.quantity for e in entries),
                    "price": round(zone_price, 2),
                }

            # Accumulate stats for deck-counted zones
            if zone.value not in {z.value for z in counted_zones}:
                for entry in entries:
                    total_cards += entry.quantity
                    for c in (entry.card.color_identity or []):
                        color_counts[c] = color_counts.get(c, 0) + entry.quantity

        has_commander = any(
            c.zone == DeckZone.COMMANDER for c in all_entries
        )

        # Color distribution with labels
        color_dist = []
        for code in ["W", "U", "B", "R", "G"]:
            if code in color_counts:
                color_dist.append({
                    "code": code,
                    "name": self.COLOR_MAP[code],
                    "count": color_counts[code],
                })
        colorless = sum(
            e.quantity for e in all_entries
            if e.zone not in {z.value for z in counted_zones}
            and not e.card.color_identity
        )
        if colorless:
            color_dist.append({"code": "C", "name": "Colorless", "count": colorless})

        # Shared cards (in other user decks)
        shared = {}
        for entry in all_entries:
            if entry.zone in (DeckZone.MAIN, DeckZone.COMMANDER, DeckZone.COMPANION):
                others = entry.is_in_other_decks()
                if others.exists():
                    shared[entry.card.name] = [o.deck.name for o in others]

        # Flat list for grid/table/stacks views (excluding maybeboard)
        deck_entries = sorted(all_entries, key=lambda e: (e.zone, e.card.name))

        ctx.update({
            "deck":           deck,
            "zones":          zones,
            "deck_entries":   deck_entries,
            "is_owner":       deck.user == self.request.user,
            "illegal":        deck.validate_format(),
            "curve":          deck.mana_curve,
            "curve_max":      max(deck.mana_curve.values()) if deck.mana_curve else 0,
            "has_commander":  has_commander,
            "total_cards":    total_cards,
            "main_count":     deck.main_count,
            "side_count":     deck.sideboard_count,
            "total_value":    deck.total_value,
            "type_breakdown": type_breakdown,
            "color_dist":     color_dist,
            "shared":         shared,
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

    SINGLETON_FORMATS = {
        MagicFormat.COMMANDER, MagicFormat.BRAWL, MagicFormat.OATHBREAKER,
    }
    CONSTRUCTED_FORMATS = {
        MagicFormat.STANDARD, MagicFormat.PIONEER, MagicFormat.MODERN,
        MagicFormat.LEGACY, MagicFormat.VINTAGE, MagicFormat.PAUPER,
    }

    def _max_copies(self, card, deck_format):
        """Return the max allowed copies for a card in a given format.
        Returns None for unlimited (basic lands, 'any number' cards)."""
        # Cards explicitly marked unlimited (basic lands, relentless rats, etc.)
        if card.has_deck_limit and card.max_deck_copies == 0:
            return None
        # Cards with a specific limit (e.g. Seven Dwarves = 7)
        if card.has_deck_limit and card.max_deck_copies:
            return card.max_deck_copies
        # Singleton formats: 1 copy
        if deck_format in self.SINGLETON_FORMATS:
            return 1
        # Constructed formats: 4 copies
        if deck_format in self.CONSTRUCTED_FORMATS:
            return 4
        # Limited / Other: no limit
        return None

    def post(self, request, pk):
        deck = get_object_or_404(Deck, pk=pk)
        form = DeckCardForm(request.POST)

        if not form.is_valid():
            msg = "Error en el formulario."
            if request.headers.get("HX-Request") or request.content_type == "multipart/form-data":
                return JsonResponse({"error": msg}, status=400)
            messages.error(request, msg)
            return redirect("tolarian:deck-detail", pk=pk)

        entry = form.save(commit=False)
        entry.deck = deck
        card = entry.card

        # Total copies already in this deck (across all zones)
        current_qty = (
            DeckCard.objects.filter(deck=deck, card=card)
            .aggregate(total=Sum("quantity"))["total"] or 0
        )
        max_copies = self._max_copies(card, deck.format)

        if max_copies is not None and current_qty + entry.quantity > max_copies:
            allowed = max(0, max_copies - current_qty)
            if allowed == 0:
                msg = (
                    f"Ya tienes {current_qty} copia(s) de {card.name}. "
                    f"Máximo permitido en {deck.get_format_display()}: {max_copies}."
                )
            else:
                msg = (
                    f"Solo puedes agregar {allowed} copia(s) más de {card.name} "
                    f"(máximo {max_copies} en {deck.get_format_display()})."
                )
            if request.headers.get("HX-Request") or request.content_type == "multipart/form-data":
                return JsonResponse({"error": msg}, status=400)
            messages.error(request, msg)
            return redirect("tolarian:deck-detail", pk=pk)

        # Check existing entry in same zone + print
        existing = DeckCard.objects.filter(
            deck=deck, card=card, zone=entry.zone, print=entry.print,
        ).first()

        if existing:
            existing.quantity += entry.quantity
            existing.save(update_fields=["quantity", "updated_at"])
            messages.success(request, f"Cantidad actualizada: {existing.card.name}")
        else:
            entry.save()
            messages.success(request, f"Carta agregada: {entry.card.name}")

        if request.headers.get("HX-Request") or request.content_type == "multipart/form-data":
            return HttpResponse(status=204)
        return redirect("tolarian:deck-detail", pk=pk)


class DeckCardEditView(LoginRequiredMixin, View):
    def get(self, request, card_pk):
        entry = get_object_or_404(
            DeckCard.objects.select_related(
                "card", "print__cardset", "deck",
            ).prefetch_related("card__prints__cardset"),
            pk=card_pk,
        )
        if entry.deck.user != request.user:
            raise PermissionDenied

        form = DeckCardForm(instance=entry)
        prints = entry.card.prints.select_related("cardset").order_by(
            "-cardset__released_at"
        )

        # Check if user owns this card in any collection
        owned_qty = (
            CollectionItem.objects
            .filter(
                collection__user=request.user,
                card=entry.card,
                collection__is_active=True,
            )
            .aggregate(total=Sum("quantity"))["total"] or 0
        )

        # Other decks using this card
        other_decks = (
            DeckCard.objects
            .filter(card=entry.card, deck__user=request.user, deck__is_active=True)
            .exclude(deck=entry.deck)
            .select_related("deck")
            .values_list("deck__name", flat=True)
            .distinct()
        )

        return render(request, "tolarian/partials/deck_card_modal.html", {
            "entry":       entry,
            "deck":        entry.deck,
            "form":        form,
            "prints":      prints,
            "owned_qty":   owned_qty,
            "other_decks": list(other_decks),
            "is_owner":    entry.deck.user == request.user,
        })

    def post(self, request, card_pk):
        entry = get_object_or_404(DeckCard, pk=card_pk)
        if entry.deck.user != request.user:
            raise PermissionDenied
        form = DeckCardForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, "Carta actualizada.")
        if request.headers.get("HX-Request"):
            return HttpResponse(status=204,
                                headers={"HX-Trigger": "deck-card-updated"})
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
        curve = deck.mana_curve
        ctx.update({
            "deck":      deck,
            "curve":     curve,
            "curve_max": max(curve.values()) if curve else 0,
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
                "can_be_commander": card.can_be_commander,
                "prints": prints,
            })

        return JsonResponse(results, safe=False)