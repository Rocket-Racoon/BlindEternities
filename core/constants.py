# core/constants.py
from django.db import models



# --- Formats ---
class MagicFormat(models.TextChoices):
    STANDARD  = "standard",  "Standard"
    PIONEER   = "pioneer",   "Pioneer"
    MODERN    = "modern",    "Modern"
    LEGACY    = "legacy",    "Legacy"
    VINTAGE   = "vintage",   "Vintage"
    COMMANDER = "commander", "Commander"
    PAUPER    = "pauper",    "Pauper"
    DRAFT     = "draft",     "Draft"
    SEALED    = "sealed",    "Sealed"


# --- Colors ---
class MagicColor(models.TextChoices):
    WHITE     = "W", "Blanco"
    BLUE      = "U", "Azul"
    BLACK     = "B", "Negro"
    RED       = "R", "Rojo"
    GREEN     = "G", "Verde"
    COLORLESS = "C", "Colorless"


# --- Rarities ---
class CardRarity(models.TextChoices):
    COMMON    = "common",   "Common"
    UNCOMMON  = "uncommon", "Uncommon"
    RARE      = "rare",     "Rare"
    MYTHIC    = "mythic",   "Mythic Rare"
    SPECIAL   = "special",  "Special"
    BONUS     = "bonus",    "Bonus"
    TIMESHIFTED = "timeshifted", "Timeshifted"


# --- Parts & Layouts ---
class CardPart(models.TextChoices):
    NAME                = 'name',               'Name'
    MANA_COST           = 'mana_cost',          'Mana Cost'
    COLOR               = 'color',              'Color'
    ILLUSTRATION        = 'illustration',       'Illustration'
    INDICATOR           = 'color_indicator',    'Color Indicator'
    TYPELINE            = 'type_line',          'Type Line'
    EXPANSIONSYMBOL     = 'expansion_symbol',   'Expansion Symbol'
    TEXTBOX             = 'text_box',           'Text Box'
    POWER_TOUGHNESS     = 'power_toughness',    'Power/Toughness'
    LOYALTY             = 'loyalty',            'Loyalty'
    DEFENSE             = 'defense',            'Defense'
    HANDMOD             = 'hand_modifier',      'Hand Modifier'
    LIFEMOD             = 'life_modifier',      'Life Modifier'
    INFORMATION         = 'information',        'Information'

class CardLayout(models.TextChoices):
    NORMAL               = "normal",               "Normal"
    SPLIT                = "split",                "Split"
    FLIP                 = "flip",                 "Flip"
    TRANSFORM            = "transform",            "Transform"
    MODAL_DFC            = "modal_dfc",            "Modal DFC"
    MELD                 = "meld",                 "Meld"
    LEVELER              = "leveler",              "Leveler"
    CLASS                = "class",                "Class"
    CASE                 = "case",                 "Case"
    SAGA                 = "saga",                 "Saga"
    ADVENTURE            = "adventure",            "Adventure"
    PLANAR               = "planar",               "Planar"
    SCHEME               = "scheme",               "Scheme"
    VANGUARD             = "vanguard",             "Vanguard"
    TOKEN                = "token",                "Token"
    DOUBLE_FACED_TOKEN   = "double_faced_token",   "Double Faced Token"
    EMBLEM               = "emblem",               "Emblem"
    AUGMENT              = "augment",              "Augment"
    HOST                 = "host",                 "Host"
    ART_SERIES           = "art_series",           "Art Series"
    REVERSIBLE_CARD      = "reversible_card",      "Reversible Card"
    BATTLE               = "battle",               "Battle"
    ATTRACTION           = "attraction",            "Attraction"


