# multiverse/forms.py
from django import forms
from core.constants import (
    MagicFormat,
    MagicColor,
    CardRarity,
    CardLayout,
    CardSetType,
    CardType,
    CardSupertype,
)


EMPTY = [("", "— Todos —")]

CARD_KIND_CHOICES = [
    ("",            "— Todos —"),
    ("normal",      "Solo cartas normales"),
    ("token",       "Tokens"),
    ("planar",      "Planos"),
    ("scheme",      "Schemes"),
    ("conspiracy",  "Conspiracies"),
    ("vanguard",    "Vanguard"),
    ("emblem",      "Emblemas"),
]

VERSION_CHOICES = [
    ("all",    "Todas las versiones"),
    ("latest", "Solo versión más reciente"),
]

SORT_CHOICES = [
    ("date_desc", "Fecha ↓ (más reciente)"),
    ("date_asc",  "Fecha ↑ (más antiguo)"),
    ("name_asc",  "Nombre A → Z"),
    ("name_desc", "Nombre Z → A"),
]

NORMAL_LAYOUTS = {
    "normal", "split", "flip", "transform", "modal_dfc",
    "meld", "leveler", "class", "case", "saga", "adventure",
    "battle", "reversible_card", "augment", "host",
}

KIND_LAYOUTS = {
    "token":      ["token", "double_faced_token"],
    "planar":     ["planar"],
    "scheme":     ["scheme"],
    "conspiracy": ["conspiracy"],
    "vanguard":   ["vanguard"],
    "emblem":     ["emblem"],
    "art_series": ["art_series"]
}


class CardSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={
            "placeholder": "Search ...",
            "class":       "input",
            "autofocus":   True,
        }),
    )
    sort = forms.ChoiceField(
        required=False,
        label="Ordenar por",
        choices=SORT_CHOICES,
        widget=forms.Select(attrs={"class": "input"}),
        initial="date_desc",
    )
    color = forms.MultipleChoiceField(
        required=False,
        label="Color",
        choices=MagicColor.choices,
        widget=forms.CheckboxSelectMultiple,
    )
    color_identity = forms.BooleanField(
        required=False,
        label="Buscar por identidad de color",
        widget=forms.CheckboxInput(attrs={"class": "w-4 h-4 rounded"}),
    )
    color_exact = forms.BooleanField(
        required=False,
        label="Exacto (debe tener todos los seleccionados)",
        widget=forms.CheckboxInput(attrs={"class": "w-4 h-4 rounded"}),
    )
    color_exclude = forms.BooleanField(
        required=False,
        label="Excluir no seleccionados",
        widget=forms.CheckboxInput(attrs={"class": "w-4 h-4 rounded"}),
    )
    rarity = forms.MultipleChoiceField(
        required=False,
        label="Rareza",
        choices=CardRarity.choices,
        widget=forms.CheckboxSelectMultiple,
    )
    layout = forms.ChoiceField(
        required=False,
        label="Layout",
        choices=EMPTY + CardLayout.choices,
        widget=forms.Select(attrs={"class": "input"}),
    )
    format = forms.ChoiceField(
        required=False,
        label="Formato",
        choices=EMPTY + MagicFormat.choices,
        widget=forms.Select(attrs={"class": "input"}),
    )
    cmc = forms.DecimalField(
        required=False,
        label="Mana Value (CMC)",
        min_value=0,
        max_value=20,
        widget=forms.NumberInput(attrs={
            "class":       "input",
            "placeholder": "0",
            "step":        "1",
        }),
    )
    cmc_op = forms.ChoiceField(
        required=False,
        label="Operador CMC",
        choices=[
            ("eq", "="),
            ("lte", "≤"),
            ("gte", "≥"),
        ],
        widget=forms.Select(attrs={"class": "input"}),
    )
    # Set filter
    set_code = forms.CharField(
        required=False,
        label="Set",
        widget=forms.TextInput(attrs={
            "placeholder": "Nombre del set...",
            "class":       "input",
        }),
    )
    # Type (autocomplete from CardType enum)
    card_type = forms.CharField(
        required=False,
        label="Tipo",
        widget=forms.TextInput(attrs={
            "placeholder": "Creature, Instant...",
            "class":       "input",
        }),
    )
    # Supertype (autocomplete from CardSupertype enum)
    supertype = forms.CharField(
        required=False,
        label="Supertipo",
        widget=forms.TextInput(attrs={
            "placeholder": "Legendary, Snow...",
            "class":       "input",
        }),
    )
    # Subtype (autocomplete from CreatureType model)
    subtype = forms.CharField(
        required=False,
        label="Subtipo",
        widget=forms.TextInput(attrs={
            "placeholder": "Elf, Dragon, Aura...",
            "class":       "input",
        }),
    )
    # Artist
    artist = forms.CharField(
        required=False,
        label="Artista",
        widget=forms.TextInput(attrs={
            "placeholder": "Nombre del artista...",
            "class":       "input",
        }),
    )
    # Keep legacy type_line for backwards compat
    type_line = forms.CharField(
        required=False,
        label="Línea de tipo (texto libre)",
        widget=forms.TextInput(attrs={
            "placeholder": "Línea de tipo completa...",
            "class":       "input",
        }),
    )
    oracle_text = forms.CharField(
        required=False,
        label="Texto oracle",
        widget=forms.Textarea(attrs={
            "placeholder": "flying, haste...",
            "class":       "input",
            "rows":        2,
        }),
    )
    card_kind = forms.ChoiceField(
        required=False,
        label="Tipo especial",
        choices=CARD_KIND_CHOICES,
        widget=forms.Select(attrs={"class": "input"}),
    )
    version = forms.ChoiceField(
        required=False,
        label="Versiones",
        choices=VERSION_CHOICES,
        widget=forms.Select(attrs={"class": "input"}),
        initial="all",
    )
    # Exclude Universe Beyond
    exclude_ub = forms.BooleanField(
        required=False,
        label="Excluir Universes Beyond",
        widget=forms.CheckboxInput(attrs={"class": "w-4 h-4 rounded"}),
    )
    digital = forms.BooleanField(
        required=False,
        label="Incluir cartas digitales",
        widget=forms.CheckboxInput(attrs={"class": "w-4 h-4 rounded"}),
    )
    commander = forms.BooleanField(
        required=False,
        label="Solo commanders",
        widget=forms.CheckboxInput(attrs={"class": "w-4 h-4 rounded"}),
    )
    has_deck_limit = forms.BooleanField(
        required=False,
        label="Copias ilimitadas",
        widget=forms.CheckboxInput(attrs={"class": "w-4 h-4 rounded"}),
    )

    def filter_queryset(self, qs):
        if not self.is_valid():
            return qs

        data = self.cleaned_data

        if data.get("q"):
            qs = qs.filter(name__icontains=data["q"])

        # Excluir cartas sin type_line por defecto
        qs = qs.exclude(type_line="")

        # Excluir cartas digitales por defecto — solo incluir si el usuario lo pide
        if not data.get("digital"):
            qs = qs.filter(prints__digital=False).distinct()

        # --- Filtros del usuario ---

        if data.get("color"):
            from django.db.models import Q
            colors_selected = set(data["color"])  # set of color codes
            use_identity = data.get("color_identity", False)
            exact = data.get("color_exact", False)
            exclude = data.get("color_exclude", False) or use_identity
            field = "color_identity" if use_identity else "colors"
            has_colorless = "C" in colors_selected
            real_colors = colors_selected - {"C"}
            all_wubrg = {"W", "U", "B", "R", "G"}

            if exact:
                # Must have ALL selected colors
                for c in real_colors:
                    qs = qs.filter(**{f"{field}__icontains": f'"{c}"'})
                if has_colorless and not real_colors:
                    qs = qs.filter(**{field: "[]"})

            if exclude:
                # Forbid non-selected colors
                excluded = all_wubrg - real_colors
                for c in excluded:
                    qs = qs.exclude(**{f"{field}__icontains": f'"{c}"'})

            if not exact:
                # Need at least one selected color (OR logic)
                if real_colors:
                    q = Q()
                    if has_colorless and not exclude:
                        q = Q(**{field: "[]"})
                    for c in real_colors:
                        q |= Q(**{f"{field}__icontains": f'"{c}"'})
                    qs = qs.filter(q)
                elif has_colorless:
                    qs = qs.filter(**{field: "[]"})

        if data.get("rarity"):
            qs = qs.filter(prints__rarity__in=data["rarity"]).distinct()

        if data.get("layout"):
            qs = qs.filter(layout=data["layout"])

        if data.get("format"):
            # SQLite-compatible: search raw JSON text for "format": "legal"
            fmt = data["format"]
            qs = qs.filter(legality__data__icontains=f'"{fmt}": "legal"')

        if data.get("cmc") is not None:
            op = data.get("cmc_op", "eq")
            if op == "lte":
                qs = qs.filter(cmc__lte=data["cmc"])
            elif op == "gte":
                qs = qs.filter(cmc__gte=data["cmc"])
            else:
                qs = qs.filter(cmc=data["cmc"])

        # Set filter
        if data.get("set_code"):
            qs = qs.filter(
                prints__cardset__name__icontains=data["set_code"]
            ).distinct()

        # Card type (searches type_line for the type)
        if data.get("card_type"):
            qs = qs.filter(type_line__icontains=data["card_type"])

        # Supertype (searches type_line)
        if data.get("supertype"):
            qs = qs.filter(type_line__icontains=data["supertype"])

        # Subtype (searches type_line — part after the dash)
        if data.get("subtype"):
            qs = qs.filter(type_line__icontains=data["subtype"])

        # Artist filter
        if data.get("artist"):
            qs = qs.filter(
                prints__artist__icontains=data["artist"]
            ).distinct()

        # Legacy type_line free text
        if data.get("type_line"):
            qs = qs.filter(type_line__icontains=data["type_line"])

        if data.get("oracle_text"):
            qs = qs.filter(oracle_text__icontains=data["oracle_text"])

        if data.get("commander"):
            qs = qs.filter(can_be_commander=True)

        if data.get("has_deck_limit"):
            qs = qs.filter(has_deck_limit=True)

        # Exclude Universe Beyond
        if data.get("exclude_ub"):
            qs = qs.exclude(prints__cardset__is_universe_beyond=True)

        # Filtro por card_kind
        kind = data.get("card_kind", "")
        if kind == "normal":
            qs = qs.filter(layout__in=NORMAL_LAYOUTS)
        elif kind in KIND_LAYOUTS:
            qs = qs.filter(layout__in=KIND_LAYOUTS[kind])

        if data.get("digital"):
            qs = qs.filter(prints__digital=True).distinct()

        return qs


class SetSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={
            "placeholder": "Nombre del set...",
            "class":       "input",
            "autofocus":   True,
        }),
    )
    set_type = forms.ChoiceField(
        required=False,
        label="Tipo",
        choices=EMPTY + CardSetType.choices,
        widget=forms.Select(attrs={"class": "input"}),
    )
    digital = forms.ChoiceField(
        required=False,
        label="Disponibilidad",
        choices=[
            ("",    "— Todos —"),
            ("0",   "Solo papel"),
            ("1",   "Solo digital"),
        ],
        widget=forms.Select(attrs={"class": "input"}),
    )

    def filter_queryset(self, qs):
        if not self.is_valid():
            return qs

        data = self.cleaned_data

        if data.get("q"):
            qs = qs.filter(name__icontains=data["q"])

        if data.get("set_type"):
            qs = qs.filter(set_type=data["set_type"])

        if data.get("digital") == "0":
            qs = qs.filter(digital=False)
        elif data.get("digital") == "1":
            qs = qs.filter(digital=True)

        return qs
