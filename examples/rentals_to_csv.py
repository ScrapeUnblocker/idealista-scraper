"""Long-term rentals under a monthly budget with 2+ bedrooms, cheapest first, to CSV.

    python examples/rentals_to_csv.py barcelona-barcelona --max-rent 1600 -o rentals.csv

Uses Idealista's own filters (price, bedrooms, long-term rentals only) and sort
order, collects several pages and writes a CSV that opens cleanly in Excel.
Needs SCRAPEUNBLOCKER_KEY in the environment.
"""

from __future__ import annotations

import argparse

from idealista_scraper import IdealistaScraper, write_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("location", help="Spanish location slug, e.g. barcelona-barcelona")
    parser.add_argument("--max-rent", type=float, default=1600, help="EUR per month")
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("-o", "--output", default="rentals.csv")
    args = parser.parse_args()

    idealista = IdealistaScraper()
    rentals = idealista.search(
        args.location,
        operation="rent",
        max_price=args.max_rent,
        filters=[
            "de-dos-dormitorios",
            "de-tres-dormitorios",
            "de-cuatro-cinco-habitaciones-o-mas",
            "alquiler-de-larga-temporada",
        ],
        sort="price-asc",
        pages=args.pages,
    )
    for home in rentals[:10]:
        print(
            f"{home.price:>7,.0f} EUR/{home.price_period}  {home.bedrooms} bed  "
            f"{home.size_m2 or '?'} m2  {home.address}"
        )
    count = write_csv(rentals, args.output)
    print(f"wrote {count} rentals to {args.output}")


if __name__ == "__main__":
    main()