# --- Set Types ---
class CardSetType(models.TextChoices):
    CORE             = "core",             "Core Set"
    EXPANSION        = "expansion",        "Expansion"
    MASTERS          = "masters",          "Masters"
    ALCHEMY          = "alchemy",          "Alchemy"
    MASTERPIECE      = "masterpiece",      "Masterpiece"
    ARSENAL          = "arsenal",          "Arsenal"
    FROM_THE_VAULT   = "from_the_vault",   "From the Vault"
    SPELLBOOK        = "spellbook",        "Spellbook"
    PREMIUM_DECK     = "premium_deck",     "Premium Deck"
    DUEL_DECK        = "duel_deck",        "Duel Deck"
    DRAFT_INNOVATION = "draft_innovation", "Draft Innovation"
    TREASURE_CHEST   = "treasure_chest",   "Treasure Chest"
    COMMANDER        = "commander",        "Commander"
    PLANECHASE       = "planechase",       "Planechase"
    ARCHENEMY        = "archenemy",        "Archenemy"
    VANGUARD         = "vanguard",         "Vanguard"
    UNSET            = "un_set", "Un-Set"
    FUNNY            = "funny",            "Funny"
    STARTER          = "starter",          "Starter"
    JUMPSTART        = "jumpstart", "Jumpstart"
    BOX              = "box",              "Box"
    PROMO            = "promo",            "Promo"
    TOKEN            = "token",            "Token"
    MEMORABILIA      = "memorabilia",      "Memorabilia"
    MINIGAME         = "minigame",         "Minigame"
    ETERNAL          = "eternal", "Eternal"
    HEROES           = "heroes_of_the_realm", "Heroes of the Realm"
    FRONTCARDS       = "front_cards", "Jumpstart Front Cards" 
    PLANAR           = "planar_deck", "Planar Deck"
    SCHEMES          = "schemes_deck", "Scheme Deck"
    SCENE            = "scene_box", "Scene Box"
    CHAMPIONSHIP_DECK = "championship_deck",     "Championship Deck"

# --- Printing Topics ---
class BorderColor(models.TextChoices):
    BLACK      = "black",      "Black"
    WHITE      = "white",      "White"
    SILVER     = "silver",     "Silver"
    GOLD       = "gold",       "Gold"
    BORDERLESS = "borderless", "Borderless"


class CardFinish(models.TextChoices):
    NONFOIL         = "nonfoil", "Non-Foil"
    FOIL            = "foil",    "Foil"
    PREMODERN       = 'premodern', 'Pre-Modern Foil'
    AMPERSAND       = 'ampersand', 'Ampersand Foil'
    CONFETTI        = 'confetti', 'Confetti Foil'
    DOUBLERAINBOW   = 'doublerainbow', 'Double-Rainbow Foil'
    FIRSTPLACE      = 'firstplace', 'First Place Foil'
    FRACTURE        = 'fractur', 'Fractur Foil'
    ETCHED          = "etched",  "Etched"
    GALAXY          = 'galaxy', 'Galaxy Foil'
    GILDED          = 'gilded', 'Gilded Foil'
    GLOSSY          = "glossy",  "Glossy"
    HALO            = 'halo', 'Halo Foil'
    INVISIBLE       = 'invisible', 'Invisible Ink Foil'
    MANA            = 'mana', 'Mana Foil'
    NEONINK         = 'neonink', 'Neon Ink Foil'
    OILSLICK        = 'oilslick', 'Oil Slick Raised Foil'
    RIPPLE          = 'ripple', 'Ripple Foil'
    SILVERSCREEN    = 'silverscreen', 'Silver Screen Foil'
    STEPCOMPLETE    = 'stepcomplete', 'Step & Complete Foil'
    SURGE           = 'surge', 'Surge Foil'
    TEXTURED        = 'textured', 'Textured Foil'
    VAULT           = 'vault', 'From the Vault Foil'
    

