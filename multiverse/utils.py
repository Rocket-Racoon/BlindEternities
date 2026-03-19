# multiverse/utils.py
import re


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