"""Idealista URLs: search listings, pagination, sort orders and filters, listing pages.

Idealista runs one site per country - ``idealista.com`` (Spain), ``idealista.it``
(Italy) and ``idealista.pt`` (Portugal) - with the same page layout but localized
URL words. A search URL is made of these parts::

    https://www.idealista.com
      /venta-viviendas                            operation + property type
      /madrid-madrid                              location slug
      /con-precio-hasta_500000,de-dos-dormitorios filters (comma-joined slugs)
      /pagina-2.htm                               page
      ?ordenado-por=fecha-publicacion-desc        sort order

Everything site-specific lives in :data:`SITES`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

#: Canonical sort orders, in the order Idealista lists them.
SORTS = (
    "relevance",
    "newest",
    "oldest",
    "price-asc",
    "price-desc",
    "price-drop",
    "price-m2-asc",
    "price-m2-desc",
    "size-desc",
    "size-asc",
    "floor-desc",
    "floor-asc",
)

OPERATIONS = ("sale", "rent")

#: Property types and what each site calls them in its URLs.
PROPERTY_TYPES = (
    "homes",
    "new-homes",
    "rooms",
    "offices",
    "premises",
    "garages",
    "land",
    "storage",
    "buildings",
)


@dataclass(frozen=True)
class Site:
    """URL vocabulary of one Idealista country site."""

    code: str
    host: str
    language: str
    operations: dict[str, str]
    types: dict[str, str]
    #: Property types that only exist for one operation (e.g. rooms are rent-only).
    only: dict[str, str]
    filter_prefix: str
    page_segment: str
    sort_param: str
    sorts: dict[str, str]
    listing_path: str
    price_slugs: dict[str, str] = field(default_factory=dict)

    @property
    def base(self) -> str:
        return f"https://{self.host}"

    def page_path(self, page: int) -> str:
        return self.page_segment.format(page=page)


SITES: dict[str, Site] = {
    "es": Site(
        code="es",
        host="www.idealista.com",
        language="es",
        operations={"sale": "venta", "rent": "alquiler"},
        types={
            "homes": "viviendas",
            "new-homes": "obranueva",
            "rooms": "habitacion",
            "offices": "oficinas",
            "premises": "locales",
            "garages": "garajes",
            "land": "terrenos",
            "storage": "trasteros",
            "buildings": "edificios",
        },
        only={"rooms": "rent"},
        filter_prefix="con-",
        page_segment="pagina-{page}.htm",
        sort_param="ordenado-por",
        sorts={
            "newest": "fecha-publicacion-desc",
            "oldest": "fecha-publicacion-asc",
            "price-asc": "precios-asc",
            "price-desc": "precios-desc",
            "price-drop": "rebajas-desc",
            "price-m2-asc": "precio-metro-cuadrado-asc",
            "price-m2-desc": "precio-metro-cuadrado-desc",
            "size-desc": "area-desc",
            "size-asc": "area-asc",
            "floor-desc": "planta-desc",
            "floor-asc": "planta-asc",
        },
        listing_path="/inmueble/{id}/",
        price_slugs={
            "max_price": "precio-hasta_{}",
            "min_price": "precio-desde_{}",
            "min_size": "metros-cuadrados-mas-de_{}",
            "max_size": "metros-cuadrados-menos-de_{}",
        },
    ),
    "it": Site(
        code="it",
        host="www.idealista.it",
        language="it",
        operations={"sale": "vendita", "rent": "affitto"},
        types={
            "homes": "case",
            "offices": "uffici",
            "premises": "negozi",
            "garages": "garage",
            "land": "terreni",
            "storage": "cantine",
            "buildings": "edifici",
        },
        only={},
        filter_prefix="con-",
        page_segment="lista-{page}.htm",
        sort_param="ordine",
        sorts={
            "newest": "pubblicazione-desc",
            "oldest": "pubblicazione-asc",
            "price-asc": "prezzi-asc",
            "price-desc": "prezzi-desc",
            "price-drop": "queda-desc",
            "price-m2-asc": "prezzoMedio-asc",
            "price-m2-desc": "prezzoMedio-desc",
            "size-desc": "area-desc",
            "size-asc": "area-asc",
            "floor-desc": "piano-desc",
            "floor-asc": "piano-asc",
        },
        listing_path="/immobile/{id}/",
        price_slugs={
            "max_price": "prezzo_{}",
            "min_price": "prezzo-min_{}",
            "min_size": "dimensione_{}",
            "max_size": "dimensione-max_{}",
        },
    ),
    "pt": Site(
        code="pt",
        host="www.idealista.pt",
        language="pt",
        operations={"sale": "comprar", "rent": "arrendar"},
        types={
            "homes": "casas",
            "new-homes": "empreendimentos",
            "offices": "escritorios",
            "garages": "garagens",
            "land": "terrenos",
            "storage": "arrecadacoes",
            "buildings": "predios",
        },
        only={},
        filter_prefix="com-",
        page_segment="pagina-{page}",
        sort_param="ordem",
        sorts={
            "newest": "atualizado-desc",
            "oldest": "atualizado-asc",
            "price-asc": "precos-asc",
            "price-desc": "precos-desc",
            "price-drop": "descida-desc",
            "price-m2-asc": "preco_medio-asc",
            "price-m2-desc": "preco_medio-desc",
            "size-desc": "tamanho-desc",
            "size-asc": "tamanho-asc",
            "floor-desc": "andar-desc",
            "floor-asc": "andar-asc",
        },
        listing_path="/imovel/{id}/",
        price_slugs={
            "max_price": "preco-max_{}",
            "min_price": "preco-min_{}",
            "min_size": "tamanho-min_{}",
            "max_size": "tamanho-max_{}",
        },
    ),
}

_HOSTS = {site.host.removeprefix("www."): site for site in SITES.values()}
_PAGE_RE = re.compile(r"^(?:pagina-\d+(?:\.htm)?|lista-\d+\.htm)$")
_FILTER_RE = re.compile(r"^(?:con|com)-(.+)$")
_LISTING_RE = re.compile(r"/(?:inmueble|immobile|imovel)/(\d+)")
_LOCATION_RE = re.compile(r"^[a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9-]*)*$")
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def get_site(code: str | Site) -> Site:
    """The :class:`Site` for ``es``, ``it`` or ``pt`` (also accepts a host name)."""
    if isinstance(code, Site):
        return code
    key = (code or "").strip().lower()
    if key in SITES:
        return SITES[key]
    host = key.removeprefix("https://").removeprefix("http://").split("/")[0]
    site = site_for_host(host)
    if site is None:
        raise ValueError(f"unknown Idealista site {code!r}; use one of: {', '.join(SITES)}")
    return site


def site_for_host(host: str) -> Site | None:
    host = host.lower().split(":")[0]
    for suffix, site in _HOSTS.items():
        if host == suffix or host.endswith("." + suffix):
            return site
    return None


def site_for_url(url: str) -> Site:
    """The site of an Idealista URL; ``ValueError`` for any other URL."""
    site = site_for_host(urlsplit(url).hostname or "")
    if site is None:
        raise ValueError(f"not an Idealista URL (idealista.com, .it or .pt): {url!r}")
    return site


def normalize_sort(sort: str | None) -> str | None:
    """A canonical sort name (``price_asc`` and ``PRICE-ASC`` work too); None = relevance."""
    if sort is None:
        return None
    key = sort.strip().lower().replace("_", "-")
    if key not in SORTS:
        raise ValueError(f"unknown sort {sort!r}; use one of: {', '.join(SORTS)}")
    return None if key == "relevance" else key


def _number(value: float | int, name: str) -> str:
    if value is None or value < 0:
        raise ValueError(f"{name} must be a positive number")
    return str(int(round(value)))


def filter_slugs(
    site: str | Site,
    *,
    min_price: float | None = None,
    max_price: float | None = None,
    min_size: float | None = None,
    max_size: float | None = None,
    filters: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """The filter part of a search URL as a list of Idealista slugs.

    ``min_price`` / ``max_price`` are in euros (per month for rentals) and
    ``min_size`` / ``max_size`` in m². ``filters`` are any other filter slugs, as
    listed by the ``filters`` command (``de-dos-dormitorios``, ``ascensor``,
    ``terrazza``, ``t2``, ...).
    """
    site = get_site(site)
    slugs: list[str] = []
    for name, value in (
        ("max_price", max_price),
        ("min_price", min_price),
        ("min_size", min_size),
        ("max_size", max_size),
    ):
        if value is not None:
            slugs.append(site.price_slugs[name].format(_number(value, name)))
    if min_price is not None and max_price is not None and min_price > max_price:
        raise ValueError("min_price is higher than max_price")
    if min_size is not None and max_size is not None and min_size > max_size:
        raise ValueError("min_size is higher than max_size")
    for raw in filters or ():
        for slug in str(raw).split(","):
            slug = slug.strip().lower()
            if not slug:
                continue
            slug = _FILTER_RE.sub(r"\1", slug)
            if not _SLUG_RE.match(slug):
                raise ValueError(f"not an Idealista filter slug: {raw!r}")
            if slug not in slugs:
                slugs.append(slug)
    return slugs


def search_path(site: str | Site, operation: str, property_type: str) -> str:
    """``venta-viviendas``, ``affitto-case``, ``comprar-casas``, ..."""
    site = get_site(site)
    operation = (operation or "").strip().lower()
    if operation not in site.operations:
        raise ValueError(f"unknown operation {operation!r}; use sale or rent")
    kind = (property_type or "").strip().lower()
    if kind not in PROPERTY_TYPES:
        raise ValueError(f"unknown property type {kind!r}; use one of: {', '.join(PROPERTY_TYPES)}")
    if kind not in site.types:
        offered = ", ".join(site.types)
        raise ValueError(f"{site.host} has no {kind!r} search (types there: {offered})")
    needed = site.only.get(kind)
    if needed and needed != operation:
        raise ValueError(f"{kind!r} listings on {site.host} are {needed}-only")
    return f"{site.operations[operation]}-{site.types[kind]}"


def normalize_location(location: str) -> str:
    """A location slug as Idealista uses it: ``madrid-madrid``, ``madrid/centro``, ``lisboa``."""
    value = (location or "").strip().strip("/").lower()
    if not _LOCATION_RE.match(value):
        raise ValueError(
            f"not an Idealista location slug: {location!r} - copy it from a search URL, e.g. "
            "'madrid-madrid' in idealista.com/venta-viviendas/madrid-madrid/"
        )
    return value


def search_url(
    location: str,
    *,
    site: str | Site = "es",
    operation: str = "sale",
    property_type: str = "homes",
    page: int = 1,
    sort: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_size: float | None = None,
    max_size: float | None = None,
    filters: list[str] | tuple[str, ...] | None = None,
) -> str:
    """The URL of one page of an Idealista search.

    >>> search_url("madrid-madrid", max_price=300000, sort="newest", page=2)
    'https://www.idealista.com/venta-viviendas/madrid-madrid/con-precio-hasta_300000/pagina-2.htm?ordenado-por=fecha-publicacion-desc'
    """
    site = get_site(site)
    path = f"/{search_path(site, operation, property_type)}/{normalize_location(location)}/"
    slugs = filter_slugs(
        site,
        min_price=min_price,
        max_price=max_price,
        min_size=min_size,
        max_size=max_size,
        filters=filters,
    )
    if slugs:
        path += f"{site.filter_prefix}{','.join(slugs)}/"
    return paginate(site.base + path, page=page, sort=sort)


def is_search_url(url: str) -> bool:
    try:
        site_for_url(url)
    except ValueError:
        return False
    return not _LISTING_RE.search(urlsplit(url).path)


def paginate(
    url: str,
    *,
    page: int = 1,
    sort: str | None = None,
    filters: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Point any Idealista search URL at ``page``; set ``sort`` and add ``filters`` when given.

    Filters and query parameters already in the URL are kept, so a search set up in
    the browser can be pasted as is.
    """
    if page < 1:
        raise ValueError("page must be at least 1")
    site = site_for_url(url)
    parts = urlsplit(url)
    segments = [segment for segment in parts.path.split("/") if segment]
    if segments and _PAGE_RE.match(segments[-1]):
        segments.pop()
    extra = filter_slugs(site, filters=filters) if filters else []
    if extra:
        if segments and _FILTER_RE.match(segments[-1]):
            current = _FILTER_RE.match(segments[-1]).group(1).split(",")  # type: ignore[union-attr]
            merged = current + [slug for slug in extra if slug not in current]
            segments[-1] = site.filter_prefix + ",".join(merged)
        else:
            segments.append(site.filter_prefix + ",".join(extra))
    if page > 1:
        segments.append(site.page_path(page))
    path = "/" + "/".join(segments)
    if not segments or not _PAGE_RE.match(segments[-1]):
        path += "/"
    query = parse_qsl(parts.query, keep_blank_values=True)
    wanted = normalize_sort(sort)
    if sort is not None:
        query = [(key, value) for key, value in query if key != site.sort_param]
        if wanted:
            query.append((site.sort_param, site.sorts[wanted]))
    return urlunsplit(("https", site.host, path, urlencode(query, safe=","), ""))