class CardWatermark(models.TextChoices):
    # Lore
    ABZAN               = "Abzan", "Abzan"
    ATARKA              = "Atarka", "Atarka"
    AZORIUS             = "Azorius", "Azorius"
    BOROS               = "Boros", "Boros"
    BROKERS             = "Brokers", "Brokers"
    CABARETTI           = "Cabaretti", "Cabaretti"
    DESPARK             = "Desparked", "Desparked"
    DIMIR               = "Dimir", "Dimir"
    DROMOKA             = "Dromoka", "Dromoka"
    GOLGARI             = "Golgari", "Golgari"
    GRUUL               = "Gruul", "Gruul"
    IZZET               = "Izzet", "Izzet"
    JESKAI              = "Jeskai", "Jeskai"
    KOLAGHAN            = "Kolaghan", "Kolaghan"
    LOREHOLD            = "Lorehold", "Lorehold"
    MAESTROS            = "Maestros", "Maestros"
    MARDU               = "Mardu", "Mardu"
    MIRRAN              = "Mirran", "Mirran"
    OBSCURA             = "Obscura", "Obscura"
    OJUTAI              = "Ojutai", "Ojutai"
    ORZHOV              = "Orzhov", "Orzhov"
    PHYREXIAN           = "Phyrexian", "Phyrexian"
    PRISMARI            = "Prismari", "Prismari"
    QUANDRIX            = "Quandrix", "Quandrix"
    RAKDOS              = "Rakdos", "Rakdos"
    RIVETEERS           = "Riveteers", "Riveteers"
    SELESNYA            = "Selesnya", "Selesnya"
    SILUMGAR            = "Silumgar", "Silumgar"
    SILVERQUILL         = "Silverquill", "Silverquill"
    SIMIC               = "Simic", "Simic"
    SULTAI              = "Sultai", "Sultai"
    TARKIR              = "Tarkir", "Tarkir"
    TEMUR               = "Temur", "Temur"
    WITHERBLOOM         = "Witherbloom", "Witherbloom"
    # Game
    CONSPIRACY          = "Conspiracy", "Conspiracy"
    FORTELL             = "Fortell", "Fortell"
    PLANESWALKER        = "Planeswalker", "Planeswalker"
    SET                 = "Set", "Set"
    # Un-game
    AGENTSSNEAK         = "Agentsofsneak", "Agents of S.N.E.A.K."
    CROSSBREEDLABS      = "Crossbreed Labs", "Crossbreed Labs"
    GOBLINEXPLOSIONEERS = "Goblin Explosioneers", "Goblin Explosioneers"
    LEAGUEDOOM          = "League of Dastarly Doom", "League of Dastarly Doom"
    ORDERWIDGET         = "Order of the Widget", "Order of the Widget"
    # Universe Beyond
    DND                 = "D&D", "D&D"
    TRANSFORMERS        = "Transformers", "Transformers"
    AIRNOMADS           = "Air Nomads", "Air Nomads"
    EARTHKINGDOM        = "Earth Kingdom", "Earth Kingdom"
    FIRENATION          = "Fire Nation", "Fire Nation"
    WATERTRIBE          = "Water Tribe", "Water Tribe"
    # Tournament
    DCI                 = "DCI", "DCI"
    GRANDPRIX           = "Grand Prix", "Grand Prix"
    JAPANJR             = "Japan Jr", "Japan Jr"
    JR                  = "Junior", "Junior Superseries"
    JRAPC               = "Junior APC", "Junior APC"
    JREU                = "Junior Europe", "Junior Europe"
    PROTOUR             = "Pro Tour", "Pro Tour"
    WOTC                = "WOTC", "WOTC"
    WPN                 = "WPN", "WPN" 
    # Promotion
    ARENA               = "Arena", "Arena"
    COLORPIE            = "Colorpie", "Colorpie"
    FLAVOR              = "Flavor", "Flavor"
    FNM                 = "FNM", "FNM"
    HEROSPATH           = "Heros Path", "Heros Path"
    JUDGE               = "Judge Academy", "Judge Academy"
    MAGICFEST           = "MagicFest", "MagicFest"
    MPS                 = "MPS", "MPS"
    MTG                 = "MTG", "MTG"
    MTG10               = "MTG10", "MTG10"
    MTG15               = "MTG15", "MTG15"
    SCOLARSHIP          = "Scholarship", "Scholarship"
    # IPs
    COROCORO            = "CoroCoro", "CoroCoro"
    CUTIEMARK           = "Cutie Mark", "Cutie Mark"
    DANGEKI             = "Dengekimaho", "Dengekimaoh"
    NERF                = "Nerf", "Nerf"
    TRUMPKATSUMAI       = "Trumpkatsumai", "Trumpkatsumai"

