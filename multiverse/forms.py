# multiverse/forms.py
from django import forms
from core.constants import (
    MagicFormat,
    MagicColor,
    CardRarity,
    CardLayout,
    CardSetType,
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
    color = forms.ChoiceField(
        required=False,
        label="Color",
        choices=EMPTY + MagicColor.choices,
        widget=forms.Select(attrs={"class": "input"}),
    )
    color_match = forms.ChoiceField(
        required=False,
        label="Coincidencia",
        choices=[
            ("",         "— Cualquiera —"),
            ("identity", "Color identity"),
            ("exact",    "Exacto"),
            ("includes", "Incluye"),
        ],
        widget=forms.Select(attrs={"class": "input"}),
    )
    rarity = forms.ChoiceField(
        required=False,
        label="Rareza",
        choices=EMPTY + CardRarity.choices,
        widget=forms.Select(attrs={"class": "input"}),
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
    type_line = forms.CharField(
        required=False,
        label="Tipo",
        widget=forms.TextInput(attrs={
            "placeholder": "Creature, Instant...",
            "class":       "input",
        }),
    )
    oracle_text = forms.CharField(
        required=False,
        label="Texto oracle",
        widget=forms.TextInput(attrs={
            "placeholder": "flying, haste...",
            "class":       "input",
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
        if data.get("q"):
            qs = qs.filter(name__icontains=data["q"])

        if data.get("color"):
            color       = data["color"]
            color_match = data.get("color_match", "identity")
            if color_match == "exact":
                qs = qs.filter(colors=[color])
            elif color_match == "includes":
                qs = qs.filter(colors__contains=color)
            else:
                qs = qs.filter(color_identity__contains=color)

        if data.get("rarity"):
            qs = qs.filter(prints__rarity=data["rarity"]).distinct()

        if data.get("layout"):
            qs = qs.filter(layout=data["layout"])

        if data.get("format"):
            qs = qs.filter(
                legality__data__contains={data["format"]: "legal"}
            )

        if data.get("cmc") is not None:
            op = data.get("cmc_op", "eq")
            if op == "lte":
                qs = qs.filter(cmc__lte=data["cmc"])
            elif op == "gte":
                qs = qs.filter(cmc__gte=data["cmc"])
            else:
                qs = qs.filter(cmc=data["cmc"])

        if data.get("type_line"):
            qs = qs.filter(type_line__icontains=data["type_line"])

        if data.get("oracle_text"):
            qs = qs.filter(oracle_text__icontains=data["oracle_text"])

        if data.get("commander"):
            qs = qs.filter(can_be_commander=True)

        if data.get("has_deck_limit"):
            qs = qs.filter(has_deck_limit=True)

        # Filtro por card_kind
        kind = data.get("card_kind", "")
        if kind == "normal":
            # Solo layouts normales — excluye arte, tokens, planes, etc.
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