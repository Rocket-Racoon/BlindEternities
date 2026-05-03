# Blind Eternities

A Django web app for Magic: The Gathering players to manage card collections, build decks, log games, run tournaments, and trade cards with other players.

Card data is synced from [Scryfall](https://scryfall.com/docs/api). The frontend uses HTMX for dynamic updates and Tailwind CSS 4 for styling.

## Features

| App | URL | What it does |
|---|---|---|
| **nexus** | `/` | User profiles, OAuth login (Google / GitHub via allauth), friends |
| **multiverse** | `/cards/` | Card database synced from Scryfall — sets, prints, faces, rulings, format legality, per-user collection completion |
| **tolarian** | `/collection/` | Collections (binder / wishlist / tradelist / loanlist) and decks with zone support (main / sideboard / commander / companion / maybeboard). Plaintext + MTG Arena import. Side-by-side deck compare |
| **phyrexian** | `/stats/` | Game records, live multiplayer life-tracker sessions, win-rate analytics, tournaments (Swiss / single-elim, Bo1 / Bo3, 1v1 / 3-player / 4-player pods), multiplayer ELO ratings, collection + format-coverage stats, CSV exports |
| **omenpath** | `/market/` | Trading marketplace — sell / wanted-to-buy listings, two-party trade or sale transactions with proposal → counter → accept → mutual-confirm → completed flow, inline messaging, event-based timeline, inventory reservations, Scryfall / TCGPlayer / Cardmarket price quotes, trade reputation badges |
| **conflux** | `/conflux/` | AI-driven EDH deck evaluation — scores decks against the Honest Scale Commander rubric and assigns a WotC Commander Bracket tier (1–5) using a local Ollama model |

## Tech stack

- **Backend** — Django 5, SQLite (dev) / PostgreSQL (prod), allauth, crispy-forms, whitenoise
- **Frontend** — HTMX, Tailwind CSS 4 (`@tailwindcss/forms`, `@tailwindcss/typography`), Bootstrap 5 (crispy template pack), [mana-font](https://mana.andrewgioia.com/) for Magic symbols
- **External APIs** — Scryfall (card data + free prices), TCGPlayer, Cardmarket
- **Local LLM** — [Ollama](https://ollama.com/) for the Conflux deck evaluator

## Quick start

### 1. Clone and install

```bash
git clone <repo-url> blindeternities
cd blindeternities

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
npm install
```

### 2. Create a `.env` in the project root

```ini
SECRET_KEY=replace-me
DJANGO_SETTINGS_MODULE=BlindEternities.settings.development

# Optional: enable paid price sources for the omenpath market
TCGPLAYER_PUBLIC_KEY=
TCGPLAYER_PRIVATE_KEY=
CARDMARKET_APP_TOKEN=
CARDMARKET_APP_SECRET=
CARDMARKET_ACCESS_TOKEN=
CARDMARKET_ACCESS_TOKEN_SECRET=

# Conflux — local Ollama server for AI deck evaluation
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
OLLAMA_TIMEOUT=300

# Production-only
# DATABASE_URL=postgres://user:pass@host:5432/db
# EMAIL_HOST=
# EMAIL_HOST_USER=
# EMAIL_HOST_PASSWORD=
# DEFAULT_FROM_EMAIL=
```

### 3. Initialize the database and seed Scryfall data

```bash
python manage.py migrate

# Run in this order on first setup
python manage.py sync_sets
python manage.py sync_creature_types
python manage.py sync_mechanics
python manage.py sync_cards            # bulk sync, ~10 minutes
python manage.py sync_prices
python manage.py sync_rulings

# Optional: seeded test users (all share password testpass123)
python manage.py create_test_users
```

### 4. Run the dev server

In two terminals:

```bash
# Terminal 1 — Django
python manage.py runserver

# Terminal 2 — Tailwind watcher
npm run dev
```

Visit <http://127.0.0.1:8000/>.

## Common commands

```bash
# Single-set Scryfall sync (faster than full bulk)
python manage.py sync_cards --set znr

# Daily price refresh
python manage.py sync_prices

# Omenpath market prices (TCGPlayer / Cardmarket / Scryfall)
python manage.py sync_market_prices
python manage.py sync_market_prices --source tcgplayer --set znr

# Omenpath listing expiration sweeper (run daily)
python manage.py expire_listings
python manage.py expire_listings --dry-run

# Conflux card tagger — classify MTG cards via Ollama (function + theme tags)
python manage.py tag_cards                          # tag every untagged card
python manage.py tag_cards --set znr --limit 100    # only ZNR, first 100
python manage.py tag_cards --retag --concurrency 8  # re-tag everything, 8 threads
python manage.py tag_cards --vocab-only             # only re-tag stale-vocab rows

# Phyrexian — exports and recompute
python manage.py export_games --format csv --output games.csv
python manage.py export_elo --history
python manage.py recalculate_elo
python manage.py recalculate_tournament_stats

# Tailwind production build
npm run build
```

On Windows, `scripts\sync_market_prices.bat` is a wrapper suitable for Task Scheduler.

## Project layout

```
BlindEternities/        # Django project (settings/, urls.py, wsgi.py)
  settings/
    base.py             # shared config — Scryfall, allauth, market-price creds
    development.py      # SQLite, DEBUG=True, debug toolbar
    production.py       # PostgreSQL, HTTPS, SendGrid email
core/                   # BaseModel (UUID PK, soft delete), enums, mana-symbol template tags
multiverse/             # Card / CardSet / CardPrint / CardFace / CardLegality / Ruling
tolarian/               # Collections, Decks, deck compare, importers
phyrexian/              # Game records, live sessions, tournaments, ELO, analytics
omenpath/               # Listings, transactions, pricing, inventory reservations
conflux/                # AI deck evaluation (Ollama) — Honest Scale + Bracket System
nexus/                  # Profiles, friends, OAuth glue
templates/              # Per-app templates + HTMX partials under <app>/partials/
static/css/input.css    # Tailwind input → compiled to static/css/main.css
```

## Settings

`BlindEternities/settings/` is split:

- `base.py` — shared config (Scryfall API rate limits / batch sizes / timeouts, allauth, market-price API credentials)
- `development.py` — SQLite, `DEBUG=True`, debug toolbar, console email backend
- `production.py` — PostgreSQL via `DATABASE_URL`, HTTPS enforcement, SMTP email

Switch with `DJANGO_SETTINGS_MODULE`.

## Tests and linting

No test suite or linter is configured yet.

## Contributing

Architectural notes for AI assistants and contributors who want a deeper map of the codebase live in [CLAUDE.md](CLAUDE.md) — including the key model patterns, HTMX conventions, enum locations, and per-app feature maps.
