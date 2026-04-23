class ManaSymbol:

    # --- Maná de colores ---
    COLORS = {
        "W": ("w", True,  "White mana"),
        "U": ("u", True,  "Blue mana"),
        "B": ("b", True,  "Black mana"),
        "R": ("r", True,  "Red mana"),
        "G": ("g", True,  "Green mana"),
        "C": ("c", True,  "Colorless mana"),
    }

    # --- Maná genérico ---
    GENERIC = {str(i): (str(i), True, f"{i} generic mana") for i in range(21)}
    GENERIC.update({
        "100":     ("100",     True, "100 generic mana"),
        "1000000": ("1000000", True, "1,000,000 generic mana"),
        "X":       ("x",       True, "X mana"),
        "Y":       ("y",       True, "Y mana"),
        "Z":       ("z",       True, "Z mana"),
    })

    # --- Maná especial ---
    SPECIAL_MANA = {
        "S":  ("s",  True,  "Snow mana"),
        "E":  ("e",  False, "Energy"),
        "HW": ("hw", True,  "Half white mana"),
        "HU": ("hu", True,  "Half blue mana"),
        "HB": ("hb", True,  "Half black mana"),
        "HR": ("hr", True,  "Half red mana"),
        "HG": ("hg", True,  "Half green mana"),
    }

    # --- Maná híbrido (2 colores) ---
    HYBRID = {
        "W/U": ("wu", True, "White/Blue hybrid"),
        "W/B": ("wb", True, "White/Black hybrid"),
        "U/B": ("ub", True, "Blue/Black hybrid"),
        "U/R": ("ur", True, "Blue/Red hybrid"),
        "B/R": ("br", True, "Black/Red hybrid"),
        "B/G": ("bg", True, "Black/Green hybrid"),
        "R/G": ("rg", True, "Red/Green hybrid"),
        "R/W": ("rw", True, "Red/White hybrid"),
        "G/W": ("gw", True, "Green/White hybrid"),
        "G/U": ("gu", True, "Green/Blue hybrid"),
    }

    # --- Maná híbrido genérico (2/color) ---
    HYBRID_GENERIC = {
        "2/W": ("2w", True, "2/White hybrid"),
        "2/U": ("2u", True, "2/Blue hybrid"),
        "2/B": ("2b", True, "2/Black hybrid"),
        "2/R": ("2r", True, "2/Red hybrid"),
        "2/G": ("2g", True, "2/Green hybrid"),
        "2/C": ("2c", True, "2/Colorless hybrid"),
    }

    # --- Maná Phyrexian (color/P) ---
    PHYREXIAN = {
        "W/P": ("wp", True, "Phyrexian white mana"),
        "U/P": ("up", True, "Phyrexian blue mana"),
        "B/P": ("bp", True, "Phyrexian black mana"),
        "R/P": ("rp", True, "Phyrexian red mana"),
        "G/P": ("gp", True, "Phyrexian green mana"),
        "C/P": ("cp", True, "Phyrexian colorless mana"),
        # Phyrexian híbrido
        "W/U/P": ("wup", True, "Phyrexian White/Blue hybrid"),
        "G/W/P": ("gwp", True, "Phyrexian Green/White hybrid"),
        "R/G/P": ("rgp", True, "Phyrexian Red/Green hybrid"),
        "U/R/P": ("urp", True, "Phyrexian Blue/Red hybrid"),
        "B/G/P": ("bgp", True, "Phyrexian Black/Green hybrid"),
    }

    # --- Half mana (media mana) ---
    HALF = {
        "HW": ("hw", True, "Half white mana"),
        "HU": ("hu", True, "Half blue mana"),
        "HB": ("hb", True, "Half black mana"),
        "HR": ("hr", True, "Half red mana"),
        "HG": ("hg", True, "Half green mana"),
    }

    # --- Acciones de juego ---
    ACTIONS = {
        "T":     ("tap",     False, "Tap"),
        "Q":     ("untap",   False, "Untap"),
        "CHAOS": ("chaos",   False, "Chaos"),
    }

    # --- Planeswalker ---
    PLANESWALKER = {
        "PW":  ("planeswalker", False, "Planeswalker"),
        "LYN": ("loyalty-up",   False, "Loyalty up"),
        "LYD": ("loyalty-down", False, "Loyalty down"),
        "LY0": ("loyalty-zero", False, "Loyalty zero"),
        "LYA": ("loyalty-up",   False, "Loyalty all"),
    }

    # --- Símbolos de carta ---
    CARD_SYMBOLS = {
        "ARTIST":   ("artist",   False, "Artist"),
        "ACORN":    ("acorn",    False, "Acorn (Unfinity)"),
        "TICKET":   ("ticket",   False, "Ticket (Unfinity)"),
        "INFINITY": ("infinity", False, "Infinity"),
        "PT":       ("pt",       False, "Power/Toughness"),
        "SAGA":     ("saga",     False, "Saga"),
    }

    # --- Rareza ---
    RARITY = {
        "COMMON":      ("common",      False, "Common"),
        "UNCOMMON":    ("uncommon",    False, "Uncommon"),
        "RARE":        ("rare",        False, "Rare"),
        "MYTHIC":      ("mythic",      False, "Mythic Rare"),
        "SPECIAL":     ("special",     False, "Special"),
        "BONUS":       ("bonus",       False, "Bonus"),
        "TIMESHIFTED": ("timeshifted", False, "Timeshifted"),
    }

    # --- Día / Noche ---
    DAY_NIGHT = {
        "DAY":   ("day",   False, "Day"),
        "NIGHT": ("night", False, "Night"),
    }

    # --- DFC symbols ---
    DFC = {
        "DFC-IGNITE":       ("dfc-ignite",       False, "Spark Ignite"),
        "DFC-SPARK":        ("dfc-spark",        False, "Spark"),
        "DFC-MOON":         ("dfc-moon",         False, "Moon"),
        "DFC-EMRAKUL":      ("dfc-emrakul",      False, "Emrakul"),
        "DFC-ENCHANTMENT":  ("dfc-enchantment",  False, "Enchantment DFC"),
        "DFC-LESSON":       ("dfc-lesson",       False, "Lesson"),
        "DFC-LAND":         ("dfc-land",         False, "Land DFC"),
        "DFC-CREATURE":     ("dfc-creature",     False, "Creature DFC"),
        "DFC-PLANESWALKER": ("dfc-planeswalker", False, "Planeswalker DFC"),
        "DFC-SORCERY":      ("dfc-sorcery",      False, "Sorcery DFC"),
        "DFC-INSTANT":      ("dfc-instant",      False, "Instant DFC"),
        "DFC-ARTIFACT":     ("dfc-artifact",     False, "Artifact DFC"),
        "DFC-MOONELDRITCH": ("dfc-mooneldritch", False, "Moon Eldritch"),
    }

    # --- Contadores ---
    COUNTERS = {
        "COUNTER-P1P1":       ("counter-p1p1",       False, "+1/+1 counter"),
        "COUNTER-M1M1":       ("counter-m1m1",       False, "-1/-1 counter"),
        "COUNTER-CHARGE":     ("counter-charge",     False, "Charge counter"),
        "COUNTER-LOYALTY":    ("counter-loyalty",    False, "Loyalty counter"),
        "COUNTER-POISON":     ("counter-poison",     False, "Poison counter"),
        "COUNTER-ENERGY":     ("counter-energy",     False, "Energy counter"),
        "COUNTER-EXPERIENCE": ("counter-experience", False, "Experience counter"),
        "COUNTER-LORE":       ("counter-lore",       False, "Lore counter"),
        "COUNTER-LEVEL":      ("counter-level",      False, "Level counter"),
        "COUNTER-FADE":       ("counter-fade",       False, "Fade counter"),
        "COUNTER-FLAME":      ("counter-flame",      False, "Flame counter"),
        "COUNTER-TIME":       ("counter-time",       False, "Time counter"),
        "COUNTER-QUEST":      ("counter-quest",      False, "Quest counter"),
        "COUNTER-AGE":        ("counter-age",        False, "Age counter"),
        "COUNTER-DOOM":       ("counter-doom",       False, "Doom counter"),
        "COUNTER-STUDY":      ("counter-study",      False, "Study counter"),
        "COUNTER-VEST":       ("counter-vest",       False, "Vest counter"),
        "COUNTER-WISH":       ("counter-wish",       False, "Wish counter"),
        "COUNTER-BRICK":      ("counter-brick",      False, "Brick counter"),
        "COUNTER-GOLD":       ("counter-gold",       False, "Gold counter"),
        "COUNTER-SHIELD":     ("counter-shield",     False, "Shield counter"),
        "COUNTER-STUN":       ("counter-stun",       False, "Stun counter"),
    }

    # --- Nivel ---
    LEVEL = {
        "LEVEL":  ("level",  False, "Level"),
        "LEVELX": ("levelx", False, "Level X"),
    }

    @classmethod
    def get_all(cls):
        result = {}
        result.update(cls.COLORS)
        result.update(cls.GENERIC)
        result.update(cls.SPECIAL_MANA)
        result.update(cls.HYBRID)
        result.update(cls.HYBRID_GENERIC)
        result.update(cls.PHYREXIAN)
        result.update(cls.HALF)
        result.update(cls.ACTIONS)
        result.update(cls.PLANESWALKER)
        result.update(cls.CARD_SYMBOLS)
        result.update(cls.RARITY)
        result.update(cls.DAY_NIGHT)
        result.update(cls.DFC)
        result.update(cls.COUNTERS)
        result.update(cls.LEVEL)
        return result

    @classmethod
    def to_css(cls, symbol):
        """
        Convierte un símbolo de Magic a clases CSS de mana-font.
        Maneja lookup directo, híbridos, phyrexian y fallback.
        """
        s = symbol.upper().strip()
        all_symbols = cls.get_all()

        # Lookup directo — cubre todos los casos mapeados
        if s in all_symbols:
            css_suffix, is_cost, _ = all_symbols[s]
            cost_class = " ms-cost" if is_cost else ""
            return f"ms ms-{css_suffix}{cost_class}"

        # Híbridos dinámicos con slash no mapeados explícitamente
        if "/" in s:
            parts = s.split("/")

            # Phyrexian triple: W/U/P
            if "P" in parts and len(parts) == 3:
                colors = [p.lower() for p in parts if p != "P"]
                combined = "".join(colors) + "p"
                return f"ms ms-{combined} ms-cost ms-phyrexian"

            # Phyrexian doble: W/P o P/W
            if "P" in parts and len(parts) == 2:
                color = next((p for p in parts if p != "P"), "").lower()
                return f"ms ms-{color}p ms-cost ms-phyrexian"

            # Phyrexian alternativo: A/W
            if "A" in parts:
                color = next((p for p in parts if p != "A"), "").lower()
                return f"ms ms-a{color} ms-cost ms-phyrexian"

            # Half mana: H/W (alternativo a HW)
            if "H" in parts:
                color = next((p for p in parts if p != "H"), "").lower()
                return f"ms ms-h{color} ms-cost"

            # Híbrido genérico: 2/W, W/U, etc.
            combined = "".join(p.lower() for p in parts)
            return f"ms ms-{combined} ms-cost ms-split ms-duo"

        # Número genérico no mapeado
        if s.isdigit():
            return f"ms ms-{s} ms-cost"

        # Fallback
        return f"ms ms-{s.lower()} ms-cost"