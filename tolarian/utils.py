# tolarian/utils.py
import csv
import io
import re
from django.db import transaction
from multiverse.models import Card, CardPrint
from .models import (CollectionItem, DeckCard, DeckZone)
from core.constants import (CardCondition, CardFinish)


# ---------------------------------------------------------------------------
# Parsers de import
# ---------------------------------------------------------------------------

# Regex para líneas de texto plano: "4x Lightning Bolt" o "4 Lightning Bolt"
DECKLIST_LINE_RE = re.compile(
    r"^\s*(?P<qty>\d+)\s*[xX]?\s+(?P<name>.+?)\s*$"
)

# Cabeceras de zona en texto plano
ZONE_HEADERS = {
    "commander":  DeckZone.COMMANDER,
    "companion":  DeckZone.COMPANION,
    "sideboard":  DeckZone.SIDEBOARD,
    "side":       DeckZone.SIDEBOARD,
    "maybeboard": DeckZone.MAYBEBOARD,
    "maybe":      DeckZone.MAYBEBOARD,
    "reserve":    DeckZone.RESERVE,
    "extras":     DeckZone.EXTRAS,
    "tokens":     DeckZone.EXTRAS,
}


def parse_decklist_text(source, deck):
    """
    Parsea una lista de cartas en texto plano o CSV y las agrega al deck.

    Soporta:
        - Texto plano: "4x Lightning Bolt"
        - CSV de Moxfield / Archidekt con columna 'Name'

    Retorna: {"created": int, "not_found": int}
    """
    if hasattr(source, "read"):
        raw = source.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
    else:
        raw = str(source)

    # Detectar si es CSV
    if "," in raw[:500] and "\n" in raw[:500]:
        return _parse_csv_decklist(raw, deck)
    return _parse_text_decklist(raw, deck)


@transaction.atomic
def _parse_text_decklist(text, deck):
    created   = 0
    not_found = 0
    current_zone = DeckZone.MAIN

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Detectar cabecera de zona (// Commander, // Sideboard, etc.)
        if line.startswith("//"):
            zone_hint = line.lstrip("/").strip().lower()
            for key, zone in ZONE_HEADERS.items():
                if key in zone_hint:
                    current_zone = zone
                    break
            continue

        match = DECKLIST_LINE_RE.match(line)
        if not match:
            continue

        qty  = int(match.group("qty"))
        name = match.group("name").strip()

        # Quitar el set code si viene (ej: "Lightning Bolt (M10)")
        name = re.sub(r"\s*\([^)]+\)\s*$", "", name).strip()

        card = Card.objects.filter(name__iexact=name, is_active=True).first()
        if not card:
            not_found += 1
            continue

        existing = DeckCard.objects.filter(
            deck=deck,
            card=card,
            zone=current_zone,
        ).first()

        if existing:
            existing.quantity += qty
            existing.save(update_fields=["quantity", "updated_at"])
        else:
            DeckCard.objects.create(
                deck=deck,
                card=card,
                zone=current_zone,
                quantity=qty,
            )
            created += 1

    return {"created": created, "not_found": not_found}


@transaction.atomic
def _parse_csv_decklist(text, deck):
    """Parsea CSV de Moxfield / Archidekt."""
    created   = 0
    not_found = 0
    reader    = csv.DictReader(io.StringIO(text))

    # Normalizar cabeceras
    fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]

    for row in reader:
        row_normalized = {k.strip().lower(): v for k, v in row.items()}

        # Buscar nombre de carta
        name = (
            row_normalized.get("name") or
            row_normalized.get("card name") or
            row_normalized.get("cardname") or ""
        ).strip()
        if not name:
            continue

        # Buscar cantidad
        qty_raw = (
            row_normalized.get("quantity") or
            row_normalized.get("qty") or
            row_normalized.get("count") or "1"
        ).strip()
        try:
            qty = int(qty_raw)
        except ValueError:
            qty = 1

        # Detectar zona
        zone_raw = (
            row_normalized.get("board") or
            row_normalized.get("zone") or
            row_normalized.get("section") or ""
        ).strip().lower()
        zone = ZONE_HEADERS.get(zone_raw, DeckZone.MAIN)

        card = Card.objects.filter(name__iexact=name, is_active=True).first()
        if not card:
            not_found += 1
            continue

        existing = DeckCard.objects.filter(
            deck=deck,
            card=card,
            zone=zone,
        ).first()

        if existing:
            existing.quantity += qty
            existing.save(update_fields=["quantity", "updated_at"])
        else:
            DeckCard.objects.create(
                deck=deck,
                card=card,
                zone=zone,
                quantity=qty,
            )
            created += 1

    return {"created": created, "not_found": not_found}


