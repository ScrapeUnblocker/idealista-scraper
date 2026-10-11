"""Typed records returned by the scraper. Every record has ``to_dict()``."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _plain(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


class _Record:
    def to_dict(self) -> dict[str, Any]:
        return {key: _plain(value) for key, value in asdict(self).items()}  # type: ignore[call-overload]


@dataclass
class Listing(_Record):
    """One property card of a search results page. Prices are in euros.

    ``bedrooms`` is filled on idealista.com ("3 hab.") and idealista.pt ("T3");
    idealista.it counts all rooms instead ("3 locali"), which goes to ``rooms``.
    """

    listing_id: int
    url: str
    title: str
    site: str
    property_type: str | None = None
    address: str | None = None
    price: float | None = None
    currency: str = "EUR"
    price_period: str | None = None
    original_price: float | None = None
    price_drop_percent: float | None = None
    price_per_m2: float | None = None
    bedrooms: int | None = None
    rooms: int | None = None
    size_m2: float | None = None
    floor: str | None = None
    floor_number: int | None = None
    exterior: bool | None = None
    lift: bool | None = None
    parking: str | None = None
    parking_price: float | None = None
    details: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str | None = None
    professional: bool | None = None
    agency_name: str | None = None
    agency_url: str | None = None
    agency_logo: str | None = None
    photos: int | None = None
    media: list[str] = field(default_factory=list)
    image: str | None = None
    position: int | None = None
    page: int | None = None
    search: str | None = None


@dataclass
class FilterOption(_Record):
    """One option of a sidebar filter. Pass ``slug`` as a filter to apply it."""

    label: str
    slug: str | None = None
    selected: bool = False


@dataclass
class FilterGroup(_Record):
    """A filter group of the search sidebar (property type, bedrooms, features, ...)."""

    label: str
    options: list[FilterOption] = field(default_factory=list)

    @property
    def slugs(self) -> list[str]:
        return [option.slug for option in self.options if option.slug]


@dataclass
class SearchPage(_Record):
    """One page of search results plus what Idealista reports about the search."""

    url: str
    site: str
    page: int
    listings: list[Listing] = field(default_factory=list)
    total: int | None = None
    heading: str | None = None
    operation: str | None = None
    property_type: str | None = None
    location: str | None = None
    average_price_per_m2: float | None = None
    has_next: bool = False
    filters: list[FilterGroup] = field(default_factory=list)

    @property
    def page_size(self) -> int:
        return len(self.listings)


@dataclass
class Photo(_Record):
    url: str
    tag: str | None = None
    floor_plan: bool = False


@dataclass
class EnergyRating(_Record):
    """One line of the energy certificate: e.g. ``Consumo:`` rated ``E`` at ``234 kWh/m² año``."""

    label: str | None = None
    rating: str | None = None
    value: str | None = None


@dataclass
class ListingDetails(_Record):
    """Everything on a listing page. Prices are in euros.

    ``area`` is the neighbourhood and town under the title; ``location`` is the
    location breadcrumb (street when shown, neighbourhood, district, town, region).
    ``operation`` (``sale`` / ``rent``) and ``typology`` (``home``, ``office``, ...)
    are Idealista's own codes for the listing.
    """

    listing_id: int
    url: str
    site: str
    title: str | None = None
    area: str | None = None
    operation: str | None = None
    typology: str | None = None
    price: float | None = None
    currency: str = "EUR"
    price_period: str | None = None
    original_price: float | None = None
    price_drop_percent: float | None = None
    price_per_m2: float | None = None
    price_details: list[str] = field(default_factory=list)
    bedrooms: int | None = None
    rooms: int | None = None
    bathrooms: int | None = None
    size_m2: float | None = None
    floor: str | None = None
    floor_number: int | None = None
    exterior: bool | None = None
    lift: bool | None = None
    parking: str | None = None
    parking_price: float | None = None
    summary: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    features: dict[str, list[str]] = field(default_factory=dict)
    energy_certificate: list[EnergyRating] = field(default_factory=list)
    description: str | None = None
    location: list[str] = field(default_factory=list)
    reference: str | None = None
    advertiser_name: str | None = None
    advertiser_type: str | None = None
    advertiser_url: str | None = None
    last_updated: str | None = None
    photos: list[Photo] = field(default_factory=list)