# --- Card Typelines ---
class CardSupertype(models.TextChoices):
    BASIC     = "Basic",     "Basic"
    LEGENDARY = "Legendary", "Legendary"
    ONGOING   = "Ongoing",   "Ongoing"
    SNOW      = "Snow",      "Snow"
    TOKEN     = "Token",     "Token"
    WORLD     = "World",     "World"
    ELITE     = "Elite",     "Elite"


class CardType(models.TextChoices):
    ARTIFACT     = "Artifact",     "Artifact"
    BATTLE       = "Battle",       "Battle"
    CONSPIRACY   = "Conspiracy",   "Conspiracy"
    CREATURE     = "Creature",     "Creature"
    DUNGEON      = "Dungeon",      "Dungeon"
    ENCHANTMENT  = "Enchantment",  "Enchantment"
    INSTANT      = "Instant",      "Instant"
    KINDRED      = "Kindred",      "Kindred"
    LAND         = "Land",         "Land"
    PHENOMENON   = "Phenomenon",   "Phenomenon"
    PLANE        = "Plane",        "Plane"
    PLANESWALKER = "Planeswalker", "Planeswalker"
    SCHEME       = "Scheme",       "Scheme"
    SORCERY      = "Sorcery",      "Sorcery"
    TRIBAL       = "Tribal",       "Tribal"
    VANGUARD     = "Vanguard",     "Vanguard"
    EMBLEM       = "Emblem",     "Emblem"
    HERO         = "Hero",       "Hero"


class ArtifactType(models.TextChoices):
    """
    Subtipos específicos para Artefactos.
    CR 205.3g
    """
    ATTRACTION      = "Attraction", "Attraction"
    BLOOD           = "Blood", "Blood"
    BOBBLEHEAD      = "Bobblehead", "Bobblehead"
    CLUE            = "Clue", "Clue"
    CONTRAPTION     = "Contraption", "Contraption"
    EQUIPMENT       = "Equipment", "Equipment"
    FOOD            = "Food", "Food"
    FORTIFICATION   = "Fortification", "Fortification"
    GOLD            = "Gold", "Gold"
    INCUBATOR       = "Incubator", "Incubator"
    INFINITY        = "Infinity", "Infinity"
    JUNK            = "Junk", "Junk"
    MAP             = "Map", "Map"
    POWERSTONE      = "Powerstone", "Powerstone"
    STONE           = "Stone", "Stone"
    TERMINUS        = "Terminus", "Terminus"
    TREASURE        = "Treasure", "Treasure"
    VEHICLE         = "Vehicle", "Vehicle"
    SPACECRAFT      = "Spacecraft", "Spacecraft"


class BattleType(models.TextChoices):
    """
    Subtipos específicos para Batallas.
    CR 205.3h
    """
    SIEGE = "Siege", "Siege"


class EnchantmentType(models.TextChoices):
    """
    Subtipos para Encantamientos. 
    CR 205.3h
    """
    AURA        = "Aura", "Aura"
    BACKGROUND  = "Background", "Background"
    CARTOUCHE   = "Cartouche", "Cartouche"
    CASE        = "Case", "Case"
    CLASS       = "Class", "Class"
    CURSE       = "Curse", "Curse"
    ROLE        = "Role", "Role"
    ROOM        = "Room", "Room"
    RUNE        = "Rune", "Rune"
    SAGA        = "Saga", "Saga"
    SHARD       = "Shard", "Shard"
    SHRINE      = "Shrine", "Shrine"


