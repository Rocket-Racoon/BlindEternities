# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Blind Eternities is a Django web app for Magic: The Gathering players to manage card collections, build decks, and browse card data synced from Scryfall. Frontend uses HTMX for dynamic updates and Tailwind CSS 4.

## Commands

```bash
# Dev server (uses DJANGO_SETTINGS_MODULE=BlindEternities.settings.development)
python manage.py runserver

# Tailwind CSS watch / build
npm run dev       # watch mode
npm run build     # minified output

# Database migrations
python manage.py migrate

# Scryfall data sync (run in this order for initial setup)
python manage.py sync_sets
python manage.py sync_creature_types
python manage.py sync_mechanics
python manage.py sync_cards              # bulk, ~10 min
python manage.py sync_cards --set znr    # single set
python manage.py sync_prices             # daily price update
python manage.py sync_rulings
```

No test suite or linter is configured yet.

## Architecture

### Django Apps (domain-driven)

| App | URL prefix | Purpose |
|---|---|---|
| **nexus** | `/` | User profiles, OAuth (allauth with Google/GitHub), home page |
| **multiverse** | `/cards/` | Card database: Card, CardSet, CardFace, CardPrint, CardLegality, Ruling. All synced from Scryfall API |
| **tolarian** | `/collection/` | Collections (binder/wishlist/tradelist/loanlist) and Decks with zone support (main/sideboard/commander/companion/maybeboard) |
| **core** | — | Shared BaseModel (UUID PK, timestamps, soft-delete), constants (enums for formats, colors, rarities, layouts), template tags (mana symbol rendering), pagination utility |
| **phyrexian** | `/stats/` | Stub — future game statistics |
| **omenpath** | `/market/` | Stub — future trading marketplace |

### Settings

Split settings in `BlindEternities/settings/`:
- `base.py` — shared config, Scryfall API settings (rate limits, timeouts, batch sizes), allauth OAuth
- `development.py` — SQLite, DEBUG=True, debug toolbar, console email
- `production.py` — PostgreSQL via `DATABASE_URL`, HTTPS enforcement, SendGrid email

### Key Patterns

- **BaseModel** (`core/models.py`): All models inherit UUID primary key, `created_at`/`updated_at` timestamps, `is_active` soft-delete with `soft_delete()`/`restore()` methods
- **HTMX partials**: Views check for `HX-Request` header and return partial templates. Partials live in `templates/<app>/partials/`
- **Mana symbols**: `core/templatetags/core_tags.py` provides `mana_cost` and `oracle_symbols` filters that convert `{W}{U}{B}` notation to icon markup using mana-font
- **Owner permissions**: `OwnerRequiredMixin` in `core/mixins.py`; collection/deck views also check `is_public` for shared access
- **Pagination**: `core.utils.paginate_queryset()` + `{% paginator page_obj %}` template tag
- **Card model hierarchy**: Card (oracle data) → CardPrint (specific printing in a set) → CardFace (multi-face card data). CardLegality is 1:1 with Card storing format legality as JSON
- **Deck/Collection imports**: `tolarian/utils.py` has parsers for plaintext ("4x Lightning Bolt") and CSV formats. Deck import supports MTG Arena format with zone headers (`// Sideboard`)

### Frontend Stack

- Tailwind CSS 4.2 with `@tailwindcss/forms` and `@tailwindcss/typography` plugins
- HTMX for dynamic content loading (card grids, deck stats, user profile tabs)
- Crispy Forms with Bootstrap 5 template pack
- Mana-font for Magic card symbols
- CSS input: `static/css/input.css` → compiled to `static/css/main.css`

### Scryfall API

Config in `base.py`: 100ms request delay, 500 batch size for bulk inserts, 15s/300s timeouts. User-Agent header: `BlindEternities/1.0`. Management commands handle all sync logic with `--dry-run`, `--limit`, `--set`, and `--verbosity` flags.

### Enums

`core/constants.py` defines TextChoices enums used across the project: `MagicFormat`, `MagicColor`, `CardRarity`, `CardLayout`, `CardSetType`, `CollectionType`, `DeckZone`, `CardCondition`, `CardFinish`. Always use these instead of raw strings.