def unfiltered(url: str) -> str:
    """A search URL without its filters, page and sort: the plain search of the location.

    Idealista only links the sidebar filters (the slugs the ``filters`` command
    lists) on a search page that has no filters applied yet.
    """
    site = site_for_url(url)
    segments = [
        segment
        for segment in urlsplit(url).path.split("/")
        if segment and not _PAGE_RE.match(segment) and not _FILTER_RE.match(segment)
    ]
    return f"{site.base}/{'/'.join(segments)}/"


def url_filters(url: str) -> list[str]:
    """The filter slugs in a search URL (``['precio-hasta_500000', 'ascensor']``)."""
    for segment in urlsplit(url).path.split("/"):
        match = _FILTER_RE.match(segment)
        if match:
            return [slug for slug in match.group(1).split(",") if slug]
    return []


def listing_id(value: str | int) -> int:
    """The numeric listing ID of a listing URL (or an ID given as text)."""
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    match = _LISTING_RE.search(text)
    if not match:
        raise ValueError(f"not an Idealista listing ID or URL: {value!r}")
    return int(match.group(1))


def listing_url(value: str | int, site: str | Site | None = None) -> str:
    """The canonical URL of a listing, from its ID (plus ``site``) or any listing URL."""
    text = str(value).strip()
    if text.startswith(("http://", "https://", "www.", "idealista.")):
        if not text.startswith("http"):
            text = "https://" + text
        found = site_for_url(text)
        if site is not None and get_site(site) is not found:
            raise ValueError(f"{text} is on {found.host}, not {get_site(site).host}")
        return found.base + found.listing_path.format(id=listing_id(text))
    resolved = get_site(site or "es")
    return resolved.base + resolved.listing_path.format(id=listing_id(text))


def absolute(url: str | None, site: Site) -> str | None:
    if not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return site.base + url
    return url


__all__ = [
    "OPERATIONS",
    "PROPERTY_TYPES",
    "SITES",
    "SORTS",
    "Site",
    "absolute",
    "filter_slugs",
    "get_site",
    "is_search_url",
    "listing_id",
    "listing_url",
    "normalize_location",
    "normalize_sort",
    "paginate",
    "search_path",
    "search_url",
    "site_for_url",
    "unfiltered",
    "url_filters",
]
