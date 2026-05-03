# TODO

Project-level work list. Edit freely — items here are starter prompts, not commitments.

## Quality / tooling

- [ ] **Test suite.** `tests.py` in every app is the 3-line Django placeholder. No tests exist. Start with the highest-leverage units:
  - [ ] `omenpath/inventory.py` — `available_quantity` / reservation math, including the SELL-listing de-dup edge case
  - [ ] `omenpath/services.py` — transaction state machine (propose → counter → accept → mutual-confirm → completed) and the `Recolect` move on completion
  - [ ] `phyrexian/elo.py` — pairwise ELO updates for multiplayer games
  - [ ] `phyrexian/tournament.py` — Swiss pairing (no rematches, byes), record_match_result, recompute_tournament_stats
  - [ ] `tolarian/utils.py` — plaintext + MTG Arena deck import parsers
- [ ] **Linter / formatter.** No ruff/black/flake8 config in repo. Pick one (suggest ruff) and add `pyproject.toml`.
- [ ] **Pre-commit hooks.** No `.pre-commit-config.yaml`. Wire ruff + django-check once a linter lands.
- [ ] **CI.** No `.github/` workflow. Once tests + lint exist, run them on PRs.
- [ ] **`.env.example`.** README documents env vars but there's no template file in the repo. Drop one in so first-time clones can `cp .env.example .env`.

## Omenpath

- [ ] **In-app notifications.** Only email is wired (`omenpath/notifications.py`). A bell-icon inbox / HTMX poll for unread events would be a natural next step.
- [ ] **Counter-offer diff view.** Timeline shows that a counter happened, but doesn't visually diff it against the previous proposal.
- [ ] **Pricing fallback UX.** When TCGPlayer/Cardmarket creds are missing, behaviour silently degrades to Scryfall-only. Surface this state in the UI so users know which source the snapshot came from.
- [ ] **Bulk listing import.** Listings are created one-at-a-time; importing from a CSV / collection subset would speed onboarding.
- [ ] **Reputation breakdown.** Badge currently shows count + last-completed only. Consider per-format / per-partner / disputed-rate detail.

## Phyrexian

- [ ] **Bracket types.** `BracketType` only covers swiss + single_elim. Double-elim and round-robin are obvious follow-ups.
- [ ] **Live session reconnect.** Confirm tab-close / refresh recovery for life-tracker sessions in progress.
- [ ] **ELO calibration.** Default K-factors (32/24) and starting rating (1200) are guesses. Sanity-check against logged history.

## Multiverse / Scryfall

- [ ] **Incremental sync.** `sync_cards` is a 10-minute bulk run. A delta-sync (since last `updated_at`) would make daily refresh cheap.
- [ ] **Set-level scheduling.** `sync_prices` runs across the whole DB; allow per-set throttling for large catalogs.

## Nexus / auth

- [ ] **Account deletion flow.** Allauth covers signup/login/password reset, but a self-serve "delete my account + cascade soft-delete" page is missing.
- [ ] **Profile privacy controls.** Friend system exists; per-collection / per-deck `is_public` is wired, but there's no global "make my profile private" toggle.

## Docs

- [ ] **Screenshots in README.** No visuals yet.
- [ ] **Deployment guide.** `production.py` exists but there's no doc covering how to actually deploy (DB, static files via whitenoise, Tailwind build, scheduled tasks).
