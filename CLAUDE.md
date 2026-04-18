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

# Phyrexian data export / ELO / tournament stats
python manage.py export_games --format csv --output games.csv
python manage.py export_elo --history
python manage.py recalculate_elo                   # replay all games, rebuild ratings
python manage.py recalculate_tournament_stats     # rebuild per-user tournament aggregates
```

No test suite or linter is configured yet.

## Architecture

### Django Apps (domain-driven)

| App | URL prefix | Purpose |
|---|---|---|
| **nexus** | `/` | User profiles, OAuth (allauth with Google/GitHub), home page, friend system |
| **multiverse** | `/cards/` | Card database: Card, CardSet, CardFace, CardPrint, CardLegality, Ruling. All synced from Scryfall API. Set detail shows per-user completion + quick-add to collection |
| **tolarian** | `/collection/` | Collections (binder/wishlist/tradelist/loanlist) and Decks with zone support (main/sideboard/commander/companion/maybeboard). Deck compare with rich analytics |
| **core** | — | Shared BaseModel (UUID PK, timestamps, soft-delete), constants (enums for formats, colors, rarities, layouts), template tags (mana symbol rendering), pagination utility |
| **phyrexian** | `/stats/` | Game stats dashboard, game record CRUD, live multiplayer sessions (lifetap-style), win rate analytics, tournament brackets (Swiss / single-elim / Bo3), multiplayer ELO ratings, TournamentStats aggregates, collection+deck analytics, data export commands |
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

App-local enums live next to their models:
- `phyrexian/models.py` — `GameResult`, `EliminationCause` (life/poison/commander_damage/alt_wincon/forfeit/alt_losecon), `SessionStatus`, `BracketType` (swiss/single_elim), `TournamentStatus`

### Phyrexian feature map

- **Game records** (`/stats/games/`) — CRUD with opponents (`GamePlayer` inline), commanders, placement, elimination tracking (cause + turn + eliminator)
- **Live sessions** (`/stats/session/new/`) — 2-6 player Lifetap-style tracker. `GameSession` + `PlayerSlot` + `LifeChange`. Session end auto-creates `GameRecord`s for each linked user and triggers ELO updates
- **Win rate analytics** (`/stats/winrate/`) — trends (monthly/yearly), elimination cause pie, placement distribution, turn duration, commander performance, H2H, biggest-threats. Filter by format/deck/commander/color
- **Collection stats** (`/stats/collection/`) — rarity/color/condition/top-valuable + playset completion (cross-collection aggregate, non-basic-land) + format coverage (legal cards per format vs deck minimum)
- **Tournaments** (`/stats/tournaments/`) — Swiss pairing (avoids rematches, handles byes) or Single Elim, configurable pod size (1v1 / 3 / 4) and best_of (1 or 3). `tournament.py` has the engine (`generate_next_round`, `record_match_result`, `recompute_tournament_stats`). Rich add-player UI with user-search + deck-dropdown + commander autocomplete
- **ELO** (`/stats/elo/`) — `elo.py` has the pairwise-comparison multiplayer ELO engine (K=32/24, default 1200, floor 100). `EloRating` per user+format, `EloHistory` for audit/chart. Auto-updates on session end
- **Deck comparison** (`/collection/decks/compare/`) — side-by-side with overlap %, cost-to-transform, mana curve + type distribution grouped bars, color identity comparison
- **Deck detail** (`/collection/decks/<pk>/`) — right sidebar shows Record panel (W/L/D, monthly + cumulative win rate trend chart, recent games) for decks with logged games
