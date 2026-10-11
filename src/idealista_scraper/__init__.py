"""Scrape Idealista property listings with the ScrapeUnblocker API.

Search homes, rooms, offices, premises, garages, land and more for sale or to
rent on idealista.com (Spain), idealista.it (Italy) and idealista.pt
(Portugal) with Idealista's own sort orders and filters, and get every result
as a typed record: listing ID, title, property type, address, price with rent
period, previous price and price drop, price per m², bedrooms or rooms, size,
floor, exterior and lift flags, parking, tags, agency, photo count, media and
URL. Listing pages add the full description, every feature group, bathrooms,
the energy certificate, community fees and deposit, the location breadcrumb,
advertiser, reference, last update and the photo gallery. Pages are fetched
through the ScrapeUnblocker ``getPageSource`` API.

    >>> from idealista_scraper import IdealistaScraper
    >>> idealista = IdealistaScraper()                  # reads SCRAPEUNBLOCKER_KEY
    >>> homes = idealista.search("madrid-madrid", max_price=400000, sort="newest", pages=2)
    >>> homes[0].price, homes[0].bedrooms, homes[0].size_m2, homes[0].address
    >>> idealista.listing(homes[0]).features
"""

from .export import csv_string, flatten, to_json, to_jsonl, write_csv, write_json
from .models import (
    EnergyRating,
    FilterGroup,
    FilterOption,
    Listing,
    ListingDetails,
    Photo,
    SearchPage,
)
from .parsing import (
    IdealistaError,
    IdealistaNotFoundError,
    IdealistaParseError,
    parse_amount,
    parse_listing_page,
    parse_search_page,
)
from .scraper import IdealistaScraper, page_url
from .urls import (
    OPERATIONS,
    PROPERTY_TYPES,
    SITES,
    SORTS,
    filter_slugs,
    listing_url,
    paginate,
    search_url,
    unfiltered,
)

__version__ = "0.1.0"

__all__ = [
    "OPERATIONS",
    "PROPERTY_TYPES",
    "SITES",
    "SORTS",
    "EnergyRating",
    "FilterGroup",
    "FilterOption",
    "IdealistaError",
    "IdealistaNotFoundError",
    "IdealistaParseError",
    "IdealistaScraper",
    "Listing",
    "ListingDetails",
    "Photo",
    "SearchPage",
    "__version__",
    "csv_string",
    "filter_slugs",
    "flatten",
    "listing_url",
    "page_url",
    "paginate",
    "parse_amount",
    "parse_listing_page",
    "parse_search_page",
    "search_url",
    "to_json",
    "to_jsonl",
    "unfiltered",
    "write_csv",
    "write_json",
]
