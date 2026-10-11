"""Scrape Idealista through the ScrapeUnblocker ``getPageSource`` API.

:class:`IdealistaScraper` fetches Idealista search results and listing pages as
rendered HTML and parses them. Timeouts, transient API errors and pages that
come back without their content are retried with doubling backoff, so a long
collection run keeps going.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Iterator, Sequence
from typing import Any, Callable, TypeVar

from .models import Listing, ListingDetails, SearchPage
from .parsing import (
    IdealistaNotFoundError,
    IdealistaParseError,
    parse_listing_page,
    parse_search_page,
)
from .urls import is_search_url, listing_url, paginate, search_url, unfiltered

T = TypeVar("T")

_TRANSIENT_NAMES = (
    "UpstreamOutageError",
    "RateLimitError",
    "ScrapeTimeoutError",
    "BrowserTimeoutError",
    "BlockedError",
    "ServerError",
    "ConnectionError",
)
_NOT_FOUND_NAMES = ("TargetNotFoundError", "NotFoundError")

#: Search options that become part of the Idealista URL.
URL_OPTIONS = (
    "site",
    "operation",
    "property_type",
    "sort",
    "min_price",
    "max_price",
    "min_size",
    "max_size",
    "filters",
)


def _transient_errors() -> tuple[type[BaseException], ...]:
    """Best-effort tuple of ScrapeUnblocker exceptions worth retrying.

    Imported lazily so the package is usable (and unit-testable) even when the
    ``scrapeunblocker`` SDK is not installed.
    """
    try:
        import scrapeunblocker  # type: ignore
    except Exception:  # pragma: no cover - depends on SDK availability
        return ()
    found = (getattr(scrapeunblocker, name, None) for name in _TRANSIENT_NAMES)
    return tuple(cls for cls in found if isinstance(cls, type))


def _is_not_found(error: BaseException) -> bool:
    return any(cls.__name__ in _NOT_FOUND_NAMES for cls in type(error).__mro__)


def page_url(
    location: str | None = None,
    *,
    url: str | None = None,
    page: int = 1,
    site: str = "es",
    operation: str = "sale",
    property_type: str = "homes",
    sort: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_size: float | None = None,
    max_size: float | None = None,
    filters: Sequence[str] | None = None,
) -> str:
    """The URL of one page of results, from a location slug or a copied search URL.

    ``url`` may be any Idealista search URL from the browser (its filters and
    sort are kept); ``page``, ``sort`` and extra ``filters`` slugs are applied
    to it. Price and size bounds need a location (put them in the URL otherwise).
    """
    if url:
        if location:
            raise ValueError("give a location or a url, not both")
        if not is_search_url(url):
            raise ValueError(f"not an Idealista search URL: {url!r}")
        if any(value is not None for value in (min_price, max_price, min_size, max_size)):
            raise ValueError(
                "price and size bounds go with a location; with --url set them on Idealista "
                "and copy the URL, or pass the slug with --filter"
            )
        return paginate(url, page=page, sort=sort, filters=list(filters or ()))
    if not location:
        raise ValueError("give a location slug (e.g. madrid-madrid) or a search url")
    return search_url(
        location,
        site=site,
        operation=operation,
        property_type=property_type,
        page=page,
        sort=sort,
        min_price=min_price,
        max_price=max_price,
        min_size=min_size,
        max_size=max_size,
        filters=list(filters or ()),
    )


class IdealistaScraper:
    """Search Idealista (Spain, Italy, Portugal) and read listing pages.

    Args:
        api_key: ScrapeUnblocker key. If omitted, the SDK reads
            ``SCRAPEUNBLOCKER_KEY`` from the environment.
        client: A pre-built client (or any object exposing
            ``get_page_source(url, proxy_country=...)``). Mainly for testing.
        country: Optional country to route requests through (``es``, ``it``, ...).
            By default ScrapeUnblocker picks the route.
        retries: Extra attempts per request on transient failures.
        backoff: Seconds before the first retry; doubles on every further retry.
        max_backoff: Upper bound for a single wait between retries.
        timeout: Per-request timeout passed to the SDK client.
        transient_errors: Exception classes treated as retryable. Defaults to
            the ScrapeUnblocker transient set.
        on_retry: Optional callback ``(attempt, delay_seconds, error)`` invoked
            before every retry (handy for progress output).
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: Any | None = None,
        country: str | None = None,
        retries: int = 3,
        backoff: float = 5.0,
        max_backoff: float = 60.0,
        timeout: float = 180.0,
        transient_errors: Sequence[type[BaseException]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        on_retry: Callable[[int, float, BaseException], None] | None = None,
    ) -> None:
        if client is None:
            from scrapeunblocker import Client  # local import: optional dep

            client = Client(api_key=api_key, timeout=timeout)
        self._client = client
        self.country = (country or "").strip().lower() or None
        self.retries = max(0, int(retries))
        self.backoff = float(backoff)
        self.max_backoff = float(max_backoff)
        self.on_retry = on_retry
        transient = tuple(transient_errors) if transient_errors is not None else _transient_errors()
        self._transient = (*transient, IdealistaParseError)
        self._sleep = sleep

    # ------------------------------------------------------------------ #
    # Fetching
    # ------------------------------------------------------------------ #

    def _retry(self, action: Callable[[], T]) -> T:
        """Run ``action``, retrying transient failures with doubling backoff."""
        attempt = 0
        while True:
            try:
                return action()
            except Exception as exc:
                if not isinstance(exc, self._transient) or attempt >= self.retries:
                    raise
                attempt += 1
                delay = min(self.backoff * 2 ** (attempt - 1), self.max_backoff)
                if self.on_retry is not None:
                    self.on_retry(attempt, delay, exc)
                self._sleep(delay)

    def fetch(self, url: str) -> str:
        """One getPageSource call: the rendered HTML of an Idealista page."""
        options: dict[str, Any] = {}
        if self.country:
            options["proxy_country"] = self.country
        try:
            html = self._client.get_page_source(url, **options)
        except Exception as exc:
            if _is_not_found(exc):
                raise IdealistaNotFoundError(f"Idealista has no page at {url}") from exc
            raise
        return html if isinstance(html, str) else ""

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    def search_page(
        self, location: str | None = None, *, url: str | None = None, page: int = 1, **options: Any
    ) -> SearchPage:
        """Fetch one page of search results (30 listings).

        Args:
            location: Location slug as in Idealista URLs: ``madrid-madrid``,
                ``barcelona-barcelona``, ``madrid/centro``, ``milano-milano``,
                ``lisboa``.
            url: Any Idealista search URL instead of ``location``.
            page: 1-based page number.
            **options: ``site`` (``es``, ``it``, ``pt``), ``operation`` (``sale``,
                ``rent``), ``property_type``, ``sort``, ``min_price``,
                ``max_price``, ``min_size``, ``max_size`` and ``filters``; see
                :func:`page_url`.

        Raises:
            IdealistaNotFoundError: Idealista answered 404 - an unknown location
                or filter slug, no listing matches, or ``page`` is past the end.
        """
        target = page_url(location, url=url, page=page, **options)
        try:
            return self._retry(lambda: parse_search_page(self.fetch(target), target, page))
        except IdealistaNotFoundError as exc:
            hint = (
                "page is past the last page"
                if page > 1
                else "unknown location or filter slug, or no listing matches the filters"
            )
            raise IdealistaNotFoundError(f"{exc} ({hint})") from exc

    def iter_search(
        self,
        location: str | None = None,
        *,
        url: str | None = None,
        pages: int = 1,
        limit: int | None = None,
        seen: set[int] | None = None,
        professional: bool | None = None,
        on_page: Callable[[SearchPage], None] | None = None,
        **options: Any,
    ) -> Iterator[Listing]:
        """Yield listings page by page; see :meth:`search` for the arguments."""
        if pages < 1:
            raise ValueError("pages must be at least 1")
        if limit is not None and limit < 1:
            raise ValueError("limit must be at least 1")
        seen = set() if seen is None else seen
        label = location or url
        yielded = 0
        for number in range(1, pages + 1):
            try:
                result = self.search_page(location, url=url, page=number, **options)
            except IdealistaNotFoundError:
                if number == 1:
                    raise
                return  # Idealista answers 404 past the last page
            if on_page is not None:
                on_page(result)
            fresh = 0
            for listing in result.listings:
                if listing.listing_id in seen:
                    continue
                seen.add(listing.listing_id)
                fresh += 1
                if professional is not None and listing.professional is not professional:
                    continue
                listing.search = label
                yield listing
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            if not result.has_next or fresh == 0:
                return

    def search(
        self,
        location: str | None = None,
        *,
        url: str | None = None,
        pages: int = 1,
        limit: int | None = None,
        seen: set[int] | None = None,
        professional: bool | None = None,
        on_page: Callable[[SearchPage], None] | None = None,
        **options: Any,
    ) -> list[Listing]:
        """Search Idealista and collect listings across pages.

        Args:
            location: Location slug as in Idealista URLs (``madrid-madrid``,
                ``barcelona-barcelona``, ``madrid/centro``, ``milano-milano``,
                ``roma-roma``, ``lisboa``).
            url: Any Idealista search URL copied from the browser instead.
            pages: Pages to fetch (30 listings each). Stops early at the last page.
            limit: Return at most this many listings.
            seen: Shared set of listing IDs; listings already in it are skipped.
                Pass the same set to several calls to de-duplicate across searches.
            professional: ``True`` keeps agency listings only, ``False`` private
                sellers only.
            on_page: Callback invoked with every fetched :class:`SearchPage`.
            **options: ``site`` (``es`` = idealista.com, ``it``, ``pt``),
                ``operation`` (``sale`` or ``rent``), ``property_type``
                (``homes``, ``new-homes``, ``rooms``, ``offices``, ``premises``,
                ``garages``, ``land``, ``storage``, ``buildings``), ``sort``
                (see :data:`idealista_scraper.urls.SORTS`), ``min_price`` /
                ``max_price`` in euros, ``min_size`` / ``max_size`` in m² and
                ``filters``: Idealista filter slugs from :meth:`filters`.

        Raises:
            IdealistaNotFoundError: the first page does not exist (unknown
                location or filter slug, or nothing matches the filters).
        """
        return list(
            self.iter_search(
                location,
                url=url,
                pages=pages,
                limit=limit,
                seen=seen,
                professional=professional,
                on_page=on_page,
                **options,
            )
        )

    def search_many(
        self,
        locations: Iterable[str],
        *,
        on_location: Callable[[str, list[Listing]], None] | None = None,
        on_error: Callable[[str, Exception], None] | None = None,
        **options: Any,
    ) -> list[Listing]:
        """Run :meth:`search` for several locations, merged and de-duplicated by listing ID.

        A location Idealista does not know (404) goes to ``on_error`` when given,
        so one typo does not stop the run.
        """
        seen: set[int] = options.pop("seen", None) or set()
        results: list[Listing] = []
        for location in locations:
            try:
                found = self.search(location, seen=seen, **options)
            except IdealistaNotFoundError as exc:
                if on_error is None:
                    raise
                on_error(location, exc)
                continue
            if on_location is not None:
                on_location(location, found)
            results.extend(found)
        return results

    def filters(
        self, location: str | None = None, *, url: str | None = None, **options: Any
    ) -> SearchPage:
        """The filters Idealista offers for a search, from its sidebar (one request).

        Returns the :class:`SearchPage` of the plain search (no filters applied:
        Idealista only links its filters there); ``page.filters`` lists every
        group with the option labels and the slug to pass as a filter.
        """
        options = {key: value for key, value in options.items() if key in URL_OPTIONS}
        for bound in ("min_price", "max_price", "min_size", "max_size", "filters", "sort"):
            options.pop(bound, None)
        target = unfiltered(page_url(location, url=url, **options))
        return self.search_page(url=target)

    # ------------------------------------------------------------------ #
    # Listing pages
    # ------------------------------------------------------------------ #

    def listing(self, listing: str | int | Listing, site: str | None = None) -> ListingDetails:
        """Read a listing page: full description, every feature group, bathrooms,
        energy certificate, price details (community fees, deposit), location,
        advertiser, reference, last update and the photo gallery.

        Args:
            listing: A listing URL, a listing ID (with ``site``) or a :class:`Listing`.
            site: ``es`` (default for bare IDs), ``it`` or ``pt``.

        Raises:
            IdealistaNotFoundError: no such listing (or it was removed).
        """
        if isinstance(listing, Listing):
            target = listing.url
        else:
            target = listing_url(listing, site)
        return self._retry(lambda: parse_listing_page(self.fetch(target), target))

    def listings(
        self,
        items: Iterable[str | int | Listing],
        *,
        site: str | None = None,
        on_error: Callable[[str, Exception], None] | None = None,
    ) -> list[ListingDetails]:
        """Read several listing pages; failures go to ``on_error`` (or are raised)."""
        found: list[ListingDetails] = []
        for item in items:
            try:
                found.append(self.listing(item, site))
            except Exception as exc:
                if on_error is None:
                    raise
                on_error(item.url if isinstance(item, Listing) else str(item), exc)
        return found


__all__ = ["URL_OPTIONS", "IdealistaScraper", "page_url"]
