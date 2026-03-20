# multiverse/utils.py
import re
import uuid as uuid_lib


def compute_deck_rules(card_data):
    """
    Calcula las reglas de deck building a partir del objeto Scryfall.
    Funciona con cartas normales y multifaz.
    """
    # Para cartas multifaz el oracle_text puede estar en las caras
    oracle_text = card_data.get("oracle_text") or " ".join(
        face.get("oracle_text", "")
        for face in card_data.get("card_faces", [])
    )
    type_line = card_data.get("type_line", "")

    # can_be_commander
    can_be_commander = (
        ("Legendary" in type_line and "Creature" in type_line)
        or ("Legendary" in type_line and "Vehicle" in type_line)
        or bool(re.search(r"can be your commander", oracle_text, re.IGNORECASE))
    )

    # has_deck_limit / max_deck_copies
    any_number_pattern = re.search(
        r"a deck can have any number of cards named",
        oracle_text,
        re.IGNORECASE,
    )
    up_to_pattern = re.search(
        r"a deck can have up to (\d+) cards named",
        oracle_text,
        re.IGNORECASE,
    )
    basic_land = (
        bool(re.search(r"\bBasic\b", type_line))
        and bool(re.search(r"\bLand\b", type_line))
    )

    if basic_land:
        has_deck_limit  = True
        max_deck_copies = 0
    elif any_number_pattern:
        has_deck_limit  = True
        max_deck_copies = 0
    elif up_to_pattern:
        has_deck_limit  = True
        max_deck_copies = int(up_to_pattern.group(1))
    else:
        has_deck_limit  = False
        max_deck_copies = None

    return {
        "can_be_commander":    can_be_commander,
        "has_deck_limit":      has_deck_limit,
        "max_deck_copies":     max_deck_copies,
        "banned_as_companion": False,
    }
    
    
def parse_uuid(value):
    """Convierte un string a UUID — retorna None si falla."""
    if not value:
        return None
    try:
        return uuid_lib.UUID(str(value))
    except (ValueError, AttributeError):
        return None


def build_card_defaults(data, deck_rules):
    return {
        "name":               data.get("name", ""),
        "lang":               data.get("lang", "en"),
        "layout":             data.get("layout", ""),
        "type_line":          data.get("type_line", ""),
        "oracle_text":        data.get("oracle_text", ""),
        "mana_cost":          data.get("mana_cost", ""),
        "cmc":                data.get("cmc"),
        "colors":             data.get("colors", []),
        "color_identity":     data.get("color_identity", []),
        "color_indicator":    data.get("color_indicator", []),
        "power":              data.get("power", ""),
        "toughness":          data.get("toughness", ""),
        "loyalty":            data.get("loyalty", ""),
        "defense":            data.get("defense", ""),
        "hand_modifier":      data.get("hand_modifier", ""),
        "life_modifier":      data.get("life_modifier", ""),
        "keywords":           data.get("keywords", []),
        "produced_mana":      data.get("produced_mana", []),
        "all_parts":          data.get("all_parts", []),
        "reserved":           data.get("reserved", False),
        "foil":               data.get("foil", False),
        "nonfoil":            data.get("nonfoil", False),
        "oversized":          data.get("oversized", False),
        "edhrec_rank":        data.get("edhrec_rank"),
        "penny_rank":         data.get("penny_rank"),
        "scryfall_uri":       data.get("scryfall_uri", ""),
        "rulings_uri":        data.get("rulings_uri", ""),
        "prints_search_uri":  data.get("prints_search_uri", ""),
        "multiverse_ids":     data.get("multiverse_ids", []),
        "mtgo_id":            data.get("mtgo_id"),
        "mtgo_foil_id":       data.get("mtgo_foil_id"),
        "arena_id":           data.get("arena_id"),
        "tcgplayer_id":       data.get("tcgplayer_id"),
        "cardmarket_id":      data.get("cardmarket_id"),
        "is_active":          True,
        **deck_rules,
    }