class LandType(models.TextChoices):
    """
    Subtipos para Tierras (Básicas y No Básicas). 
    CR 205.3i
    """
    # Tipos básicos
    PLAINS      = "Plains", "Plains"
    ISLAND      = "Island", "Island"
    SWAMP       = "Swamp", "Swamp"
    MOUNTAIN    = "Mountain", "Mountain"
    FOREST      = "Forest", "Forest"
    # Tipos no básicos
    CAVE        = "Cave", "Cave"
    CLOUD       = "Cloud", "Cloud"
    DESERT      = "Desert", "Desert"
    GATE        = "Gate", "Gate"
    LAIR        = "Lair", "Lair"
    LOCUS       = "Locus", "Locus"
    MINE        = "Mine", "Mine"
    SPHERE      = "Sphere", "Sphere"
    PLANET      = "Planet", "Planet"
    POWERPLANT  = "Power-Plant", "Power-Plant"
    TOWER       = "Tower", "Tower"
    TOWN        = "Town", "Town"
    URZAS       = "Urza's", "Urza's"


class BasicLandType(models.TextChoices):
    """Subtipos para Tierras Básicas."""
    PLAINS      = "Plains", "Plains"
    ISLAND      = "Island", "Island"
    SWAMP       = "Swamp", "Swamp"
    MOUNTAIN    = "Mountain", "Mountain"
    FOREST      = "Forest", "Forest"
    WASTES      = "Wastes", "Wastes"
    # Snow Lands
    SNOW_PLAINS     = "Snow-Covered Plains", "Snow-Covered Plains"
    SNOW_ISLAND     = "Snow-Covered Island", "Snow-Covered Island"
    SNOW_SWAMP      = "Snow-Covered Swamp", "Snow-Covered Swamp"
    SNOW_MOUNTAIN   = "Snow-Covered Mountain", "Snow-Covered Mountain"
    SNOW_FOREST     = "Snow-Covered Forest", "Snow-Covered Forest"
    
    
class SpellType(models.TextChoices):
    """
    Subtipos para Instants y Sorceries. 
    CR 205.3i
    """
    ADVENTURE   = "Adventure", "Adventure"
    ARCANE      = "Arcane", "Arcane"
    CHORUS      = "Chorus", "Chorus"
    LESSON      = "Lesson", "Lesson"
    OMEN        = "Omen", "Omen"
    TRAP        = "Trap", "Trap"


