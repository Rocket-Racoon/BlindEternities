"""
Controlled vocabularies for the Conflux card tagger.

Centralized so they double as documentation AND the validation whitelist.
To add or rename a tag, edit here in one place. Bump VOCABULARY_VERSION
whenever the meaning of a tag changes (so downstream consumers know to
re-tag affected cards).
"""
from typing import List, Tuple


VOCABULARY_VERSION = 1


FUNCTION_TAGS = {
    "removal-single":  "Destroys, exiles, or otherwise neutralizes ONE target permanent.",
    "sweeper":         "Removes multiple permanents at once (board wipe).",
    "burn":            "Deals direct damage to creatures or players.",
    "counterspell":    "Counters a spell on the stack.",
    "ramp":            "Accelerates mana (extra lands, mana rocks, mana dorks).",
    "fixing":          "Provides color fixing without real acceleration.",
    "card-draw":       "Draws extra cards.",
    "tutor":           "Searches the library for a specific card or type.",
    "discard":         "Forces opponents to discard.",
    "mill":            "Mills opponent's library.",
    "self-mill":       "Mills your own library on purpose.",
    "recursion":       "Returns cards from graveyard to hand or library.",
    "reanimation":     "Returns a creature from graveyard directly to play.",
    "protection":      "Grants hexproof / indestructible / ward / phasing-style protection.",
    "combat-trick":    "Instant-speed pump or combat-altering spell.",
    "finisher":        "A card whose role is to close out games.",
    "bomb":            "High-impact must-answer threat (typically 5+ mana).",
    "alt-win":         "Alternative or secondary win condition.",
    "lifegain":        "Gains life.",
    "lifeloss":        "Causes opponents to lose life (non-damage).",
    "token-generator": "Creates one or more tokens.",
    "anthem":          "Statically buffs your team.",
    "evasion":         "Grants or has flying, menace, unblockable, etc.",
    "extra-turn":      "Take additional turns.",
    "copy":            "Copies spells or permanents.",
    "bounce":          "Returns a permanent to its owner's hand.",
    "flicker":         "Exiles and returns a permanent (ETB abuse).",
    "stax":            "Taxes or restricts opponents' actions.",
    "lock":            "Prevents opponents from playing the game normally.",
    "utility":         "Flexible role, multiple modes, or general utility.",
    "enabler":         "Sets up a synergy without paying off on its own.",
    "payoff":          "Rewards a strategy by capitalizing on a synergy.",
}


THEME_TAGS = {
    "aristocrats":         "Rewards sacrificing or losing creatures.",
    "tribal":              "Cares about a creature type. Use 'tribal:<type>' subtag (e.g. 'tribal:elf').",
    "mill":                "Wins or grinds by emptying opponents' libraries.",
    "self-mill":           "Fills own graveyard as a strategy.",
    "reanimator":          "Cheats big creatures into play from the graveyard.",
    "tokens":              "Go-wide token strategy.",
    "voltron":             "Pumps a single creature to lethal damage.",
    "spells-matter":       "Prowess, magecraft, storm-lite — many instants/sorceries.",
    "artifacts-matter":    "Cares about artifact count or artifact synergies.",
    "enchantments-matter": "Enchantress / constellation strategies.",
    "+1/+1-counters":      "Cares about +1/+1 counters.",
    "-1/-1-counters":      "Cares about -1/-1 counters / wither / infect.",
    "lifegain-matters":    "Triggers on or rewards gaining life.",
    "sacrifice":           "Wants to sacrifice permanents for value.",
    "blink":               "Flicker / ETB-abuse strategies.",
    "landfall":            "Triggers when lands enter the battlefield.",
    "lands-matter":        "Cares about lands as a resource (beyond landfall).",
    "graveyard":           "Broad graveyard-as-resource strategies.",
    "equipment":           "Equipment-focused strategy.",
    "auras":               "Aura-focused strategy.",
    "combo":               "Part of a known infinite or near-infinite combo line.",
    "control":             "Reactive, attrition-oriented archetype.",
    "aggro":               "Fast, low-curve, damage-focused archetype.",
    "midrange":            "Efficient 2-5 mana threats and answers.",
    "big-mana":            "Ramps high to cast large spells.",
    "stax":                "Locks the game to prevent opponents playing.",
    "wheels":              "Mass discard/redraw effects.",
    "storm":               "Cast many spells in a turn for a payoff.",
    "treasures":           "Generates or cares about Treasure tokens.",
    "vehicles":            "Crew/vehicle-based strategy.",
    "energy":              "Uses energy counters.",
    "proliferate":         "Built around proliferating counters.",
}


