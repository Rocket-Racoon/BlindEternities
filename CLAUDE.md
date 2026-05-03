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

# Omenpath market price sync (TCGPlayer / Cardmarket / Scryfall)
python manage.py sync_market_prices                # refresh all sources, skip fresh <24h
python manage.py sync_market_prices --source tcgplayer --set znr
# Windows scheduled task — run scripts\sync_market_prices.bat daily via Task Scheduler
# Requires TCGPLAYER_* and CARDMARKET_* credentials in .env to enable those sources.

# Omenpath listing expiration sweeper (run daily)
python manage.py expire_listings              # OPEN → EXPIRED past expires_at
python manage.py expire_listings --dry-run
```

No test suite or linter is configured yet.

## Test Users

Seeded via `python manage.py create_test_users` ([nexus/management/commands/create_test_users.py](nexus/management/commands/create_test_users.py)). Allauth is configured for email login (`ACCOUNT_LOGIN_METHODS = {"email"}`), so the command also creates a verified primary `EmailAddress` per user. All share the same password; re-running resets it.

| Login Email | Username | Display Name | Password |
|---|---|---|---|
| `urza@blindeternities.test` | `urza` | Urza, Lord High Artificer | `testpass123` |
| `karn@blindeternities.test` | `karn` | Karn, Silver Golem | `testpass123` |
| `teferi@blindeternities.test` | `teferi` | Teferi, Temporal Archmage | `testpass123` |
| `nicol.bolas@blindeternities.test` | `nicol_bolas` | Nicol Bolas, the Ravager | `testpass123` |
| `freyalise@blindeternities.test` | `freyalise` | Freyalise, Llanowar's Fury | `testpass123` |
| `nahiri@blindeternities.test` | `nahiri` | Nahiri, the Lithomancer | `testpass123` |
| `sorin@blindeternities.test` | `sorin` | Sorin Markov | `testpass123` |
| `ugin@blindeternities.test` | `ugin` | Ugin, the Spirit Dragon | `testpass123` |
| `toshiro@blindeternities.test` | `toshiro` | Toshiro Umezawa | `testpass123` |

Override the default with `--password <pw>`. These accounts are for local testing only — do not run this command in production.

## Architecture

### Django Apps (domain-driven)

| App | URL prefix | Purpose |
|---|---|---|
| **nexus** | `/` | User profiles, OAuth (allauth with Google/GitHub), home page, friend system |
| **multiverse** | `/cards/` | Card database: Card, CardSet, CardFace, CardPrint, CardLegality, Ruling. All synced from Scryfall API. Set detail shows per-user completion + quick-add to collection |
| **tolarian** | `/collection/` | Collections (binder/wishlist/tradelist/loanlist) and Decks with zone support (main/sideboard/commander/companion/maybeboard). Deck compare with rich analytics |
| **core** | — | Shared BaseModel (UUID PK, timestamps, soft-delete), constants (enums for formats, colors, rarities, layouts), template tags (mana symbol rendering), pagination utility |
| **phyrexian** | `/stats/` | Game stats dashboard, game record CRUD, live multiplayer sessions (lifetap-style), win rate analytics, tournament brackets (Swiss / single-elim / Bo3), multiplayer ELO ratings, TournamentStats aggregates, collection+deck analytics, data export commands |
| **omenpath** | `/market/` | Trading marketplace: listings (sell / wanted-to-buy), two-party transactions (trade or sale) with proposal → counter → accept → mutual-confirm → completed flow, inline messaging, event-based timeline, inventory reservations, market price quotes (Scryfall/TCGPlayer/Cardmarket), trade reputation badges |
| **conflux** | `/conflux/` | AI-driven EDH deck evaluation against the Honest Scale Commander rubric and the WotC Commander Bracket System (1–5). Talks to a local Ollama server. Accepts a saved `tolarian.Deck` or a pasted decklist. Background-thread runner with HTMX poll for the result panel |

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
- `omenpath/models.py` — `ListingType` (sell/buy_wanted), `ListingVisibility` (public/friends), `ListingStatus` (open/expired/closed/completed), `TransactionKind` (trade/sale), `TransactionStatus` (proposed/counter_proposed/accepted/rejected/cancelled/completed), `TransactionSide` (from_a/from_b), `TransactionEventType`, `PriceSource` (scryfall/tcgplayer/cardmarket/user)
- `conflux/models.py` — `BracketTier` (1–5: exhibition/core/upgraded/optimized/cedh), `HonestTier` (jank/casual/mid/high/cedh), `IntentLabel` (competitive/optimized/casual/jank), `EvaluationStatus` (pending/running/completed/failed)

### Phyrexian feature map

- **Game records** (`/stats/games/`) — CRUD with opponents (`GamePlayer` inline), commanders, placement, elimination tracking (cause + turn + eliminator)
- **Live sessions** (`/stats/session/new/`) — 2-6 player Lifetap-style tracker. `GameSession` + `PlayerSlot` + `LifeChange`. Session end auto-creates `GameRecord`s for each linked user and triggers ELO updates
- **Win rate analytics** (`/stats/winrate/`) — trends (monthly/yearly), elimination cause pie, placement distribution, turn duration, commander performance, H2H, biggest-threats. Filter by format/deck/commander/color
- **Collection stats** (`/stats/collection/`) — rarity/color/condition/top-valuable + playset completion (cross-collection aggregate, non-basic-land) + format coverage (legal cards per format vs deck minimum)
- **Tournaments** (`/stats/tournaments/`) — Swiss pairing (avoids rematches, handles byes) or Single Elim, configurable pod size (1v1 / 3 / 4) and best_of (1 or 3). `tournament.py` has the engine (`generate_next_round`, `record_match_result`, `recompute_tournament_stats`). Rich add-player UI with user-search + deck-dropdown + commander autocomplete
- **ELO** (`/stats/elo/`) — `elo.py` has the pairwise-comparison multiplayer ELO engine (K=32/24, default 1200, floor 100). `EloRating` per user+format, `EloHistory` for audit/chart. Auto-updates on session end
- **Deck comparison** (`/collection/decks/compare/`) — side-by-side with overlap %, cost-to-transform, mana curve + type distribution grouped bars, color identity comparison
- **Deck detail** (`/collection/decks/<pk>/`) — right sidebar shows Record panel (W/L/D, monthly + cumulative win rate trend chart, recent games) for decks with logged games

### Omenpath feature map

- **Listings** (`/market/`) — `Listing` model: SELL or BUY_WANTED, public or friends-only, with condition / finish / language / quantity / asking price / optional `expires_at`. List view filters by type / scope / condition / price range and sorts. `expire_listings` command flips OPEN → EXPIRED past their `expires_at` (frees reserved inventory)
- **Transactions** (`/market/trades/`) — two-party `Transaction` (kind = trade or sale) with `TransactionItem` rows on each side (`from_a` / `from_b`). State machine: PROPOSED → COUNTER_PROPOSED (either side can counter back) → ACCEPTED → mutual-confirm → COMPLETED, plus REJECTED / CANCELLED terminal states. On completion, items move into the recipient's auto-managed `Recolect` collection
- **Inventory reservations** (`omenpath/inventory.py`) — a giver can only promise cards they own in BINDER or TRADELIST (excluding `Recolect`). `available_quantity = owned − reserved`, where reserved = own OPEN SELL listings + non-terminal-tx items where they are the giver. `validate_inventory()` enforces this on listing/proposal/counter/acceptance. Sale-tx items tied to one of the user's own SELL listings are de-duplicated against (1)
- **Timeline & messaging** — `TransactionEvent` is an immutable audit log of state transitions (proposed/countered/accepted/rejected/cancelled/confirmed/unconfirmed/completed) rendered as the negotiation timeline. `TransactionMessage` is free-text chat, allowed on any status, merged into the same timeline view
- **Pricing** (`omenpath/pricing/`) — `PriceQuote` cache per (card_print, source, finish, currency). Sources: Scryfall (free), TCGPlayer, Cardmarket (env-gated credentials). `sync_market_prices` refreshes; `market_value_for()` snapshots `unit_value` on `TransactionItem` at proposal time
- **Trade reputation** (`omenpath/stats.py`) — `trade_stats_for(user)` and bulk `trade_stats_for_users(users)` return completed-tx count + last-completed timestamp. Rendered as a badge on listings, transactions, and user profiles
- **CSV export** (`/market/trades/export.csv`) — completed transactions for the requesting user
- **Notifications** (`omenpath/notifications.py`) — email via Django's `EMAIL_BACKEND` on transaction state changes; `SITE_URL` setting is used to build absolute links

### Conflux feature map

- **Evaluations** (`/conflux/`) — `DeckEvaluation` model snapshots either a saved `tolarian.Deck` (resolved to plaintext via `serialize_deck`) or a pasted decklist, plus the user's self-rated bracket. Indexed by `(user, status)` and `(deck, -created_at)`
- **Hybrid scoring** — the LLM does only what it's good at: card classification (functional tags), per-axis qualitative scores (0–10), combo identification, narrative. Python applies the **official Honest Scale weighted formula** (`compute_final_score` in `conflux/rubric.py`) so the result is reproducible regardless of model drift
- **Rubric** (`conflux/rubric.py`) — encodes the 8 Commander Honest Scale criteria (`speed`, `consistency`, `access`, `mana_efficiency`, `wincon`, `interaction`, `resilience`, `intent`) plus 2 algorithm components (`synergy`, `card_power_avg`). Weighted-formula axes: `0.20·speed + 0.20·consistency + 0.15·synergy + 0.15·wincon + 0.10·interaction + 0.10·resilience + 0.10·card_power_avg`. `tier_for()` maps the final score to a `HonestTier` (cedh/high/mid/casual/jank); `bracket_for()` maps it to a WotC bracket (1–5). `CARD_TAGS` enumerates the functional categories used in preprocessing (RAMP_FAST, TUTOR_DIRECT, COMBO_PIECE, etc.)
- **LLM client** (`conflux/services.py`) — POSTs to Ollama's `/api/chat` with `format=json` and a low temperature. The system prompt is generated from `CRITERIA` + `ALGORITHM_COMPONENTS` so any rubric edit propagates automatically. `evaluate_async()` spawns a daemon thread, calls `close_old_connections()` on exit, and writes `honest_scores`, `card_tags`, `combos`, `intent_label`/`intent_reason`, `narrative`, `final_score` (Python-computed), `honest_tier`, `bracket`, `prompt`, `raw_response`, `duration_ms` back to the row
- **Result panel** (`templates/conflux/partials/result_panel.html`) — hero with final score / honest tier / bracket; per-axis bars with reasons; intent card; combo list; collapsed card-tag classification; collapsed decklist. HTMX polls the detail URL every 2s while status is non-terminal (`hx-trigger="load delay:2s" hx-swap="outerHTML"`); the view returns the full page or just the partial based on `HX-Request`
- **Deck-detail integration** — Commander-format decks show an "Evaluar" link in the toolbar that points at `/conflux/new/?deck=<pk>`; `EvaluationCreateView.get_initial()` validates ownership and pre-selects the deck + commander
- **Card tagger** (`conflux/tagger.py` + `conflux/vocabulary.py`) — per-card classification agent over Ollama. `vocabulary.py` defines the controlled `FUNCTION_TAGS` (~32) and `THEME_TAGS` (~32) vocabularies plus `validate_tags()` (rejects unknown tags, allows `tribal:<type>` subtags). `tag_card()` runs one Ollama `/api/chat` call per card with `format=json` and a low temperature; `tag_cards_concurrent()` fans out across a `ThreadPoolExecutor`. `VOCABULARY_VERSION` lets us invalidate stored tags in bulk when the taxonomy changes
- **CardTag model** — `OneToOneField(multiverse.Card)` storing `function_tags` + `theme_tags` (JSON lists), `reasoning`, `model_name`, `vocabulary_version`, `error`. Re-tagging overwrites. Used by the deck evaluator (`_tag_summary_for_deck` aggregates tag counts and stitches them into the user prompt) and reserved for future deck-building suggestion features
- **Bulk tagging command** — `python manage.py tag_cards [--set CODE] [--limit N] [--retag] [--vocab-only] [--concurrency 5] [--model qwen2.5] [--dry-run]`. Default behaviour tags only cards without a CardTag row; `--vocab-only` re-tags rows whose `vocabulary_version` is below the current code version
- **Settings** — `OLLAMA_URL` (default `http://localhost:11434`), `OLLAMA_MODEL` (default `llama3.1`), `OLLAMA_TIMEOUT` (default 300s) all read from `.env` via `django-environ`