class PlaneswalkerType(models.TextChoices):
    """
    Subtipos de Planeswalker.
    CR ***.**
    """
    ABIAN       = "Abian", "Abian"
    AJANI       = "Ajani", "Ajani"
    AMINATOU    = "Aminatou", "Aminatou"
    ANGRATH     = "Angrath", "Angrath"
    ARLINN      = "Arlinn", "Arlinn"
    ASHIOK      = "Ashiok", "Ashiok"
    BASRI       = "Basri", "Basri"
    BOLAS       = "Bolas", "Bolas"
    CALIX       = "Calix", "Calix"
    CHANDRA     = "Chandra", "Chandra"
    DACK        = "Dack", "Dack"
    DAKKON      = "Dakkon", "Dakkon"
    DARETTI     = "Daretti", "Daretti"
    DAVRIEL     = "Davriel", "Davriel"    
    DIHADA      = "Dihada", "Dihada"
    DOMRI       = "Domri", "Domri"
    DOVIN       = "Dovin", "Dovin"    
    ELSPETH     = "Elspeth", "Elspeth"
    ERSTA       = "Ersta", "Ersta"
    ESTRID      = "Estrid", "Estrid"
    FREYALISE   = "Freyalise", "Freyalise"
    GARRUK      = "Garruk", "Garruk"
    GIDEON      = "Gideon", "Gideon"
    GRIST       = "Grist", "Grist"
    GUFF        = "Guff", "Guff"
    HUATLI      = "Huatli", "Huatli"
    JACE        = "Jace", "Jace"
    JARED       = "Jared", "Jared"
    JAYA        = "Jaya", "Jaya"
    JESKA       = "Jeska", "Jeska"
    KAITO       = "Kaito", "Kaito"
    KARN        = "Karn", "Karn"
    KASMINA     = "Kasmina", "Kasmina"
    KAYA        = "Kaya", "Kaya"
    KIORA       = "Kiora", "Kiora"
    KOTH        = "Koth", "Koth"
    LILIANA     = "Liliana", "Liliana"
    LUKKA       = "Lukka", "Lukka"
    LUXIOR      = "Luxior", "Luxior"
    NAHIRI      = "Nahiri", "Nahiri"
    NARSET      = "Narset", "Narset"
    NIKO        = "Niko", "Niko"
    NISSA       = "Nissa", "Nissa"
    NIXILIS     = "Nixilis", "Nixilis"
    OKO         = "Oko", "Oko"
    QUINTORIUS  = "Quintorius", "Quintorius"
    RAL         = "Ral", "Ral"
    ROWAN       = "Rowan", "Rowan"
    SAHEELI     = "Saheeli", "Saheeli"
    SAMUT       = "Samut", "Samut"
    SARKHAN     = "Sarkhan", "Sarkhan"
    SERRA       = "Serra", "Serra"
    SIVITRI     = "Sivitri", "Sivitri"
    SORIN       = "Sorin", "Sorin"
    SZAT        = "Szat", "Szat"
    TAMIYO      = "Tamiyo", "Tamiyo"
    TASHA       = "Tasha", "Tasha"
    TEFERI      = "Teferi", "Teferi"
    TEYO        = "Teyo", "Teferi"
    TEZZERET    = "Tezzeret", "Tezzeret"
    TIBALT      = "Tibalt", "Tibalt"
    TYVAR       = "Tyvar", "Tyvar"
    UGIN        = "Ugin", "Ugin"
    URZA        = "Urza", "Urza"
    VENSER      = "Venser", "Venser"
    VIVIEN      = "Vivien", "Vivien"
    VRASKA      = "Vraska", "Vraska"
    VRONOS      = "Vronos", "Vronos"
    WANDERER    = "Wanderer", "Wanderer"
    WILL        = "Will", "Will"
    WINDGRACE   = "Windgrace", "Windgrace"
    WRENN       = "Wrenn", "Wrenn"
    XENAGOS     = "Xenagos", "Xenagos"
    YANGGU      = "Yanggu", "Yanggu"
    YANLING     = "Yanling", "Yanling"
    # Un-games
    BOB         = "B.O.B.", "B.O.B."
    COMET       = "Comet", "Comet"
    DUCK        = "Duck", "Duck"
    DUNGEON     = "Dungeon", "Dungeon"
    # NonWalkers
    BAHAMUT         = "Bahamut", "Bahamut"
    ELLYWICK        = "Ellywick", "Ellywick"
    ELMINSTER       = "Elminster", "Elminster"
    INZERVA         = "Inzerva", "Inzerva"
    LOLTH           = "Lolth", "Lolth"
    MINSC           = "Minsc", "Minsc"
    MORDENKAINEN    = "Mordenkainen", "Mordenkainen"
    SVEGA           = "Svega", "Svega"
    ZARIEL          = "Zariel", "Zariel"
    # HotR
    DEB     = "Deb", "Deb"
    MASTER  = "Master", "Master"



# --- Game Concepts ---
class GameZone(models.TextChoices):
    HAND        = "hand",        "Hand"
    LIBRARY     = "library",     "Library"
    BATTLEFIELD = "battlefield", "Battlefield"
    GRAVEYARD   = "graveyard",   "Graveyard"
    STACK       = "stack",       "Stack"
    EXILE       = "exile",       "Exile"
    COMMAND     = "command",     "Command"
    ANTE        = "ante",        "Ante"