def validate_tags(function_tags, theme_tags) -> Tuple[List[str], List[str]]:
    """
    Drop tags not in the controlled vocabulary.
    Allow `tribal:<type>` subtags (e.g. 'tribal:elf', 'tribal:goblin').
    Deduplicate while preserving order.
    """
    seen_func = set()
    valid_func: List[str] = []
    for t in function_tags or []:
        if isinstance(t, str) and t in FUNCTION_TAGS and t not in seen_func:
            valid_func.append(t)
            seen_func.add(t)

    seen_theme = set()
    valid_theme: List[str] = []
    for t in theme_tags or []:
        if not isinstance(t, str):
            continue
        if t in THEME_TAGS and t not in seen_theme:
            valid_theme.append(t)
            seen_theme.add(t)
        elif t.startswith("tribal:") and len(t) > 7 and t not in seen_theme:
            valid_theme.append(t)
            seen_theme.add(t)

    return valid_func, valid_theme


# ──────────────────────────────────────────────
# Oracle-text sanity check
# Each entry: {tag: [list of regex patterns; tag survives only if ANY matches]}
# Only tags listed here are policed — for the rest, the LLM has free rein.
# Patterns are case-insensitive. Use only well-known oracle phrasings.
# ──────────────────────────────────────────────
_ORACLE_REQUIREMENTS = {
    "ramp": [
        r"\badd\b.*\bmana\b",
        r"\badd\b.*\{[wubrgcx0-9]\}",
        r"\bsearch your library for.*\bland\b",
        r"\bput.*\bland.*\bonto the battlefield\b",
        r"\buntap.*\bland\b",
        r"\buntap target.*(?:permanent|artifact|creature).*\bmana\b",
        r"create.*\btreasure\b.*token",
        r"\beach.*\bland.*\bproduces\b",
    ],
    "fixing": [
        r"\bany color\b",
        r"\bof any\b.*\bcolor\b",
        r"\badd\b.*\{[wubrg]\}.*\bor\b.*\{[wubrg]\}",
        # Tutoring or putting a basic land onto the battlefield always fixes.
        r"\bsearch.*\bbasic land\b",
        r"\bput.*\bbasic land.*\bbattlefield\b",
        r"\bbasic land.*(plains|island|swamp|mountain|forest)\b",
    ],
    "card-draw": [
        r"\bdraw.*\bcard",
        r"\bdraws?\s+(?:a|two|three|four|x|that many)\s+cards?",
    ],
    "counterspell": [
        r"\bcounter target\b",
        r"\bcounter that\b",
        r"\bcounter all\b",
    ],
    "tutor": [
        r"\bsearch your library\b",
    ],
    "discard": [
        r"\b(?:target player|each opponent|opponent|each player)\b.*\bdiscards?\b",
    ],
    "mill": [
        r"\b(?:target player|each opponent|opponent|each player)\b.*\b(?:mills?|puts? the top.*into.*graveyard)\b",
        r"\bmills?\b",
    ],
    "self-mill": [
        r"\byou mill\b",
        r"\bput the top.*your library.*into your graveyard\b",
    ],
    "recursion": [
        r"\bfrom (?:your |a )?graveyard\b.*\b(?:to your hand|on top of your library|to your library)\b",
        r"\breturn.*\bgraveyard.*\bhand\b",
    ],
    "reanimation": [
        r"\breturn.*\bcreature.*\bgraveyard.*\bbattlefield\b",
        r"\bput.*\bcreature.*\bgraveyard.*onto the battlefield\b",
    ],
    "burn": [
        r"\bdeals?\b.*\bdamage\b",
    ],
    "removal-single": [
        r"\b(?:destroy|exile)\b\s+(?:target|that)\b",
        r"\breturn target.*to.*hand\b",
        r"\btarget creature.*-\d/-\d",
        r"\btarget (?:player|opponent) sacrifices\b",
        # Damage-based removal: Lightning Bolt, Doom Blade-style, etc.
        r"\bdeals?\b.*\bdamage\b.*\btarget\b",
        r"\bdeals?\b.*\bdamage\b.*\bany target\b",
        # Counter-based removal (-X/-X to a single creature, infect, etc.)
        r"\btarget creature gets? -\d",
    ],
    "sweeper": [
        r"\b(?:destroy|exile)\b\s+(?:all|each)\b",
        r"\beach (?:creature|nonland|player)\b.*(?:sacrifices?|loses?)\b",
        r"\b-x/-x\b.*\beach\b",
        # Damage-based wipes: Anger of the Gods, Pyroclasm, Blasphemous Act.
        r"\bdeals?\b.*\bdamage\b.*\beach\b",
        r"\bdeals?\b.*\bdamage\b.*\ball\b",
        # Stat-based wipes: Languish ("All creatures get -X/-X").
        r"\b(?:all|each)\b.*creatures?\b.*\bgets?\b.*-\d",
    ],
    "protection": [
        r"\bhexproof\b",
        r"\bindestructible\b",
        r"\bward\b",
        r"\bshroud\b",
        r"\bphasing\b",
        r"\bcan't be (?:countered|targeted|destroyed)\b",
        r"\bprotection from\b",
    ],
    "extra-turn": [
        r"\bextra turn\b",
        r"\btake an? (?:additional|extra) turn\b",
    ],
    "copy": [
        r"\bcopy\b.*\b(?:spell|permanent|creature|target)\b",
    ],
    "bounce": [
        r"\breturn target\b.*\bto its owner'?s? hand\b",
        r"\breturn (?:all|each).*\bto (?:its|their) owners?'?s? hands?\b",
    ],
    "flicker": [
        r"\bexile\b.*\breturn (?:it|that card)\b.*\bbattlefield\b",
        r"\bexile.*then return.*battlefield\b",
    ],
    "evasion": [
        r"\bflying\b",
        r"\bmenace\b",
        r"\bunblockable\b",
        r"\bcan't be blocked\b",
        r"\btrample\b",
        r"\bshadow\b",
        r"\bskulk\b",
        r"\bhorsemanship\b",
        r"\bfear\b",
        r"\bintimidate\b",
        r"\bflanking\b",
    ],
    "token-generator": [
        r"\bcreate\b.*\btoken\b",
        r"\bput.*\btoken.*onto the battlefield\b",
    ],
    "anthem": [
        r"\bcreatures? you control\b.*\bgets?\b.*\+\d/\+\d",
        r"\bother creatures? you control\b.*\bget\b.*\+\d/\+\d",
    ],
    "lifegain": [
        r"\bgain\b.*\blife\b",
        r"\byou gain\b.*\b\d+\b.*\blife\b",
    ],
    "lifeloss": [
        r"\b(?:each opponent|target player|opponent)\b.*\bloses?\b.*\blife\b",
    ],
}