@transaction.atomic
def parse_collection_csv(file, collection):
    """
    Parsea CSV de colección.
    Soporta: Moxfield, Archidekt, DragonShield, TCGPlayer.

    Retorna: {"created": int, "updated": int, "errors": int}
    """
    raw = file.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")

    reader  = csv.DictReader(io.StringIO(raw))
    created = updated = errors = 0

    for row in reader:
        row_n = {k.strip().lower(): v.strip() for k, v in row.items()}

        try:
            name = (
                row_n.get("name") or
                row_n.get("card name") or
                row_n.get("cardname") or ""
            ).strip()
            if not name:
                continue

            qty_raw = row_n.get("quantity") or row_n.get("qty") or row_n.get("count") or "1"
            qty     = int(qty_raw)

            condition_raw = (row_n.get("condition") or "NM").upper()[:3]
            condition     = condition_raw if condition_raw in CardCondition.values else CardCondition.NEAR_MINT

            finish_raw = (row_n.get("foil") or row_n.get("finish") or "nonfoil").lower()
            if "etched" in finish_raw:
                finish = CardFinish.ETCHED
            elif finish_raw in ("true", "yes", "foil", "1"):
                finish = CardFinish.FOIL
            else:
                finish = CardFinish.NONFOIL

            language = (row_n.get("language") or row_n.get("lang") or "en")[:10]

            purchase_price = None
            price_raw = row_n.get("purchase price") or row_n.get("price") or ""
            if price_raw:
                try:
                    purchase_price = float(price_raw.replace("$", "").strip())
                except ValueError:
                    pass

            set_code = (row_n.get("set") or row_n.get("edition") or "").lower()

            card = Card.objects.filter(name__iexact=name, is_active=True).first()
            if not card:
                errors += 1
                continue

            # Intentar encontrar el print específico
            print_obj = None
            if set_code:
                print_obj = CardPrint.objects.filter(
                    card=card,
                    cardset__code=set_code,
                ).first()

            existing = CollectionItem.objects.filter(
                collection=collection,
                card=card,
                print=print_obj,
                condition=condition,
                finish=finish,
                language=language,
            ).first()

            if existing:
                existing.quantity += qty
                existing.save(update_fields=["quantity", "updated_at"])
                updated += 1
            else:
                CollectionItem.objects.create(
                    collection=collection,
                    card=card,
                    print=print_obj,
                    quantity=qty,
                    condition=condition,
                    finish=finish,
                    language=language,
                    purchase_price=purchase_price,
                )
                created += 1

        except Exception:
            errors += 1
            continue

    return {"created": created, "updated": updated, "errors": errors}


# Regex para bulk de colección:
#   4x Lightning Bolt (M10) NM foil
#   2 Counterspell LP etched
#   1 Sol Ring
# Grupos: qty, name, set_code (opcional), extras (condición/finish opcionales)
COLLECTION_LINE_RE = re.compile(
    r"^\s*(?P<qty>\d+)\s*[xX]?\s+"
    r"(?P<name>.+?)"
    r"(?:\s+\((?P<set>[^)]+)\))?"
    r"(?P<extras>(?:\s+(?:" + "|".join([
        "NM", "LP", "MP", "HP", "DMG",
        "foil", "nonfoil", "etched", "glossy",
        "surge", "textured", "gilded", "galaxy",
        "ripple", "halo", "oilslick", "neonink",
        "confetti", "doublerainbow", "premodern",
        "ampersand", "firstplace", "fractur",
        "invisible", "mana", "silverscreen",
        "stepcomplete", "vault",
    ]) + r"))*)"
    r"\s*$",
    re.IGNORECASE,
)

