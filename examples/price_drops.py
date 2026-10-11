"""Biggest recent price drops in a location, with the full details of the top few.

    python examples/price_drops.py madrid-madrid --top 3
    python examples/price_drops.py lisboa --site pt

Sorts by Idealista's "biggest price drop" order, then reads the listing pages of
the top results for their description, features and energy certificate.
Needs SCRAPEUNBLOCKER_KEY in the environment.
"""

from __future__ import annotations

import argparse

from idealista_scraper import IdealistaScraper, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("location", help="Location slug from an Idealista URL")
    parser.add_argument("--site", default="es", choices=["es", "it", "pt"])
    parser.add_argument("--top", type=int, default=3, help="Listing pages to read")
    parser.add_argument("-o", "--output", default="price-drops.json")
    args = parser.parse_args()

    idealista = IdealistaScraper()
    drops = idealista.search(args.location, site=args.site, sort="price-drop", limit=30)
    for home in drops[:10]:
        print(
            f"-{home.price_drop_percent or 0:>4.0f}%  {home.original_price or 0:>12,.0f} -> "
            f"{home.price or 0:>12,.0f} EUR  {home.title}"
        )
    details = idealista.listings(drops[: args.top])
    for item in details:
        energy = ", ".join(f"{e.label}: {e.rating}" for e in item.energy_certificate if e.rating)
        print(
            f"\n{item.title} ({item.area})\n  {item.bathrooms} bath, {item.size_m2} m2, "
            f"energy {energy or 'n/a'}, updated: {item.last_updated}"
        )
    write_json(details, args.output)
    print(f"\nwrote {len(details)} listing(s) to {args.output}")


if __name__ == "__main__":
    main()