def sanity_check_against_oracle(
    function_tags: List[str],
    theme_tags: List[str],
    oracle_text: str,
) -> Tuple[List[str], List[str], List[str]]:
    """
    Drop function tags that lack a supporting phrase in the oracle text.
    Theme tags aren't policed (too contextual). Returns (kept_func, kept_theme, dropped_func).
    Pass an empty `oracle_text` and we skip the check.
    """
    import re
    if not oracle_text:
        return function_tags, theme_tags, []

    text = oracle_text.lower()
    kept: List[str] = []
    dropped: List[str] = []
    for tag in function_tags:
        patterns = _ORACLE_REQUIREMENTS.get(tag)
        if patterns is None:
            kept.append(tag)
            continue
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            kept.append(tag)
        else:
            dropped.append(tag)
    return kept, theme_tags, dropped


FEW_SHOT_EXAMPLES = """
EXAMPLES (study these — your output must follow the same logic):

Card:
  Name: Lightning Bolt
  Mana cost: {R}
  Type: Instant
  Oracle text: Lightning Bolt deals 3 damage to any target.
Output:
  {"function_tags": ["burn", "removal-single"], "theme_tags": [], "reasoning": "Direct damage that can kill a small creature, planeswalker, or face."}

Card:
  Name: Sol Ring
  Mana cost: {1}
  Type: Artifact
  Oracle text: {T}: Add {C}{C}.
Output:
  {"function_tags": ["ramp"], "theme_tags": ["artifacts-matter"], "reasoning": "Adds two colorless mana for a one-mana investment — the canonical ramp rock."}

Card:
  Name: +2 Mace
  Mana cost: {2}
  Type: Artifact — Equipment
  Oracle text: Equipped creature gets +2/+2. Equip {2}.
Output:
  {"function_tags": [], "theme_tags": ["equipment"], "reasoning": "A vanilla equipment with no removal, draw, or mana — the +2 in the name is a stat buff, NOT mana."}

Card:
  Name: Cultivate
  Mana cost: {2}{G}
  Type: Sorcery
  Oracle text: Search your library for up to two basic land cards, reveal those cards, put one onto the battlefield tapped and the other into your hand, then shuffle.
Output:
  {"function_tags": ["ramp", "fixing", "tutor"], "theme_tags": ["lands-matter"], "reasoning": "Land tutor that ramps (one onto battlefield) and fixes (search by basic type)."}

Card:
  Name: Solemn Simulacrum
  Mana cost: {4}
  Type: Artifact Creature — Golem
  Oracle text: When this creature enters, you may search your library for a basic land card, put it onto the battlefield tapped, then shuffle. When this creature dies, you draw a card.
Output:
  {"function_tags": ["ramp", "card-draw", "fixing"], "theme_tags": ["artifacts-matter"], "reasoning": "ETB ramps a tapped basic land and draws on death; classic value engine."}

Card:
  Name: Wrath of God
  Mana cost: {2}{W}{W}
  Type: Sorcery
  Oracle text: Destroy all creatures. They can't be regenerated.
Output:
  {"function_tags": ["sweeper"], "theme_tags": ["control"], "reasoning": "Mass creature removal — the textbook board wipe."}
"""


