import csv
import io
import secrets
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
from core.constants import CardCondition, CardFinish, MagicFormat, CardRarity, MagicColor
from core.mixins import OwnerRequiredMixin
from core.utils import paginate_queryset
from django.db.models import FloatField
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from multiverse.models import Card, CardPrint
from .mixins import CollectionOwnerMixin, DeckOwnerMixin
from .models import (
    Collection, CollectionItem, CollectionType,
    Deck, DeckCard, DeckCategory, DeckVersion, DeckZone,
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

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            if self.request.GET.get("page"):
                return ["tolarian/partials/collection_grid_items.html"]
            return ["tolarian/partials/collection_results.html"]
        return [self.template_name]

    SORT_CHOICES = [
        ("name_asc",   "Nombre A-Z"),
        ("name_desc",  "Nombre Z-A"),
        ("price_desc", "Precio ↓"),
        ("price_asc",  "Precio ↑"),
        ("qty_desc",   "Cantidad ↓"),
        ("recent",     "Más recientes"),
        ("cmc_asc",    "CMC ↑"),
        ("cmc_desc",   "CMC ↓"),
        ("rarity",     "Rareza"),
        ("set",        "Set"),
    ]
    SORT_ORDERINGS = {
        "name_asc":           ["card__name"],
        "name_desc":          ["-card__name"],
        "price_desc":         ["-_price_usd", "card__name"],
        "price_asc":          ["_price_usd", "card__name"],
        "qty_desc":           ["-quantity", "card__name"],
        "qty_asc":            ["quantity", "card__name"],
        "recent":             ["-created_at"],
        "cmc_asc":            ["card__cmc", "card__name"],
        "cmc_desc":           ["-card__cmc", "card__name"],
        "rarity":             ["print__rarity", "card__name"],
        "set":                ["print__cardset__code", "card__name"],
        "set_desc":           ["-print__cardset__code", "card__name"],
        "condition_asc":      ["condition", "card__name"],
        "condition_desc":     ["-condition", "card__name"],
        "finish_asc":         ["finish", "card__name"],
        "finish_desc":        ["-finish", "card__name"],
        "lang_asc":           ["language", "card__name"],
        "lang_desc":          ["-language", "card__name"],
        "purchase_asc":       ["purchase_price", "card__name"],
        "purchase_desc":      ["-purchase_price", "card__name"],
    }

    def get_context_data(self, **kwargs):
        from urllib.parse import urlencode
        ctx        = super().get_context_data(**kwargs)
        collection = get_object_or_404(Collection, pk=self.kwargs["pk"])
        items      = (
            collection.items
            .select_related("card", "print__cardset")
            .prefetch_related("card__faces")
        )

        q         = self.request.GET.get("q", "")
        sort      = self.request.GET.get("sort", "name_asc")
        if sort not in self.SORT_ORDERINGS:
            sort = "name_asc"
        rarity    = self.request.GET.get("rarity", "")
        color     = self.request.GET.get("color", "")
        finish    = self.request.GET.get("finish", "")
        condition = self.request.GET.get("condition", "")

        if q:
            items = items.filter(card__name__icontains=q)
        if rarity:
            items = items.filter(print__rarity=rarity)
        if color:
            if color == "C":
                items = items.filter(card__color_identity=[])
            else:
                items = items.filter(card__color_identity__contains=[color])
        if finish:
            items = items.filter(finish=finish)
        if condition:
            items = items.filter(condition=condition)

        # Annotate price (from JSON) for price-based sorting
        items = items.annotate(
            _price_usd=Cast(KeyTextTransform("usd", "print__prices"), FloatField())
        )
        items = items.order_by(*self.SORT_ORDERINGS[sort])

        # Querystring to preserve filters across infinite-scroll pagination
        params = self.request.GET.copy()
        params.pop("page", None)
        extra_qs = params.urlencode()

        # Querystring for sortable column headers (without sort / page)
        header_params = self.request.GET.copy()
        header_params.pop("page", None)
        header_params.pop("sort", None)
        header_qs = header_params.urlencode()

        ctx.update({
            "collection":         collection,
            "page_obj":           paginate_queryset(items, self.request.GET.get("page"), per_page=40),
            "is_owner":           collection.user == self.request.user,
            "is_loan":            collection.collection_type == CollectionType.LOANLIST,
            "collection_add_url": reverse("tolarian:collection-add-card", kwargs={"pk": collection.pk}),
            "collection_bulk_add_url": reverse("tolarian:collection-bulk-add", kwargs={"pk": collection.pk}),
            "condition_choices":  CardCondition.choices,
            "finish_choices":     CardFinish.choices,
            "rarity_choices":     CardRarity.choices,
            "color_choices":      MagicColor.choices,
            "sort_choices":       self.SORT_CHOICES,
            "q":                  q,
            "sort":               sort,
            "rarity":             rarity,
            "color":              color,
            "finish":             finish,
            "condition":          condition,
            "extra_qs":           extra_qs,
            "header_qs":          header_qs,
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
        ctx = super().get_context_data(**kwargs)
        decks = (
            Deck.objects
            .filter(user=self.request.user, is_active=True)
            .annotate(card_count=Sum("cards__quantity", filter=~models.Q(cards__zone=DeckZone.EXTRAS)))
            .select_related("cover_card__cardset", "cover_card__card")
            .order_by("-updated_at")
        )

        # Distinct formats for filter pills
        format_values = decks.values_list("format", flat=True).distinct()
        formats = [
            (f, dict(MagicFormat.choices).get(f, f))
            for f in sorted(format_values) if f
        ]

        # Apply format filter
        selected_format = self.request.GET.get("format", "")
        if selected_format:
            decks = decks.filter(format=selected_format)

        ctx.update({
            "decks": decks,
            "format": selected_format,
            "formats": formats,
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
            if "basic" in tl:
                return "Basic Lands"
            return "Non-Basic Lands"
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
        "Enchantments", "Artifacts", "Battles", "Non-Basic Lands",
        "Basic Lands", "Other",
    ]

    COLOR_MAP = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}

    GROUPING_MODES = [
        ("type",         "Tipos"),
        ("category",     "Categorias"),
        ("cmc",          "Mana Value"),
        ("price",        "Precio"),
        ("rarity",       "Rareza"),
        ("color",        "Color"),
        ("identity",     "Identidad"),
        ("game_changer", "Game Changer"),
    ]

    RARITY_ORDER = ["mythic", "rare", "uncommon", "common", "special", "bonus"]
    RARITY_LABELS = {
        "mythic": "Mythic", "rare": "Rare", "uncommon": "Uncommon",
        "common": "Common", "special": "Special", "bonus": "Bonus",
    }

    PRICE_BUCKETS = [
        ("$0 – $0.49",   0,    0.50),
        ("$0.50 – $1",   0.50, 1.01),
        ("$1 – $5",      1.01, 5.01),
        ("$5 – $10",     5.01, 10.01),
        ("$10 – $25",    10.01, 25.01),
        ("$25+",         25.01, 999999),
    ]

    @staticmethod
    def _entry_price(entry):
        """Get USD price for a deck entry from its print."""
        p = entry.print or entry.card.primary_print
        if p and p.price_usd:
            return float(p.price_usd)
        return 0.0

    # --- Grouping helpers (each returns OrderedDict-style {label: [entries]}) ---

    def _group_by_type(self, entries):
        categories = {}
        for entry in entries:
            cat = self._card_category(entry.card.type_line)
            categories.setdefault(cat, []).append(entry)
        ordered = {}
        for cat in self.CATEGORY_ORDER:
            if cat in categories:
                ordered[cat] = sorted(categories[cat], key=lambda e: e.card.name)
        return ordered

    def _group_by_custom_category(self, entries, deck):
        """Group by user-defined DeckCategory. A card with multiple categories
        appears in each. Uncategorized cards go last.
        Returns {name: entries} and also builds self._category_pk_map.
        Always includes all categories (even empty) as drag-drop targets."""
        cats = list(deck.deck_categories.all())
        self._category_pk_map = {c.name: str(c.pk) for c in cats}
        groups = {c.name: [] for c in cats}
        groups["Sin categoria"] = []
        for entry in entries:
            entry_cats = list(entry.categories.all())
            if entry_cats:
                for cat in entry_cats:
                    groups.setdefault(cat.name, []).append(entry)
            else:
                groups["Sin categoria"].append(entry)
        # Always include ALL categories (even empty) so they're valid drop targets
        ordered = {}
        for c in cats:
            ordered[c.name] = sorted(groups.get(c.name, []), key=lambda e: e.card.name)
        # Uncategorized at the end — only if it has cards
        if groups.get("Sin categoria"):
            ordered["Sin categoria"] = sorted(groups["Sin categoria"], key=lambda e: e.card.name)
        return ordered

    def _group_by_cmc(self, entries):
        groups = {}
        for entry in entries:
            tl = entry.card.type_line.lower()
            if "land" in tl:
                label = "Lands"
            else:
                cmc = int(entry.card.cmc or 0)
                label = f"MV {cmc}"
            groups.setdefault(label, []).append(entry)
        # Sort: numeric CMC groups first, then Lands
        def sort_key(item):
            label = item[0]
            if label == "Lands":
                return (1, 0)
            return (0, int(label.split()[1]))
        return {k: sorted(v, key=lambda e: e.card.name)
                for k, v in sorted(groups.items(), key=sort_key)}

    def _group_by_price(self, entries):
        groups = {}
        for entry in entries:
            price = entry.display_price
            bucket = "$0 – $0.49"
            for label, lo, hi in self.PRICE_BUCKETS:
                if lo <= price < hi:
                    bucket = label
                    break
            groups.setdefault(bucket, []).append(entry)
        # Order by bucket order
        ordered = {}
        for label, _, _ in self.PRICE_BUCKETS:
            if label in groups:
                ordered[label] = sorted(groups[label], key=lambda e: e.card.name)
        return ordered

    def _group_by_rarity(self, entries):
        groups = {}
        for entry in entries:
            r = (entry.display_rarity or "common").lower()
            label = self.RARITY_LABELS.get(r, r.title())
            groups.setdefault(label, []).append(entry)
        ordered = {}
        for r in self.RARITY_ORDER:
            label = self.RARITY_LABELS.get(r, r.title())
            if label in groups:
                ordered[label] = sorted(groups[label], key=lambda e: e.card.name)
        return ordered

    def _group_by_color(self, entries):
        color_labels = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}
        order = ["W", "U", "B", "R", "G"]
        groups = {}
        for entry in entries:
            colors = entry.card.colors or []
            if not colors:
                key = "Colorless"
            elif len(colors) > 1:
                key = "Multicolor"
            else:
                key = color_labels.get(colors[0], colors[0])
            groups.setdefault(key, []).append(entry)
        ordered = {}
        for c in order:
            label = color_labels[c]
            if label in groups:
                ordered[label] = sorted(groups[label], key=lambda e: e.card.name)
        if "Multicolor" in groups:
            ordered["Multicolor"] = sorted(groups["Multicolor"], key=lambda e: e.card.name)
        if "Colorless" in groups:
            ordered["Colorless"] = sorted(groups["Colorless"], key=lambda e: e.card.name)
        return ordered

    def _group_by_identity(self, entries):
        color_labels = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}
        order = ["W", "U", "B", "R", "G"]
        groups = {}
        for entry in entries:
            ci = entry.card.color_identity or []
            if not ci:
                key = "Colorless"
            elif len(ci) > 1:
                key = "Multicolor"
            else:
                key = color_labels.get(ci[0], ci[0])
            groups.setdefault(key, []).append(entry)
        ordered = {}
        for c in order:
            label = color_labels[c]
            if label in groups:
                ordered[label] = sorted(groups[label], key=lambda e: e.card.name)
        if "Multicolor" in groups:
            ordered["Multicolor"] = sorted(groups["Multicolor"], key=lambda e: e.card.name)
        if "Colorless" in groups:
            ordered["Colorless"] = sorted(groups["Colorless"], key=lambda e: e.card.name)
        return ordered

    def _group_by_game_changer(self, entries):
        gc = [e for e in entries if e.is_game_changer]
        rest = [e for e in entries if not e.is_game_changer]
        ordered = {}
        if gc:
            ordered["Game Changers"] = sorted(gc, key=lambda e: e.card.name)
        if rest:
            ordered["Other"] = sorted(rest, key=lambda e: e.card.name)
        return ordered

    def _build_categories(self, group_by, entries, deck):
        """Route to the right grouping helper."""
        if group_by == "category":
            return self._group_by_custom_category(entries, deck)
        if group_by == "cmc":
            return self._group_by_cmc(entries)
        if group_by == "price":
            return self._group_by_price(entries)
        if group_by == "rarity":
            return self._group_by_rarity(entries)
        if group_by == "color":
            return self._group_by_color(entries)
        if group_by == "identity":
            return self._group_by_identity(entries)
        if group_by == "game_changer":
            return self._group_by_game_changer(entries)
        return self._group_by_type(entries)

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        deck = get_object_or_404(
            Deck.objects.prefetch_related(
                "cards__card__faces",
                "cards__print__cardset",
                "cards__categories",
                "deck_categories",
            ),
            pk=self.kwargs["pk"],
        )

        group_by = self.request.GET.get("group", "type")
        if group_by not in dict(self.GROUPING_MODES):
            group_by = "type"

        # Ensure custom categories exist for owner
        is_owner = deck.user == self.request.user
        if is_owner:
            DeckCategory.ensure_defaults(deck)

        all_entries = list(deck.cards.all())
        counted_zones = {DeckZone.MAYBEBOARD, DeckZone.RESERVE, DeckZone.EXTRAS}

        # Annotate each entry with display-friendly price / set / flip data
        for entry in all_entries:
            p = entry.print or entry.card.primary_print
            entry.display_price = float(p.price_usd) if p and p.price_usd else 0.0
            entry.display_set = p.cardset.code.upper() if p and p.cardset else ""
            entry.display_rarity = p.rarity if p else ""
            entry.display_scryfall_id = str(p.scryfall_id) if p and p.scryfall_id else ""
            entry.has_back_face = len(list(entry.card.faces.all())) > 1

        # Build grouped zones — Commander first, then Main, then the rest
        zones = {}
        total_cards = 0
        type_breakdown = {}
        color_counts = {}
        category_nav = []

        zone_order = [DeckZone.COMMANDER, DeckZone.COMPANION] + [
            z for z in DeckZone
            if z not in (DeckZone.COMMANDER, DeckZone.COMPANION)
        ]
        for zone in zone_order:
            entries = [c for c in all_entries if c.zone == zone.value]
            if not entries:
                continue

            if zone == DeckZone.MAIN:
                self._category_pk_map = {}
                raw_groups = self._build_categories(group_by, entries, deck)
                pk_map = self._category_pk_map  # populated by _group_by_custom_category
                ordered = {}
                for cat_name, cat_entries in raw_groups.items():
                    cat_qty = sum(e.quantity for e in cat_entries)
                    cat_price = sum(e.display_price * e.quantity for e in cat_entries)
                    ordered[cat_name] = {
                        "entries": cat_entries,
                        "qty": cat_qty,
                        "price": round(cat_price, 2),
                        "category_pk": pk_map.get(cat_name, ""),
                    }
                    category_nav.append({
                        "name": cat_name,
                        "qty": cat_qty,
                        "slug": cat_name.lower().replace(" ", "-").replace("+", "plus"),
                    })
                # type_breakdown always uses card type for stats sidebar
                type_groups = self._group_by_type(entries)
                for cat_name, cat_entries in type_groups.items():
                    type_breakdown[cat_name] = sum(e.quantity for e in cat_entries)
                zones[zone] = {"categories": ordered}
            else:
                zone_price = sum(e.display_price * e.quantity for e in entries)
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

        # Keep commander entries accessible for sidebar nav and special rendering
        commander_entries = []
        commander_qty = 0
        commander_price = 0
        if DeckZone.COMMANDER in zones:
            cmd_data = zones[DeckZone.COMMANDER]
            commander_entries = cmd_data.get("entries", [])
            commander_qty = cmd_data.get("qty", 0)
            commander_price = cmd_data.get("price", 0)

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

        # Flat list for grid/table/stacks views
        deck_entries = sorted(all_entries, key=lambda e: (e.zone, e.card.name))

        # Deck categories for the template (for category mode management)
        deck_categories = list(deck.deck_categories.all())

        ctx.update({
            "deck":            deck,
            "zones":           zones,
            "deck_entries":    deck_entries,
            "is_owner":        is_owner,
            "illegal":         deck.validate_format(),
            "curve":           deck.mana_curve,
            "curve_max":       max(deck.mana_curve.values()) if deck.mana_curve else 0,
            "has_commander":      has_commander,
            "commander_entries":  commander_entries,
            "commander_qty":     commander_qty,
            "commander_price":   commander_price,
            "total_cards":     total_cards,
            "main_count":      deck.main_count,
            "side_count":      deck.sideboard_count,
            "total_value":     deck.total_value,
            "type_breakdown":  type_breakdown,
            "color_dist":      color_dist,
            "shared":          shared,
            "category_nav":    category_nav,
            "group_by":        group_by,
            "grouping_modes":  self.GROUPING_MODES,
            "deck_categories": deck_categories,
        })

        # Game stats for this deck (from phyrexian)
        from phyrexian.models import GameRecord, GameResult
        deck_games = GameRecord.objects.filter(
            user=deck.user, deck=deck, is_active=True
        )
        deck_game_count = deck_games.count()
        if deck_game_count:
            deck_wins = deck_games.filter(result=GameResult.WIN).count()
            ctx["deck_game_count"] = deck_game_count
            ctx["deck_wins"] = deck_wins
            ctx["deck_losses"] = deck_games.filter(result=GameResult.LOSS).count()
            ctx["deck_draws"] = deck_games.filter(result=GameResult.DRAW).count()
            ctx["deck_win_rate"] = round(deck_wins / deck_game_count * 100, 1)

            # ── Win rate trend over time (monthly) ──
            import json as _json
            from django.db import models as _models
            from django.db.models.functions import TruncMonth

            monthly = (
                deck_games
                .annotate(period=TruncMonth("date_played"))
                .values("period")
                .annotate(
                    total=_models.Count("id"),
                    wins=_models.Count("id", filter=_models.Q(result=GameResult.WIN)),
                    losses=_models.Count("id", filter=_models.Q(result=GameResult.LOSS)),
                    draws=_models.Count("id", filter=_models.Q(result=GameResult.DRAW)),
                )
                .order_by("period")
            )
            labels = []
            win_rate_series = []
            rolling_series = []
            game_count_series = []
            cum_wins = 0
            cum_total = 0
            for entry in monthly:
                labels.append(entry["period"].strftime("%Y-%m"))
                wr = (entry["wins"] / entry["total"] * 100) if entry["total"] else 0
                win_rate_series.append(round(wr, 1))
                game_count_series.append(entry["total"])
                cum_wins += entry["wins"]
                cum_total += entry["total"]
                rolling_series.append(round(cum_wins / cum_total * 100, 1))

            ctx["deck_trend_chart_json"] = _json.dumps({
                "labels": labels,
                "monthly_win_rate": win_rate_series,
                "cumulative_win_rate": rolling_series,
                "game_counts": game_count_series,
            })
            ctx["deck_trend_has_data"] = len(labels) > 1

            # Recent games (latest 10)
            ctx["deck_recent_games"] = list(
                deck_games.order_by("-date_played", "-created_at")[:10]
            )

        return ctx


class DeckContentPartialView(DeckDetailView):
    """HTMX partial: returns card area + OOB updates for sidebar/stats/header."""
    template_name = "tolarian/partials/deck_content_refresh.html"


class DeckCreateView(LoginRequiredMixin, CreateView):
    model         = Deck
    form_class    = DeckForm
    template_name = "tolarian/deck_form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        DeckCategory.ensure_defaults(self.object)
        messages.success(self.request, "Deck creado.")
        return response

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


class DeckSetCoverView(DeckOwnerMixin, View):
    """Set or clear the cover card for a deck via HTMX."""

    def post(self, request, pk):
        deck = get_object_or_404(Deck, pk=pk)
        print_id = request.POST.get("print_id", "").strip()

        if print_id:
            card_print = get_object_or_404(CardPrint, pk=print_id)
            deck.cover_card = card_print
        else:
            deck.cover_card = None
        deck.save(update_fields=["cover_card"])

        return render(
            request,
            "tolarian/partials/deck_card.html",
            {"deck": deck},
        )


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
            ).prefetch_related("card__prints__cardset", "card__faces", "categories"),
            pk=card_pk,
        )
        is_owner = entry.deck.user == request.user
        if not is_owner and not entry.deck.is_public:
            raise PermissionDenied

        form = DeckCardForm(instance=entry) if is_owner else None
        prints = entry.card.prints.select_related("cardset").order_by(
            "-cardset__released_at"
        )

        # Active print price info
        active_print = entry.print or entry.card.primary_print
        price_usd = float(active_print.price_usd) if active_print and active_print.price_usd else None
        price_foil = float(active_print.price_usd_foil) if active_print and hasattr(active_print, "price_usd_foil") and active_print.price_usd_foil else None
        rarity = active_print.rarity if active_print else None

        # Collection records for this card (owned copies)
        owned_qty = 0
        collection_records = []
        if request.user.is_authenticated:
            col_items = (
                CollectionItem.objects
                .filter(
                    collection__user=request.user,
                    card=entry.card,
                    collection__is_active=True,
                )
                .select_related("collection", "print__cardset")
            )
            for item in col_items:
                owned_qty += item.quantity
                collection_records.append(item)

        # Other decks using this card (with zone info)
        other_deck_entries = (
            DeckCard.objects
            .filter(card=entry.card, deck__user=request.user, deck__is_active=True)
            .exclude(deck=entry.deck)
            .select_related("deck")
        )
        other_decks_info = []
        for de in other_deck_entries:
            other_decks_info.append({
                "deck_name": de.deck.name,
                "deck_pk": str(de.deck.pk),
                "zone": de.get_zone_display(),
                "qty": de.quantity,
            })

        # Categories assigned to this card + all deck categories
        deck_categories = list(entry.deck.deck_categories.all())
        entry_categories = list(entry.categories.all())

        # Card oracle text / faces for Card info tab
        card = entry.card
        faces = list(card.faces.all()) if card.faces.exists() else []

        # Rulings
        rulings = []
        if hasattr(card, 'rulings'):
            rulings = list(card.rulings.all().order_by('-published_at')[:20])

        return render(request, "tolarian/partials/deck_card_modal.html", {
            "entry":              entry,
            "deck":               entry.deck,
            "form":               form,
            "prints":             prints,
            "price_usd":          price_usd,
            "price_foil":         price_foil,
            "rarity":             rarity,
            "owned_qty":          owned_qty,
            "collection_records": collection_records,
            "other_decks_info":   other_decks_info,
            "is_owner":           is_owner,
            "deck_categories":    deck_categories,
            "entry_categories":   entry_categories,
            "card":               card,
            "faces":              faces,
            "rulings":            rulings,
            "zone_choices":       DeckZone.choices,
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


class DeckCardQtyView(LoginRequiredMixin, View):
    """POST: increment or decrement a deck card's quantity.
    Send delta=1 or delta=-1.  If qty reaches 0, the card is removed."""

    def post(self, request, card_pk):
        entry = get_object_or_404(DeckCard, pk=card_pk)
        if entry.deck.user != request.user:
            raise PermissionDenied
        try:
            delta = int(request.POST.get("delta", 0))
        except (ValueError, TypeError):
            delta = 0
        if not delta:
            return HttpResponse(status=400)
        entry.quantity = max(0, entry.quantity + delta)
        if entry.quantity <= 0:
            entry.delete()
        else:
            entry.save(update_fields=["quantity", "updated_at"])
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

        qs = Card.objects.filter(is_active=True, name__icontains=q)
        if request.GET.get("commander") == "1":
            qs = qs.filter(can_be_commander=True)
        if request.GET.get("partner") == "1":
            # Partner-eligible: legendary commanders with a partner-like
            # ability (Partner / Partner with / Partner — <tag> / Friends
            # forever / Doctor's companion) OR Backgrounds (partner for
            # "Choose a Background" commanders).
            partner_q = (
                Q(oracle_text__icontains="partner")
                | Q(oracle_text__icontains="friends forever")
                | Q(oracle_text__icontains="doctor's companion")
            )
            background_q = Q(type_line__icontains="Background")
            qs = qs.filter(
                (Q(can_be_commander=True) & partner_q) | background_q
            )
        if request.GET.get("emblem") == "1":
            qs = qs.filter(type_line__icontains="emblem")
        cards = qs.prefetch_related("prints__cardset").order_by("name")[:10]

        results = []
        for card in cards:
            prints = [
                {
                    "id": str(p.pk),
                    "set_code": p.cardset.code if p.cardset else "",
                    "set_name": p.cardset.name if p.cardset else "",
                    "collector_number": p.collector_number,
                    "image": p.image_uris.get("small", ""),
                    "art_crop": p.image_uris.get("art_crop", ""),
                    "price_usd": p.prices.get("usd"),
                }
                for p in card.prints.all()[:20]
            ]
            results.append({
                "id": str(card.pk),
                "oracle_id": str(card.oracle_id),
                "name": card.name,
                "type_line": card.type_line,
                "oracle_text": card.oracle_text,
                "can_be_commander": card.can_be_commander,
                "prints": prints,
            })

        return JsonResponse(results, safe=False)


# ---------------------------------------------------------------------------
# API — Deck categories & card organisation
# ---------------------------------------------------------------------------

class DeckCategoryCreateView(LoginRequiredMixin, View):
    """POST: create a new custom category for a deck."""

    def post(self, request, pk):
        deck = get_object_or_404(Deck, pk=pk)
        if deck.user != request.user:
            raise PermissionDenied
        name = request.POST.get("name", "").strip()
        if not name:
            return JsonResponse({"error": "Nombre requerido."}, status=400)
        if deck.deck_categories.filter(name=name).exists():
            return JsonResponse({"error": "Ya existe esa categoria."}, status=400)
        max_pos = deck.deck_categories.aggregate(m=models.Max("position"))["m"] or 0
        cat = DeckCategory.objects.create(deck=deck, name=name, position=max_pos + 1)
        return JsonResponse({"id": str(cat.pk), "name": cat.name, "position": cat.position})


class DeckCategoryRenameView(LoginRequiredMixin, View):
    """POST: rename a category."""

    def post(self, request, cat_pk):
        cat = get_object_or_404(DeckCategory, pk=cat_pk)
        if cat.deck.user != request.user:
            raise PermissionDenied
        name = request.POST.get("name", "").strip()
        if not name:
            return JsonResponse({"error": "Nombre requerido."}, status=400)
        if cat.deck.deck_categories.filter(name=name).exclude(pk=cat.pk).exists():
            return JsonResponse({"error": "Ya existe esa categoria."}, status=400)
        cat.name = name
        cat.save(update_fields=["name"])
        return JsonResponse({"id": str(cat.pk), "name": cat.name})


class DeckCategoryDeleteView(LoginRequiredMixin, View):
    """POST: delete a category. Cards in it become uncategorized."""

    def post(self, request, cat_pk):
        cat = get_object_or_404(DeckCategory, pk=cat_pk)
        if cat.deck.user != request.user:
            raise PermissionDenied
        cat.delete()
        if request.headers.get("HX-Request"):
            return HttpResponse(status=204)
        return JsonResponse({"ok": True})


class DeckCardMoveCategoryView(LoginRequiredMixin, View):
    """POST: add/remove categories from a card.
    Params: add=<cat_pk>  remove=<cat_pk>  (both optional, can be combined)."""

    def post(self, request, card_pk):
        entry = get_object_or_404(DeckCard, pk=card_pk)
        if entry.deck.user != request.user:
            raise PermissionDenied
        add_id = request.POST.get("add")
        remove_id = request.POST.get("remove")
        if add_id:
            cat = get_object_or_404(DeckCategory, pk=add_id, deck=entry.deck)
            entry.categories.add(cat)
        if remove_id:
            cat = get_object_or_404(DeckCategory, pk=remove_id, deck=entry.deck)
            entry.categories.remove(cat)
        cat_pks = list(entry.categories.values_list("pk", flat=True))
        return JsonResponse({"ok": True, "categories": [str(pk) for pk in cat_pks]})


class DeckCardBulkMoveCategoryView(LoginRequiredMixin, View):
    """POST: add a category to multiple cards at once."""

    def post(self, request, pk):
        import json
        deck = get_object_or_404(Deck, pk=pk)
        if deck.user != request.user:
            raise PermissionDenied

        # Accept card_pks as JSON array or repeated form field
        body_type = request.content_type or ""
        if "json" in body_type:
            data = json.loads(request.body)
            card_pks = data.get("card_pks", [])
            cat_id = data.get("category", "")
        else:
            card_pks = request.POST.getlist("card_pks")
            cat_id = request.POST.get("category", "")

        if not card_pks:
            return JsonResponse({"error": "No cards selected."}, status=400)

        entries = DeckCard.objects.filter(pk__in=card_pks, deck=deck)
        if not entries.exists():
            return JsonResponse({"error": "Cards not found."}, status=404)

        if cat_id:
            cat = get_object_or_404(DeckCategory, pk=cat_id, deck=deck)
            for entry in entries:
                entry.categories.add(cat)
        else:
            # Clear all categories from selected cards
            for entry in entries:
                entry.categories.clear()

        return JsonResponse({"ok": True, "updated": entries.count()})


class DeckCardToggleGameChangerView(LoginRequiredMixin, View):
    """POST: toggle the game changer flag on a deck card."""

    def post(self, request, card_pk):
        entry = get_object_or_404(DeckCard, pk=card_pk)
        if entry.deck.user != request.user:
            raise PermissionDenied
        entry.is_game_changer = not entry.is_game_changer
        entry.save(update_fields=["is_game_changer"])
        return JsonResponse({"ok": True, "is_game_changer": entry.is_game_changer})


# ─── Deck Cloning ────────────────────────────────────────────────────────

class DeckCloneView(LoginRequiredMixin, View):
    """POST: clone a deck (own or public) into current user's collection."""

    def post(self, request, pk):
        source = get_object_or_404(Deck, pk=pk, is_active=True)
        if source.user != request.user and not source.is_public and not source.share_token:
            raise PermissionDenied

        # Create new deck
        new_deck = Deck.objects.create(
            user=request.user,
            name=f"{source.name} (Copia)",
            description=source.description,
            format=source.format,
            is_public=False,
            cover_card=source.cover_card,
            notes=source.notes,
        )

        # Clone categories and build mapping
        cat_map = {}
        for cat in source.deck_categories.all():
            new_cat = DeckCategory.objects.create(
                deck=new_deck, name=cat.name, position=cat.position,
            )
            cat_map[cat.pk] = new_cat

        # Clone cards with category assignments
        for entry in source.cards.select_related("card", "print").prefetch_related("categories"):
            new_entry = DeckCard.objects.create(
                deck=new_deck,
                card=entry.card,
                print=entry.print,
                zone=entry.zone,
                quantity=entry.quantity,
                is_game_changer=entry.is_game_changer,
                owned=False,
            )
            for old_cat in entry.categories.all():
                if old_cat.pk in cat_map:
                    new_entry.categories.add(cat_map[old_cat.pk])

        messages.success(request, f"Deck clonado: {new_deck.name}")
        return redirect("tolarian:deck-detail", pk=new_deck.pk)


# ─── Deck Sharing ────────────────────────────────────────────────────────

class DeckShareView(DeckOwnerMixin, View):
    """POST: generate or return share token for a deck."""

    def post(self, request, pk):
        deck = get_object_or_404(Deck, pk=pk)
        if not deck.share_token:
            deck.share_token = secrets.token_urlsafe(16)
            deck.save(update_fields=["share_token"])

        share_url = request.build_absolute_uri(
            reverse("tolarian:deck-shared", kwargs={"token": deck.share_token})
        )
        return render(request, "tolarian/partials/deck_share.html", {
            "deck": deck,
            "share_url": share_url,
        })

    def delete(self, request, pk):
        deck = get_object_or_404(Deck, pk=pk)
        deck.share_token = None
        deck.save(update_fields=["share_token"])
        return HttpResponse(status=204)


class DeckSharedView(View):
    """GET: public read-only deck view by share token (no login required)."""

    def get(self, request, token):
        deck = get_object_or_404(Deck, share_token=token, is_active=True)

        entries = list(
            deck.cards
            .select_related("card", "print__cardset")
            .prefetch_related("card__faces", "categories")
            .order_by("zone", "card__name")
        )

        # Annotate display fields
        for entry in entries:
            p = entry.print or entry.card.primary_print
            entry.display_price = float(p.price_usd) if p and p.price_usd else 0.0
            entry.display_set = p.cardset.code.upper() if p and p.cardset else ""

        # Group by zone
        zones = {}
        for zone_choice in DeckZone:
            zone_entries = [e for e in entries if e.zone == zone_choice.value]
            if zone_entries:
                qty = sum(e.quantity for e in zone_entries)
                price = round(sum(e.display_price * e.quantity for e in zone_entries), 2)
                zones[zone_choice] = {
                    "entries": zone_entries,
                    "qty": qty,
                    "price": price,
                }

        total_cards = sum(
            e.quantity for e in entries
            if e.zone != DeckZone.EXTRAS
        )

        return render(request, "tolarian/deck_shared.html", {
            "deck": deck,
            "zones": zones,
            "deck_entries": entries,
            "total_cards": total_cards,
            "is_owner": False,
        })


# ─── Deck Versioning ─────────────────────────────────────────────────────

class DeckVersionCreateView(DeckOwnerMixin, View):
    """POST: snapshot current deck state into a new DeckVersion."""

    def post(self, request, pk):
        deck = get_object_or_404(Deck, pk=pk)
        last_version = deck.versions.aggregate(max_v=models.Max("version"))["max_v"] or 0
        version = DeckVersion.objects.create(
            deck=deck,
            version=last_version + 1,
            label=request.POST.get("label", "").strip(),
            notes=request.POST.get("notes", "").strip(),
            snapshot=deck.create_snapshot(),
        )
        messages.success(request, f"Version v{version.version} guardada.")

        if request.headers.get("HX-Request"):
            versions = deck.versions.filter(is_active=True)
            return render(request, "tolarian/partials/deck_versions.html", {
                "deck": deck, "versions": versions, "is_owner": True,
            })
        return redirect("tolarian:deck-detail", pk=deck.pk)


class DeckVersionListView(LoginRequiredMixin, View):
    """GET: HTMX partial — version timeline for a deck."""

    def get(self, request, pk):
        deck = get_object_or_404(Deck, pk=pk, is_active=True)
        if deck.user != request.user and not deck.is_public and not deck.share_token:
            raise PermissionDenied

        versions = deck.versions.filter(is_active=True)
        is_owner = deck.user == request.user
        return render(request, "tolarian/partials/deck_versions.html", {
            "deck": deck, "versions": versions, "is_owner": is_owner,
        })


class DeckVersionDetailView(LoginRequiredMixin, View):
    """GET: HTMX partial — read-only view of a version snapshot."""

    def get(self, request, version_pk):
        version = get_object_or_404(
            DeckVersion.objects.select_related("deck"),
            pk=version_pk,
        )
        deck = version.deck
        if deck.user != request.user and not deck.is_public and not deck.share_token:
            raise PermissionDenied

        snapshot = version.snapshot
        # Group cards by zone for display
        zone_groups = {}
        for card_data in snapshot.get("cards", []):
            zone_label = dict(DeckZone.choices).get(card_data["zone"], card_data["zone"])
            zone_groups.setdefault(zone_label, []).append(card_data)

        return render(request, "tolarian/partials/deck_version_detail.html", {
            "version": version,
            "deck": deck,
            "zone_groups": zone_groups,
            "snapshot": snapshot,
        })


class DeckVersionRestoreView(DeckOwnerMixin, View):
    """POST: restore deck state from a version snapshot."""

    def post(self, request, version_pk):
        version = get_object_or_404(
            DeckVersion.objects.select_related("deck"),
            pk=version_pk,
        )
        deck = version.deck
        if deck.user != request.user:
            raise PermissionDenied

        deck.restore_from_snapshot(version.snapshot)
        messages.success(request, f"Deck restaurado a v{version.version}.")
        return redirect("tolarian:deck-detail", pk=deck.pk)


# ─── Deck Comparison ──────────────────────────────────────────────────────

class DeckCompareView(LoginRequiredMixin, TemplateView):
    """GET: side-by-side comparison of two decks."""
    template_name = "tolarian/deck_compare.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        a_pk = self.request.GET.get("a")
        b_pk = self.request.GET.get("b")

        if not a_pk or not b_pk:
            # Show deck picker
            user_decks = (
                Deck.objects
                .filter(user=self.request.user, is_active=True)
                .annotate(card_count=Sum("cards__quantity"))
                .select_related("cover_card__card")
                .order_by("name")
            )
            ctx["user_decks"] = user_decks
            return ctx

        deck_a = get_object_or_404(Deck, pk=a_pk, is_active=True)
        deck_b = get_object_or_404(Deck, pk=b_pk, is_active=True)

        # Check access
        for d in (deck_a, deck_b):
            if d.user != self.request.user and not d.is_public and not d.share_token:
                raise PermissionDenied

        # Build card maps: {card_name: {zone: qty}}
        def build_card_map(deck):
            result = {}
            for entry in deck.cards.select_related("card").exclude(zone=DeckZone.EXTRAS):
                name = entry.card.name
                if name not in result:
                    result[name] = {"total_qty": 0, "zones": {}, "card": entry.card}
                result[name]["total_qty"] += entry.quantity
                result[name]["zones"][entry.zone] = (
                    result[name]["zones"].get(entry.zone, 0) + entry.quantity
                )
            return result

        map_a = build_card_map(deck_a)
        map_b = build_card_map(deck_b)

        all_names = sorted(set(map_a.keys()) | set(map_b.keys()))

        only_a = []
        only_b = []
        shared = []

        for name in all_names:
            in_a = map_a.get(name)
            in_b = map_b.get(name)
            if in_a and not in_b:
                only_a.append({"card": in_a["card"], "qty": in_a["total_qty"]})
            elif in_b and not in_a:
                only_b.append({"card": in_b["card"], "qty": in_b["total_qty"]})
            else:
                shared.append({
                    "card": in_a["card"],
                    "qty_a": in_a["total_qty"],
                    "qty_b": in_b["total_qty"],
                    "diff": in_a["total_qty"] - in_b["total_qty"],
                })

        a_total = sum(m["total_qty"] for m in map_a.values())
        b_total = sum(m["total_qty"] for m in map_b.values())

        # ── Enhanced comparison statistics ──
        import json as _json
        from collections import Counter as _Counter

        def _mana_curve(m):
            """Return {cmc: qty} for non-land cards."""
            curve = _Counter()
            for entry in m.values():
                c = entry["card"]
                if c.cmc is None or "land" in (c.type_line or "").lower():
                    continue
                curve[int(c.cmc)] += entry["total_qty"]
            return dict(sorted(curve.items()))

        def _type_counts(m):
            """Return {type_label: qty} across the deck."""
            counts = _Counter()
            for entry in m.values():
                tl = (entry["card"].type_line or "").lower()
                qty = entry["total_qty"]
                for t in ["creature", "instant", "sorcery", "artifact",
                          "enchantment", "planeswalker", "land", "battle"]:
                    if t in tl:
                        counts[t.capitalize()] += qty
                        break  # count each card once even if multi-typed
            return counts

        def _color_identity(m):
            """Return set of color identity symbols across the deck."""
            ci = set()
            for entry in m.values():
                for color in (entry["card"].color_identity or []):
                    ci.add(color)
            return sorted(ci)

        curve_a = _mana_curve(map_a)
        curve_b = _mana_curve(map_b)
        all_cmcs = sorted(set(curve_a.keys()) | set(curve_b.keys()))

        types_a = _type_counts(map_a)
        types_b = _type_counts(map_b)
        all_types = ["Creature", "Instant", "Sorcery", "Artifact",
                     "Enchantment", "Planeswalker", "Land", "Battle"]

        ci_a = _color_identity(map_a)
        ci_b = _color_identity(map_b)

        # Overlap %: shared unique card names / total unique names across both
        total_unique = len(map_a) + len(map_b) - len(shared)
        overlap_pct = round(len(shared) / total_unique * 100, 1) if total_unique else 0

        # Value and cost-to-transform
        val_a = float(deck_a.total_value or 0)
        val_b = float(deck_b.total_value or 0)
        # Cost to build B using cards A doesn't have
        try:
            cost_to_transform = sum(
                float(entry.print.price_usd or 0) * entry.quantity
                for entry in deck_b.cards.select_related("print").exclude(zone=DeckZone.EXTRAS)
                if entry.print and entry.card.name not in map_a
            )
        except Exception:
            cost_to_transform = 0

        ctx.update({
            "deck_a": deck_a,
            "deck_b": deck_b,
            "only_a": only_a,
            "only_b": only_b,
            "shared": shared,
            "stats": {
                "a_total": a_total,
                "b_total": b_total,
                "only_a_count": len(only_a),
                "only_b_count": len(only_b),
                "shared_count": len(shared),
                "overlap_pct": overlap_pct,
                "value_a": round(val_a, 2),
                "value_b": round(val_b, 2),
                "value_diff": round(val_b - val_a, 2),
                "cost_to_transform": round(cost_to_transform, 2),
                "ci_a": ci_a,
                "ci_b": ci_b,
                "ci_shared": sorted(set(ci_a) & set(ci_b)),
                "ci_only_a": sorted(set(ci_a) - set(ci_b)),
                "ci_only_b": sorted(set(ci_b) - set(ci_a)),
            },
            "curve_chart_json": _json.dumps({
                "labels": [str(c) for c in all_cmcs],
                "a": [curve_a.get(c, 0) for c in all_cmcs],
                "b": [curve_b.get(c, 0) for c in all_cmcs],
                "a_name": deck_a.name,
                "b_name": deck_b.name,
            }),
            "types_chart_json": _json.dumps({
                "labels": [t for t in all_types if types_a.get(t) or types_b.get(t)],
                "a": [types_a.get(t, 0) for t in all_types if types_a.get(t) or types_b.get(t)],
                "b": [types_b.get(t, 0) for t in all_types if types_a.get(t) or types_b.get(t)],
                "a_name": deck_a.name,
                "b_name": deck_b.name,
            }),
        })
        return ctx