class TurnPhase(models.TextChoices):
    BEGINNING = "beginning", "Beginning Phase"
    MAIN_1    = "main_1",    "First Main Phase"
    COMBAT    = "combat",    "Combat Phase"
    MAIN_2    = "main_2",    "Second Main Phase"
    ENDING    = "ending",    "Ending Phase"


class TurnStep(models.TextChoices):
    UNTAP             = "untap",             "Untap Step"
    UPKEEP            = "upkeep",            "Upkeep Step"
    DRAW              = "draw",              "Draw Step"
    BEGIN_COMBAT      = "begin_combat",      "Beginning of Combat Step"
    DECLARE_ATTACKERS = "declare_attackers", "Declare Attackers Step"
    DECLARE_BLOCKERS  = "declare_blockers",  "Declare Blockers Step"
    COMBAT_DAMAGE     = "combat_damage",     "Combat Damage Step"
    END_COMBAT        = "end_combat",        "End of Combat Step"
    END               = "end",              "End Step"
    CLEANUP           = "cleanup",           "Cleanup Step"


class PlayerAction(models.TextChoices):
    CAST      = "cast",      "Cast"
    ACTIVATE  = "activate",  "Activate"
    TRIGGER   = "trigger",   "Trigger"
    PLAY      = "play",      "Play"
    DRAW      = "draw",      "Draw"
    DISCARD   = "discard",   "Discard"
    SACRIFICE = "sacrifice", "Sacrifice"
    TAP       = "tap",       "Tap"
    UNTAP     = "untap",     "Untap"
    EXILE     = "exile",     "Exile"
    COUNTER   = "counter",   "Counter"
    DESTROY   = "destroy",   "Destroy"
    CREATE    = "create",    "Create"
    COPY      = "copy",      "Copy"
    

class MechanicType(models.TextChoices):
    KEYWORD     = 'keyword',        'Keyword'
    ACTION      = 'action',         'Action'
    ABILITYWORD = 'ability_word',   'Ability Word'
    MISC        = 'misc',           'Miscellaneous Ability'


class AbilityType(models.TextChoices):
    ACTIVATED   = 'activated',  'Activated'
    LINKED      = 'linked',     'Linked'
    LOYALTY     = 'loyalty',    'Loyalty'
    MANA        = 'mana',       'Mana'
    SPELL       = 'spell',      'Spell'
    STATIC      = 'static',     'Static'
    TRIGGER     = 'triggered',  'Triggered'
    

class EffectType(models.TextChoices):
    ONESHOT     = 'one-shot',       'One-Shot Effect'
    CONTINUOUS  = 'continuous',     'Contiuous Effect'
    TEXTCHANGE  = 'text-changing',  'Text-changing Effect'
    REPLACEMENT = 'replacement',    'Replacement Effect'
    PREVENTION  = 'prevention',     'Prevention Effect'


class LayerEffect(models.TextChoices):
    LAYER_1   = 'Layer 1', 'Layer 1: Copy effects'
    LAYER_2   = 'Layer 2', 'Layer 2: Control effects'
    LAYER_3   = 'Layer 3', 'Layer 3: Text-changing effects'
    LAYER_4   = 'Layer 4', 'Layer 4: Type-changing effects'
    LAYER_5   = 'Layer 5', 'Layer 5: Color-changing effects'
    LAYER_6   = 'Layer 6', 'Layer 6: Ability Add/Remove effects'
    LAYER_7   = 'Layer 7', 'Layer 7: Power/Toughness effects'
    
    
# --- Collection ---
class CardCondition(models.TextChoices):
    NEAR_MINT   = 'NM',  'Near Mint'
    LIGHTLY     = 'LP',  'Lightly Played'
    MODERATE    = 'MP',  'Moderately Played'
    HEAVILY     = 'HP',  'Heavily Played'
    DAMAGED     = 'DMG', 'Damaged'