def build_system_prompt() -> str:
    func_block  = "\n".join(f"  - {k}: {v}" for k, v in FUNCTION_TAGS.items())
    theme_block = "\n".join(f"  - {k}: {v}" for k, v in THEME_TAGS.items())
    return f"""You are an expert Magic: The Gathering analyst. You classify cards by their MECHANICAL FUNCTION and their ARCHETYPE THEME.

You read ORACLE TEXT, not card names. The card's name and flavor are irrelevant — only the rules text in the "Oracle text" field matters. A card called "+2 Mace" or "Mana Drain" gets tagged based on what its oracle text actually does, not what the name suggests.

You return tags drawn ONLY from the controlled vocabularies below. Do not invent new tags. The single exception is the `tribal:<type>` subtag (e.g. `tribal:elf`, `tribal:goblin`) — always pair it with the bare `tribal` tag when used.

FUNCTION TAGS — what the card *does* mechanically. Pick all that apply, usually 1–4. If the oracle text doesn't justify any function tag, return an empty list:
{func_block}

THEME TAGS — which archetype(s) the card fits into. Pick all that apply, usually 0–3. If the card is purely generic and fits no archetype, return an empty list:
{theme_block}

HARD RULES (violating these is wrong, no exceptions):
- `ramp` REQUIRES the oracle text to add mana, untap a mana producer, or put a land onto the battlefield. Equipment that grants +X/+X to a creature is NOT ramp. Pump spells are NOT ramp. Anything that just modifies stats is NOT ramp regardless of how big the number is.
- `card-draw` REQUIRES the oracle text to contain "draw" referencing your hand. Effects that look at the top of the library or scry are NOT card-draw on their own.
- `counterspell` REQUIRES the oracle text to say "counter target [spell|ability]". Stifle-style ability counters still qualify.
- `tutor` REQUIRES the oracle text to say "search your library". Mere library-manipulation (scry, surveil, look at top N) is NOT a tutor.
- `removal-single` REQUIRES the oracle text to destroy, exile, sacrifice, or send-to-hand ONE specified target permanent.
- `sweeper` REQUIRES removing multiple permanents ("destroy all creatures", "exile each nonland permanent", etc.).
- `burn` REQUIRES dealing damage from the spell/ability itself.
- `discard` (function) means forcing OPPONENTS to discard. Self-discard for value is NOT this tag — that's `enabler` or theme `wheels`/`graveyard` if applicable.
- `mill` means putting cards from an OPPONENT's library into the graveyard. Putting cards from YOUR library into your graveyard is `self-mill`.
- `recursion` returns cards from a graveyard to hand or library; `reanimation` returns a creature from a graveyard directly to the battlefield.
- `protection` means hexproof, indestructible, ward, phasing, shroud, or "creature can't be targeted/destroyed" — NOT mere stat buffs.
- `anthem` is a STATIC effect that buffs your team. A spell that pumps for one turn is `combat-trick`, not `anthem`.
- `bomb` vs `finisher`: a bomb is a must-answer threat; a finisher's text actually closes games (Craterhoof, Torment of Hailfire, Approach of the Second Sun).
- A vanilla creature (no relevant abilities) gets NO function tags and NO theme tags.
- Lands: tag `fixing` if they just tap for colored mana; tag `ramp` only if they actually accelerate (produce 2+ mana, untap for free, etc.). Pure dual lands are `fixing`, not ramp.

EVIDENCE RULE: For every tag you assign, you must be able to point to a specific phrase in the oracle text that justifies it. If you can't find such a phrase, do not assign the tag.
{FEW_SHOT_EXAMPLES}
You MUST respond with ONLY valid JSON, no prose, no markdown fences. Schema:
{{
  "function_tags": ["<tag>", "..."],
  "theme_tags":    ["<tag>", "..."],
  "reasoning":     "<one sentence (≤30 words) explaining the most important tag choices, citing the oracle text phrase you relied on>"
}}
"""
