"""Newest homes for sale in a location, one page, printed as JSON.

    python examples/search_to_json.py madrid-madrid
    python examples/search_to_json.py milano-milano --site it
    python examples/search_to_json.py lisboa --site pt

Needs SCRAPEUNBLOCKER_KEY in the environment.
"""

from __future__ import annotations

import argparse

from idealista_scraper import IdealistaScraper, to_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("location", help="Location slug from an Idealista URL, e.g. madrid-madrid")
    parser.add_argument("--site", default="es", choices=["es", "it", "pt"])
    args = parser.parse_args()

    idealista = IdealistaScraper()
    page = idealista.search_page(args.location, site=args.site, sort="newest")
    print(f"{page.heading} - average {page.average_price_per_m2} EUR/m2", flush=True)
    print(to_json(page.listings, pretty=True))


if __name__ == "__main__":
    main()