CONDITION_TOKENS = {v.upper(): v for v in CardCondition.values}   # NM, LP, MP, HP, DMG
FINISH_TOKENS    = {v.lower(): v for v in CardFinish.values}      # foil, etched, glossy, ...


def _parse_extras(extras_str):
    """Extract condition and finish from trailing tokens like 'NM foil'."""
    condition = CardCondition.NEAR_MINT
    finish    = CardFinish.NONFOIL

    for token in extras_str.split():
        upper = token.upper()
        lower = token.lower()
        if upper in CONDITION_TOKENS:
            condition = CONDITION_TOKENS[upper]
        elif lower in FINISH_TOKENS:
            finish = FINISH_TOKENS[lower]

    return condition, finish


@transaction.atomic
def parse_collection_text(text, collection):
    """
    Parsea una lista de cartas en texto plano y las agrega a la colección.

    Formato:
        4x Lightning Bolt
        4x Lightning Bolt (M10) NM foil
        2 Counterspell LP etched

    Retorna: {"created": int, "updated": int, "not_found": list[str]}
    """
    created   = 0
    updated   = 0
    not_found = []

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue

        match = COLLECTION_LINE_RE.match(line)
        if not match:
            # Fallback al regex simple
            simple = DECKLIST_LINE_RE.match(line)
            if not simple:
                continue
            qty  = int(simple.group("qty"))
            name = re.sub(r"\s*\([^)]+\)\s*$", "", simple.group("name")).strip()
            set_code  = None
            condition = CardCondition.NEAR_MINT
            finish    = CardFinish.NONFOIL
        else:
            qty      = int(match.group("qty"))
            name     = match.group("name").strip()
            set_code = (match.group("set") or "").strip().lower() or None
            condition, finish = _parse_extras(match.group("extras") or "")

        card = Card.objects.filter(name__iexact=name, is_active=True).first()
        if not card:
            not_found.append(name)
            continue

        # Intentar encontrar el print específico por set code
        print_obj = None
        if set_code:
            print_obj = CardPrint.objects.filter(
                card=card,
                cardset__code=set_code,
            ).first()

        existing = CollectionItem.objects.filter(
            collection=collection,
            card=card,
            print=print_obj,
            condition=condition,
            finish=finish,
            language="en",
        ).first()

        if existing:
            existing.quantity += qty
            existing.save(update_fields=["quantity", "updated_at"])
            updated += 1
        else:
            CollectionItem.objects.create(
                collection=collection,
                card=card,
                print=print_obj,
                quantity=qty,
                condition=condition,
                finish=finish,
                language="en",
            )
            created += 1

    return {"created": created, "updated": updated, "not_found": not_found}


# ---------------------------------------------------------------------------
# Exporters
# ---------------------------------------------------------------------------

def deck_to_csv(deck):
    """Exporta un deck a CSV compatible con Moxfield."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Count", "Name", "Edition", "Collector Number",
        "Foil", "Board",
    ])
    for entry in deck.cards.select_related("card", "print__cardset").order_by("zone", "card__name"):
        print_obj = entry.print
        writer.writerow([
            entry.quantity,
            entry.card.name,
            print_obj.cardset.code.upper() if print_obj else "",
            print_obj.collector_number if print_obj else "",
            "foil" if print_obj and "foil" in (print_obj.finishes or []) else "normal",
            entry.zone,
        ])
    return output.getvalue()


def collection_to_csv(collection):
    """Exporta una colección a CSV compatible con Moxfield."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Count", "Name", "Edition", "Collector Number",
        "Condition", "Foil", "Language", "Purchase Price", "Notes",
    ])
    for item in collection.items.select_related("card", "print__cardset").order_by("card__name"):
        print_obj = item.print
        writer.writerow([
            item.quantity,
            item.card.name,
            print_obj.cardset.code.upper() if print_obj else "",
            print_obj.collector_number if print_obj else "",
            item.condition,
            item.finish,
            item.language,
            item.purchase_price or "",
            item.notes,
        ])
    return output.getvalue()