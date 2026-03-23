# Sync workflow — Multiverse

Orden correcto para sincronización inicial completa:
```bash
# 1. Sets — prerequisito para todo lo demás
py manage.py sync_sets

# 2. Catálogos — creature types, keywords, mechanics
py manage.py sync_creature_types
py manage.py sync_mechanics
py manage.py sync_catalog

# 3. Cartas — bulk data desde Scryfall (~100MB, ~10min)
py manage.py sync_cards

# 4. Rulings
py manage.py sync_rulings
```

## Frecuencias recomendadas

| Comando | Frecuencia | Motivo |
|---|---|---|
| `sync_prices` | Diario | Precios cambian cada día |
| `sync_cards --set XYZ` | Por lanzamiento | Spoiler season / release |
| `sync_sets` | Por lanzamiento | Nuevo set |
| `sync_creature_types` | Por lanzamiento | Nuevas razas |
| `sync_mechanics` | Por lanzamiento | Nuevas keywords |
| `sync_rulings` | Cuando hay erratas | WotC publica erratas |
| `sync_catalog` | Rara vez | Tipos de permanentes estables |

## Importar desde archivo JSON local
```bash
# Descargar bulk data manualmente desde:
# https://scryfall.com/docs/api/bulk-data → oracle-cards

# Sync sets primero
py manage.py sync_sets

# Importar desde archivo
py manage.py import_cards C:\dumps\oracle-cards.json

# Con opciones
py manage.py import_cards C:\dumps\oracle-cards.json --limit 100 --dry-run
py manage.py import_cards C:\dumps\oracle-cards.json --set znr --verbosity 2
py manage.py import_cards C:\dumps\oracle-cards.json --skip-prints
```

## Flags disponibles

### `sync_cards` y `import_cards`
| Flag | Descripción |
|---|---|
| `--dry-run` | Procesa sin guardar |
| `--limit N` | Limita a N cartas |
| `--set CODE` | Solo un set |
| `--skip-faces` | No sincroniza CardFace |
| `--skip-legality` | No sincroniza CardLegality |
| `--skip-prints` | No sincroniza CardPrint |
| `--verbosity 2` | Output detallado por carta |

### `sync_sets`
| Flag | Descripción |
|---|---|
| `--dry-run` | Muestra cambios sin guardar |
| `--code CODE` | Solo un set específico |