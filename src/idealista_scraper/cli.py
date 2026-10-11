"""Command-line interface: ``idealista-scraper <command> ...``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Callable, TextIO

from . import __version__
from .export import csv_string, to_json, to_jsonl
from .models import Listing, SearchPage
from .parsing import IdealistaError
from .scraper import IdealistaScraper, page_url
from .urls import OPERATIONS, PROPERTY_TYPES, SITES, SORTS

FORMATS_OUT = ("json", "jsonl", "csv")

#: Local sort orders for collected listings.
ORDERS: dict[str, tuple[Callable[[Listing], Any], bool]] = {
    "price": (lambda item: item.price, False),
    "price-desc": (lambda item: item.price, True),
    "price-m2": (lambda item: item.price_per_m2, False),
    "size": (lambda item: item.size_m2, True),
    "price-drop": (lambda item: item.price_drop_percent, True),
}


def _stdout() -> TextIO:
    """stdout that always accepts UTF-8 (Windows consoles default to a legacy codepage)."""
    stream = sys.stdout
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # pragma: no cover - exotic streams
            pass
    return stream


def _log(args: argparse.Namespace, message: str) -> None:
    if not getattr(args, "quiet", False):
        print(message, file=sys.stderr, flush=True)


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--country",
        metavar="CODE",
        help="Country to route requests through (es, it, pt, ...); by default "
        "ScrapeUnblocker picks the route",
    )
    parser.add_argument("--retries", type=int, default=3, help="Retries per request (default 3)")
    parser.add_argument("-q", "--quiet", action="store_true", help="No progress on stderr")


def _add_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-f", "--format", choices=FORMATS_OUT, default="json")
    parser.add_argument("-o", "--output", help="Write to this file instead of stdout")
    parser.add_argument("--pretty", action="store_true", help="Indent JSON output")


def _add_target(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("What to search")
    group.add_argument(
        "--site",
        choices=list(SITES),
        default="es",
        help="es = idealista.com (Spain, default), it = idealista.it, pt = idealista.pt",
    )
    group.add_argument("--operation", choices=OPERATIONS, default="sale", help="sale (default)")
    group.add_argument(
        "--rent",
        dest="operation",
        action="store_const",
        const="rent",
        help="Same as --operation rent",
    )
    group.add_argument(
        "--type",
        dest="property_type",
        choices=PROPERTY_TYPES,
        default="homes",
        help="Property type (default homes)",
    )


def _add_search_filters(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("Idealista filters (applied by Idealista)")
    group.add_argument("--sort", choices=SORTS, help="Sort order (default: relevance)")
    group.add_argument(
        "--min-price", type=float, metavar="EUR", help="Lowest price (per month for rent)"
    )
    group.add_argument(
        "--max-price", type=float, metavar="EUR", help="Highest price (per month for rent)"
    )
    group.add_argument("--min-size", type=float, metavar="M2", help="Smallest size in m²")
    group.add_argument("--max-size", type=float, metavar="M2", help="Largest size in m²")
    group.add_argument(
        "--filter",
        dest="filters",
        action="append",
        default=[],
        metavar="SLUG",
        help="Any Idealista filter slug, e.g. de-dos-dormitorios, ascensor, terraza "
        "(repeatable or comma-separated; see the `filters` command)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idealista-scraper",
        description="Scrape Idealista property listings (Spain, Italy, Portugal) "
        "via ScrapeUnblocker.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search listings for sale or to rent")
    search.add_argument(
        "locations",
        nargs="*",
        metavar="LOCATION",
        help="Location slug(s) from Idealista URLs: madrid-madrid, madrid/centro, "
        "milano-milano, lisboa",
    )
    search.add_argument("--url", help="An Idealista search URL copied from the browser")
    _add_target(search)
    _add_search_filters(search)
    local = search.add_argument_group("Local options (applied to the collected listings)")
    who = local.add_mutually_exclusive_group()
    who.add_argument(
        "--professional-only", action="store_true", help="Keep agency / developer listings only"
    )
    who.add_argument("--private-only", action="store_true", help="Keep private sellers only")
    local.add_argument("--order", choices=list(ORDERS), help="Sort the collected listings locally")
    search.add_argument(
        "-p", "--pages", type=int, default=1, help="Pages per location (30 listings each)"
    )
    search.add_argument("-n", "--limit", type=int, help="At most N listings per location")
    search.add_argument(
        "--details",
        action="store_true",
        help="Also read every listing page (description, features, energy, photos); "
        "one extra request per listing",
    )
    search.add_argument(
        "--dry-run", action="store_true", help="Print the first-page URLs; no API calls"
    )
    _add_common(search)
    _add_output(search)

    listing = sub.add_parser("listing", help="Read listing pages (full details and photos)")
    listing.add_argument("listings", nargs="+", metavar="LISTING", help="Listing URL or ID")
    listing.add_argument(
        "--site", choices=list(SITES), help="Site of bare listing IDs (default es)"
    )
    _add_common(listing)
    _add_output(listing)

    filters = sub.add_parser("filters", help="List the filter slugs Idealista offers for a search")
    filters.add_argument("location", nargs="?", help="Location slug")
    filters.add_argument("--url", help="An Idealista search URL")
    _add_target(filters)
    filters.add_argument("--json", action="store_true", help="Print the filters as JSON")
    _add_common(filters)
    return parser


def _options(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "site": args.site,
        "operation": args.operation,
        "property_type": args.property_type,
        "sort": args.sort,
        "min_price": args.min_price,
        "max_price": args.max_price,
        "min_size": args.min_size,
        "max_size": args.max_size,
        "filters": args.filters,
    }


def order_listings(listings: list[Listing], order: str | None) -> list[Listing]:
    """Listings sorted by ``price``, ``price-desc``, ``price-m2``, ``size`` (largest
    first) or ``price-drop`` (biggest drop first); listings without the value go last."""
    if not order:
        return listings
    key, reverse = ORDERS[order]
    known = [item for item in listings if key(item) is not None]
    unknown = [item for item in listings if key(item) is None]
    return sorted(known, key=key, reverse=reverse) + unknown


def _render(records: list[Any], args: argparse.Namespace) -> str:
    if args.format == "jsonl":
        return to_jsonl(records)
    if args.format == "csv":
        return csv_string(records)
    return to_json(records, pretty=args.pretty) + "\n"


def _emit(records: list[Any], args: argparse.Namespace) -> None:
    text = _render(records, args)
    if args.output:
        encoding = "utf-8-sig" if args.format == "csv" else "utf-8"
        with open(Path(args.output), "w", encoding=encoding, newline="") as handle:
            handle.write(text)
        _log(args, f"wrote {len(records)} record(s) to {args.output}")
    else:
        _stdout().write(text)


def _scraper(args: argparse.Namespace) -> IdealistaScraper:
    def on_retry(attempt: int, delay: float, error: BaseException) -> None:
        _log(args, f"  retry {attempt} in {delay:.0f}s ({type(error).__name__}: {error})")

    return IdealistaScraper(country=args.country, retries=args.retries, on_retry=on_retry)


def _cmd_search(args: argparse.Namespace, scraper: IdealistaScraper | None) -> int:
    if not args.locations and not args.url:
        raise SystemExit("search: give a location slug (e.g. madrid-madrid) or --url")
    if args.locations and args.url:
        raise SystemExit("search: give location slugs or --url, not both")
    options = _options(args)
    if args.dry_run:
        for location in args.locations or [None]:
            _stdout().write(page_url(location, url=args.url, **options) + "\n")
        return 0
    scraper = scraper or _scraper(args)

    def on_page(page: SearchPage) -> None:
        total = f" of {page.total:,}" if page.total is not None else ""
        _log(args, f"  page {page.page}: {len(page.listings)} listings{total}")

    professional = True if args.professional_only else False if args.private_only else None
    seen: set[int] = set()
    listings: list[Listing] = []
    failures = 0
    for location in args.locations or [None]:
        _log(args, f"searching {location}" if location else f"reading {args.url}")
        try:
            found = scraper.search(
                location,
                url=args.url,
                pages=args.pages,
                limit=args.limit,
                seen=seen,
                professional=professional,
                on_page=on_page,
                **options,
            )
        except IdealistaError as exc:
            failures += 1
            _log(args, f"  {type(exc).__name__}: {exc}")
            continue
        _log(args, f"  {len(found)} listing(s)")
        listings.extend(found)
    listings = order_listings(listings, args.order)
    if failures and not listings:
        return 1
    if not args.details:
        _emit(listings, args)
        return 0
    details = scraper.listings(
        listings,
        on_error=lambda url, exc: _log(args, f"  skipped {url}: {type(exc).__name__}: {exc}"),
    )
    _emit(details, args)
    return 0


def _cmd_listing(args: argparse.Namespace, scraper: IdealistaScraper | None) -> int:
    scraper = scraper or _scraper(args)
    failures = 0

    def on_error(item: str, exc: Exception) -> None:
        nonlocal failures
        failures += 1
        _log(args, f"  {item}: {type(exc).__name__}: {exc}")

    details = scraper.listings(args.listings, site=args.site, on_error=on_error)
    _emit(details, args)
    return 1 if failures and not details else 0


def _cmd_filters(args: argparse.Namespace, scraper: IdealistaScraper | None) -> int:
    if not args.location and not args.url:
        raise SystemExit("filters: give a location slug or --url")
    scraper = scraper or _scraper(args)
    page = scraper.filters(
        args.location,
        url=args.url,
        site=args.site,
        operation=args.operation,
        property_type=args.property_type,
    )
    out = _stdout()
    if args.json:
        out.write(json.dumps([g.to_dict() for g in page.filters], ensure_ascii=False, indent=2))
        out.write("\n")
        return 0
    total = f"{page.total:,} listings" if page.total is not None else "listings"
    out.write(f"{page.heading or page.url} - {total} - pass a slug as --filter SLUG\n")
    for group in page.filters:
        out.write(f"\n{group.label}\n")
        for option in group.options:
            if option.slug:
                out.write(f"  {option.slug:<40} {option.label}\n")
    return 0


COMMANDS = {
    "search": _cmd_search,
    "listing": _cmd_listing,
    "filters": _cmd_filters,
}


def main(argv: Sequence[str] | None = None, *, scraper: IdealistaScraper | None = None) -> int:
    """Run the CLI. ``scraper`` lets tests inject a scraper with a mocked client."""
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args, scraper)
    except (IdealistaError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        if not type(exc).__module__.startswith("scrapeunblocker"):
            raise
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)  # API errors, e.g. a bad key
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
