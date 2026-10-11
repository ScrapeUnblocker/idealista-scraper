# Idealista Scraper

[![CI](https://github.com/ScrapeUnblocker/idealista-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/ScrapeUnblocker/idealista-scraper/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Powered by ScrapeUnblocker](https://img.shields.io/badge/powered%20by-ScrapeUnblocker-6f42c1.svg)](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)

**Scrape [Idealista](https://www.idealista.com) property listings for sale and to rent in
Spain, Italy and Portugal into clean JSON or CSV: price (and monthly rent), previous price and
price drop, price per m², bedrooms or rooms, size, floor, lift, parking, tags, agency, photos
and URL.** Search any location on idealista.com, idealista.it and idealista.pt with
Idealista's own filters and sort orders, collect several pages and locations in one run,
and read full listing pages with the description, every feature, bathrooms, the energy
certificate, community fees, the advertiser and the photo gallery. Built for rental and
property market research, price tracking, investment screening and housing data analysis.

Powered by [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos):
the `getPageSource` API loads each Idealista page in a real browser and returns the rendered
HTML. This package parses that HTML into typed records. You don't need proxies, a headless
browser or retry logic of your own.

## Features

- **Three countries, one interface.** `--site es` (idealista.com, Spain), `it` (idealista.it,
  Italy) and `pt` (idealista.pt, Portugal). Each site has its own URL words; the package
  builds them for you.
- **For sale or to rent, any property type.** Homes, new homes, rooms (Spain), offices,
  premises, garages, land, storage rooms and whole buildings.
- **Idealista's own filters.** Price and size range, plus every sidebar filter Idealista offers
  for a search (bedrooms, bathrooms, property sub-type, condition, lift, terrace, garage,
  pool, energy efficiency, long-term vs. seasonal rental, floor, bank-owned, ...). The
  `filters` command lists them with the slug to pass.
- **12 sort orders.** Relevance, newest, oldest, price up / down, biggest price drop, price
  per m² up / down, size, floor.
- **Paste a URL from the browser.** Set up a search on Idealista and pass it with `--url`;
  the scraper keeps its filters and pages through it.
- **Clean listing records.** Listing ID, URL, title, property type, address, price with rent
  period, previous price and price-drop percent, price per m², bedrooms (Spain, Portugal) or
  rooms (Italy), size in m², floor text and number, exterior and lift flags, parking
  (included / optional with its price), tags (luxury, seasonal rental, auction, tenanted,
  ...), description snippet, agency name, profile and logo, private/professional flag, photo
  count, floor plan / video / 3D tour flags, image and position.
- **Listing details.** Full description with line breaks, every feature group (basic
  features, building, equipment, energy certificate), bathrooms, energy consumption and
  emissions ratings, price details (community fees, deposit), location breadcrumb
  (street, neighbourhood, district, town), advertiser name, type and profile, reference,
  last-updated date and the full photo gallery with room tags and floor plans.
- **Multi-page, multi-location, de-duplicated.** 30 listings per page; collection stops at
  the last page. Several locations in one run are merged by listing ID.
- **Resilient.** Timeouts, transient API errors and pages that come back without their
  content are retried with doubling backoff. Unknown locations, filter slugs and removed
  listings raise a clear not-found error instead of returning nothing silently.
- **JSON, JSON Lines or CSV.** CSV files are UTF-8 with a BOM, so Excel opens accents and
  the € sign correctly.
- **CLI + Python library.** Fully typed, and tested offline with a mocked client.

## Install

```bash
git clone https://github.com/ScrapeUnblocker/idealista-scraper.git
cd idealista-scraper
pip install .
```

Get an API key at [scrapeunblocker.com](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)
and expose it as `SCRAPEUNBLOCKER_KEY` (the official SDK reads it from there):

```bash
export SCRAPEUNBLOCKER_KEY=your_key_here        # Windows PowerShell: $env:SCRAPEUNBLOCKER_KEY="your_key_here"
```

You can also copy `.env.example` to `.env` and load it with your tool of choice.

## Finding a location slug

Idealista identifies places by the slug in its URLs. Search a place on the site and copy the
part after the operation:

| URL on Idealista | Slug | Site |
| --- | --- | --- |
| idealista.com/venta-viviendas/**madrid-madrid**/ | `madrid-madrid` | `es` |
| idealista.com/alquiler-viviendas/**barcelona-barcelona**/ | `barcelona-barcelona` | `es` |
| idealista.com/venta-viviendas/**madrid/centro**/ (a district) | `madrid/centro` | `es` |
| idealista.it/vendita-case/**milano-milano**/ | `milano-milano` | `it` |
| idealista.pt/comprar-casas/**lisboa**/ | `lisboa` | `pt` |

Or skip slugs entirely and pass the whole search URL with `--url`.

## CLI usage

```bash
# Newest homes for sale in Madrid under 400,000 EUR, 3 pages, to CSV
idealista-scraper search madrid-madrid --max-price 400000 --sort newest -p 3 -f csv -o madrid.csv

# Long-term rentals in Barcelona up to 1,600 EUR/month with 2 or 3 bedrooms, cheapest first
idealista-scraper search barcelona-barcelona --rent --max-price 1600 \
    --filter de-dos-dormitorios,de-tres-dormitorios --filter alquiler-de-larga-temporada \
    --sort price-asc --pretty

# Italy and Portugal: biggest price drops in Rome, rentals in Lisbon from private owners
idealista-scraper search roma-roma --site it --sort price-drop -n 50
idealista-scraper search lisboa --site pt --rent --private-only -p 2 -f csv -o lisboa.csv

# Offices, premises, garages, land, ... and several locations in one de-duplicated run
idealista-scraper search madrid-madrid barcelona-barcelona --type offices --rent -p 2

# What can I filter on? Every sidebar filter of a search, with its slug
idealista-scraper filters madrid-madrid
idealista-scraper filters milano-milano --site it --rent

# Any search URL from the browser (filters and sort kept), 5 pages
idealista-scraper search --url "https://www.idealista.com/venta-viviendas/madrid-madrid/con-precio-hasta_500000,ascensor/" -p 5

# Full listing pages: description, features, energy certificate, photos
idealista-scraper listing 106881426 --pretty
idealista-scraper listing https://www.idealista.it/immobile/36193363/ https://www.idealista.pt/imovel/34665653/
idealista-scraper search lisboa --site pt -n 10 --details -o lisboa-details.json

# Show the URL that would be fetched, without calling the API
idealista-scraper search lisboa --site pt --min-price 300000 --min-size 60 --sort newest --dry-run
```

`search` options:

| Option | Meaning |
| --- | --- |
| `LOCATION ...` / `--url URL` | Location slugs (several allowed) or an Idealista search URL |
| `--site` | `es` (idealista.com, default), `it` (idealista.it), `pt` (idealista.pt) |
| `--operation`, `--rent` | `sale` (default) or `rent`; `--rent` is a shortcut |
| `--type` | `homes` (default), `new-homes`, `rooms` (Spain, rent), `offices`, `premises`, `garages`, `land`, `storage`, `buildings` |
| `--sort` | `relevance`, `newest`, `oldest`, `price-asc`, `price-desc`, `price-drop`, `price-m2-asc`, `price-m2-desc`, `size-desc`, `size-asc`, `floor-desc`, `floor-asc` |
| `--min-price`, `--max-price` | Price range in EUR (per month for rentals) |
| `--min-size`, `--max-size` | Size range in m² |
| `--filter SLUG` | Any filter slug from the `filters` command (repeatable or comma-separated) |
| `--professional-only`, `--private-only` | Keep agency / developer listings or private sellers only |
| `--order` | Sort the collected listings locally: `price`, `price-desc`, `price-m2`, `size`, `price-drop` |
| `-p, --pages N` | Pages per location, 30 listings each (stops at the last page) |
| `-n, --limit N` | At most N listings per location |
| `--details` | Also read every listing page (one extra request per listing) |
| `--country CODE` | Route requests through a country; by default ScrapeUnblocker picks the route |
| `-f, --format` | `json` (default), `jsonl` or `csv`; `-o FILE` to write a file, `--pretty` to indent |

## Library usage

```python
from idealista_scraper import IdealistaScraper, write_csv

# Reads SCRAPEUNBLOCKER_KEY; IdealistaScraper(api_key="...") also works
idealista = IdealistaScraper()

homes = idealista.search(
    "madrid-madrid",
    max_price=400000,
    min_size=60,
    filters=["de-dos-dormitorios", "de-tres-dormitorios", "ascensor"],
    sort="newest",
    pages=3,
)
for home in homes[:5]:
    print(home.price, home.bedrooms, home.size_m2, home.floor, home.address, home.url)
write_csv(homes, "madrid.csv")

# Rentals in Italy and Portugal
rome = idealista.search("roma-roma", site="it", operation="rent", max_price=1500)
lisbon = idealista.search("lisboa", site="pt", operation="rent", professional=False)

# Which filters does a search offer?
page = idealista.filters("barcelona-barcelona", operation="rent")
for group in page.filters:
    print(group.label, group.slugs)

# Several locations, de-duplicated by listing ID
homes = idealista.search_many(["madrid-madrid", "barcelona-barcelona"], sort="price-drop")

# Listing details: description, features, energy certificate, photos
details = idealista.listing(homes[0])  # or a listing URL, or an ID plus site="es"
print(details.bathrooms, details.features, details.energy_certificate)
print([photo.url for photo in details.photos if photo.floor_plan])
```

Errors: `IdealistaNotFoundError` (Idealista answered 404: an unknown location or filter
slug, a search that matches nothing, or a removed listing) and `IdealistaParseError` (a page
came back without its content after all retries) derive from `IdealistaError`. API errors
from the official SDK (for example an invalid key) are passed through.

## Example output

One listing from `idealista-scraper search madrid-madrid` (description shortened):

```json
{
  "listing_id": 112272495,
  "url": "https://www.idealista.com/inmueble/112272495/",
  "title": "Piso en Calle de López de Hoyos, Castellana, Madrid",
  "site": "es",
  "property_type": "Piso",
  "address": "Calle de López de Hoyos, Castellana, Madrid",
  "price": 2595000.0,
  "currency": "EUR",
  "price_period": null,
  "original_price": 2695000.0,
  "price_drop_percent": 4.0,
  "price_per_m2": null,
  "bedrooms": 3,
  "rooms": null,
  "size_m2": 284.0,
  "floor": "2ª planta",
  "floor_number": 2,
  "exterior": true,
  "lift": true,
  "parking": "included",
  "parking_price": null,
  "details": ["Garaje incluido", "3 hab.", "284 m²", "2ª planta exterior con ascensor"],
  "tags": ["Lujo"],
  "description": "En una de las zonas más exclusivas y representativas de Madrid, junto a la Plaza de los Hermanos Bécquer, ...",
  "professional": true,
  "agency_name": "Gilmar Barrio de Salamanca",
  "agency_url": "https://www.idealista.com/pro/gilmarsalamanca/",
  "agency_logo": "https://st3.idealista.com/90/79/01/gilmarsalamanca.gif",
  "photos": 39,
  "media": ["plan", "virtual_tour_3d", "video"],
  "image": "https://img4.idealista.com/blur/591_420_mq/0/id.pro.es.image.master/8c/c0/b6/1476215285.jpg",
  "position": 1,
  "page": 1,
  "search": "madrid-madrid"
}
```

A rental from `idealista-scraper listing 106881426` (description and photos shortened):

```json
{
  "listing_id": 106881426,
  "url": "https://www.idealista.com/inmueble/106881426/",
  "site": "es",
  "title": "Alquiler de piso en Calle del Congost",
  "area": "Vila de Gràcia, Barcelona",
  "operation": "rent",
  "typology": "home",
  "price": 1550.0,
  "currency": "EUR",
  "price_period": "month",
  "price_per_m2": 28.18,
  "price_details": ["Precio del inmueble: 1.550 €/mes", "Precio por m²: 28,18 €/m²"],
  "bedrooms": 2,
  "bathrooms": 1,
  "size_m2": 55.0,
  "floor": "4ª planta",
  "floor_number": 4,
  "exterior": true,
  "lift": true,
  "tags": ["Alquiler de temporada"],
  "features": {
    "Características básicas": ["55 m² construidos, 46 m² útiles", "2 habitaciones", "1 baño",
                                "Balcón", "Segunda mano/buen estado", "Orientación norte",
                                "Amueblado y cocina equipada",
                                "Calefacción individual: Bomba de frío/calor"],
    "Edificio": ["4ª planta exterior", "Con ascensor"],
    "Equipamiento": ["Aire acondicionado"],
    "Certificado energético": ["Consumo: 234 kWh/m² año", "Emisiones: 42 kg CO2/m² año"]
  },
  "energy_certificate": [
    {"label": "Consumo", "rating": "E", "value": "234 kWh/m² año"},
    {"label": "Emisiones", "rating": "D", "value": "42 kg CO2/m² año"}
  ],
  "description": "ALQUILER DE TEMPORADA (USO EXCLUSIVO VACACIONES/OCIO)\n\n...",
  "location": ["Calle del Congost", "Barrio Vila de Gràcia", "Distrito Gràcia", "Barcelona",
               "Área de Barcelona, Barcelona"],
  "reference": "I19831-4",
  "advertiser_name": "ShBarcelona",
  "advertiser_type": "Profesional",
  "advertiser_url": "https://www.idealista.com/pro/shbarcelona/",
  "last_updated": "Anuncio actualizado el 10 de octubre",
  "photos": [
    {"url": "https://img4.idealista.com/blur/WEB_DETAIL/0/id.pro.es.image.master/db/b4/77/1296634768.jpg",
     "tag": "Dormitorio", "floor_plan": false}
  ]
}
```

## Good to know

- **Prices** are in EUR. Rentals carry `price_period` (`month` for long-term rentals);
  `original_price` and `price_drop_percent` are set when Idealista shows a price reduction.
  `price_per_m2` is shown on some result cards and on every listing page.
- **Bedrooms vs. rooms.** Spain ("3 hab.") and Portugal ("T3") count bedrooms, which go to
  `bedrooms`. Italy counts all rooms ("3 locali"), which go to `rooms`.
- **Text stays in the site's language.** Titles, tags, features, floor labels and update
  dates are kept as Idealista writes them (Spanish, Italian or Portuguese); the numbers and
  flags derived from them (`size_m2`, `floor_number`, `lift`, `exterior`, `parking`) are
  language-neutral. The raw card facts are always in `details` / `summary`.
- **404 means "nothing here".** Idealista answers 404 for an unknown location slug, an
  unknown filter slug, a search with no matching listing and a page past the last one. The
  first is reported as `IdealistaNotFoundError`; a 404 on a later page ends the collection.
- **Filters.** Price and size bounds are built for each site (`precio-hasta_`, `prezzo_`,
  `preco-max_`, ...). Every other filter is a slug from the `filters` command. Idealista only
  links its filters on a search with no filters applied, so `filters` always reads the plain
  search of the location.
- **Energy certificate.** Spanish listings show a letter for consumption and emissions,
  Portuguese listings one letter. Italian pages tested showed the value but no letter, so
  `rating` is null there and `value` is kept.
- **Location.** The pages tested carried no coordinates; `location` is Idealista's location
  breadcrumb and `address` / `area` are as displayed.
- **Pagination.** 30 listings per page. Collection stops at the last page or when a page
  only repeats listings already collected.
- Collect public data responsibly: keep request volumes reasonable and follow Idealista's
  terms and the data-protection rules that apply to you. Private sellers' first names appear
  in `advertiser_name` on listing pages.

## Project layout

```
idealista-scraper/
├── src/idealista_scraper/
│   ├── __init__.py      # package exports + __version__
│   ├── scraper.py       # IdealistaScraper: search, filters, listing pages, retries
│   ├── parsing.py       # Idealista HTML -> typed records
│   ├── models.py        # Listing, SearchPage, ListingDetails, FilterGroup, Photo, ...
│   ├── urls.py          # per-site URL vocabulary: operations, types, filters, sorts, pages
│   ├── export.py        # JSON, JSON Lines and CSV writers
│   ├── cli.py           # the idealista-scraper command
│   └── __main__.py      # python -m idealista_scraper
├── examples/
│   ├── search_to_json.py     # newest listings of a location as JSON
│   ├── rentals_to_csv.py     # long-term rentals under a budget, cheapest first, to CSV
│   └── price_drops.py        # biggest price drops, plus listing details of the top ones
├── tests/                    # offline tests with a mocked client (no API calls)
├── pyproject.toml
├── requirements.txt
├── Makefile
└── .github/workflows/ci.yml
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
make install    # pip install -e ".[dev]"
make lint       # ruff check .
make format     # ruff format .
make test       # pytest -q (offline, no API key needed)
make run        # examples/search_to_json.py madrid-madrid (needs SCRAPEUNBLOCKER_KEY)
```

`pre-commit install` enables the ruff hooks from `.pre-commit-config.yaml`.

## Links

- [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos) - web scraping API that returns rendered HTML from protected sites
- [Documentation](https://docs.scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos) - `getPageSource`, SDKs, parameters and errors
- Official SDK: `pip install scrapeunblocker`

## License

[MIT](LICENSE) - Copyright (c) 2026 ScrapeUnblocker