def build_face_defaults(data):
    return {
        "name":               data.get("name", ""),
        "printed_name":       data.get("printed_name", ""),
        "flavor_name":        data.get("flavor_name", ""),
        "type_line":          data.get("type_line", ""),
        "printed_type_line":  data.get("printed_type_line", ""),
        "oracle_text":        data.get("oracle_text", ""),
        "printed_text":       data.get("printed_text", ""),
        "mana_cost":          data.get("mana_cost", ""),
        "cmc":                data.get("cmc"),
        "colors":             data.get("colors", []),
        "color_indicator":    data.get("color_indicator", []),
        "power":              data.get("power", ""),
        "toughness":          data.get("toughness", ""),
        "loyalty":            data.get("loyalty", ""),
        "defense":            data.get("defense", ""),
        "artist":             data.get("artist", ""),
        "artist_id":          parse_uuid(data.get("artist_id")),
        "illustration_id":    parse_uuid(data.get("illustration_id")),
        "image_uris":         data.get("image_uris", {}),
        "flavor_text":        data.get("flavor_text", ""),
        "watermark":          data.get("watermark", ""),
        "layout":             data.get("layout", ""),
        "oracle_id":          parse_uuid(data.get("oracle_id")),
    }


def build_print_defaults(card, cardset, data):
    return {
        "card":                 card,
        "cardset":              cardset,
        "collector_number":     data.get("collector_number", ""),
        "lang":                 data.get("lang", "en"),
        "multiverse_ids":       data.get("multiverse_ids", []),
        "mtgo_id":              data.get("mtgo_id"),
        "mtgo_foil_id":         data.get("mtgo_foil_id"),
        "arena_id":             data.get("arena_id"),
        "tcgplayer_id":         data.get("tcgplayer_id"),
        "tcgplayer_etched_id":  data.get("tcgplayer_etched_id"),
        "cardmarket_id":        data.get("cardmarket_id"),
        "illustration_id":      parse_uuid(data.get("illustration_id")),
        "image_uris":           data.get("image_uris", {}),
        "image_status":         data.get("image_status", ""),
        "rarity":               data.get("rarity", ""),
        "flavor_text":          data.get("flavor_text", ""),
        "flavor_name":          data.get("flavor_name", ""),
        "printed_name":         data.get("printed_name", ""),
        "printed_type_line":    data.get("printed_type_line", ""),
        "printed_text":         data.get("printed_text", ""),
        "artist":               data.get("artist", ""),
        "artist_id":            parse_uuid(data.get("artist_id")),
        "border_color":         data.get("border_color", ""),
        "frame":                data.get("frame", ""),
        "frame_effects":        data.get("frame_effects", []),
        "security_stamp":       data.get("security_stamp", ""),
        "watermark":            data.get("watermark", ""),
        "set_type":             data.get("set_type", ""),
        "finishes":             data.get("finishes", []),
        "foil":                 data.get("foil", False),
        "nonfoil":              data.get("nonfoil", False),
        "full_art":             data.get("full_art", False),
        "textless":             data.get("textless", False),
        "booster":              data.get("booster", False),
        "digital":              data.get("digital", False),
        "promo":                data.get("promo", False),
        "reprint":              data.get("reprint", False),
        "variation":            data.get("variation", False),
        "oversized":            data.get("oversized", False),
        "story_spotlight":      data.get("story_spotlight", False),
        "content_warning":      data.get("content_warning", False),
        "reserved":             data.get("reserved", False),
        "promo_types":          data.get("promo_types", []),
        "games":                data.get("games", []),
        "variation_of":         parse_uuid(data.get("variation_of")),
        "prices":               data.get("prices", {}),
        "purchase_uris":        data.get("purchase_uris", {}),
        "related_uris":         data.get("related_uris", {}),
        "released_at":          data.get("released_at"),
        "preview":              data.get("preview", {}),
        "is_active":            True,
    }