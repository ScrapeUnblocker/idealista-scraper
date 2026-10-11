"""Turn Idealista HTML into typed records.

Idealista renders its search results and listing pages on the server, so the
rendered HTML returned by ScrapeUnblocker carries everything: the property
cards, the result count, the filter sidebar and, on a listing page, the
feature lists, energy certificate, advertiser and photo gallery. The parsers
here read that markup; nothing is guessed from free text except the small,
well-defined card details (``3 hab.``, ``65 m²``, ``2ª planta exterior con
ascensor``, ``Box compreso``, ``T2``) in Spanish, Italian and Portuguese.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag

from .models import (
    EnergyRating,
    FilterGroup,
    FilterOption,
    Listing,
    ListingDetails,
    Photo,
    SearchPage,
)
from .urls import Site, absolute, listing_id, site_for_url, url_filters


class IdealistaError(Exception):
    """Base class of this package's errors."""


class IdealistaNotFoundError(IdealistaError):
    """Idealista answered 404: unknown listing, unknown location or filter, or no results."""


class IdealistaParseError(IdealistaError):
    """A page came back without the expected content (for example a bot challenge)."""


_SPACE_RE = re.compile(r"\s+")
_NUMBER_RE = re.compile(r"\d[\d.]*(?:,\d+)?")
_PERCENT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_CHALLENGE_MARKERS = ("captcha-delivery.com", "geo.captcha", "px-captcha", "cf-chl")
_BREAK = "[[br]]"

#: Rent periods as Idealista writes them after the price ("1.550 €/mes").
PERIODS = {
    "mes": "month",
    "mese": "month",
    "mês": "month",
    "mensal": "month",
    "día": "day",
    "dia": "day",
    "giorno": "day",
    "noche": "night",
    "notte": "night",
    "noite": "night",
    "semana": "week",
    "settimana": "week",
    "año": "year",
    "anno": "year",
    "ano": "year",
}

_TITLE_RE = re.compile(r"^(.*?)\s(?:en|in|na|no|nas|nos|em)\s(?!banda\b)(.+)$")
_BEDROOMS_RE = re.compile(r"^(\d+)\s*hab\.?$", re.I)
_TYPOLOGY_RE = re.compile(r"^T(\d+)(?:\s*\+\s*\d+)?$")
_ROOMS_RE = re.compile(r"^(\d+)\s*local[ei]$", re.I)
_SIZE_RE = re.compile(r"^(\d[\d.,]*)\s*m²")
_BATHROOMS_RE = re.compile(r"^(\d+)\s+(?:bañ|bagn|casas? de banho|wc)", re.I)
_PARKING_RE = re.compile(r"^(?:garaje|garagem|box|posto auto|plaza de garaje)\b", re.I)
_OPTIONAL_RE = re.compile(r"\b(?:opc|opz|opcional|opzionale|opcionais)\b", re.I)
_LIFT_RE = re.compile(r"\b(con|sin|senza|com|sem)\s+(?:ascensor|ascensore|elevador)\b", re.I)
_SIDE_RE = re.compile(r"\b(exterior|interior)\b", re.I)
_FLOOR_WORDS_RE = re.compile(
    r"\b(?:planta|bajo|entreplanta|s[oó]tano|semis[oó]tano|piano|andar|cave|"
    r"r[eé]s do ch[aã]o|rialzato|seminterrato|sobreloja)\b",
    re.I,
)
_FLOOR_NUMBER_RE = re.compile(r"^(-?\d+)\s*[ªº°]?\s*(?:planta|piano|andar)?\b", re.I)
_GROUND_RE = re.compile(r"^(?:bajo|planta baja|piano terra|r[eé]s do ch[aã]o)\b", re.I)
_M2_LINE_RE = re.compile(r"m²\s*:\s*(.+)$")
_ENERGY_CLASS_RE = re.compile(r"icon-energy-c-([a-z0-9]+)$", re.I)
_RATING_RE = re.compile(r"^[a-g][+1-4]{0,2}$", re.I)
_PHOTO_RE = re.compile(r"\{[^{}]*\}")


# ---------------------------------------------------------------------- #
# Small helpers
# ---------------------------------------------------------------------- #


def clean(text: str | None) -> str:
    """Collapse whitespace (Idealista's HTML is indented across lines)."""
    return _SPACE_RE.sub(" ", text or "").strip()


def _text(element: Tag | None) -> str | None:
    if element is None:
        return None
    return clean(element.get_text(" ")) or None


def parse_amount(text: str | None) -> float | None:
    """``"2.595.000 €"`` -> 2595000.0, ``"28,18 €/m²"`` -> 28.18 (European number format)."""
    if not text:
        return None
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    raw = match.group(0)
    whole, _, decimals = raw.partition(",")
    whole = whole.replace(".", "")
    try:
        return float(f"{whole}.{decimals}" if decimals else whole)
    except ValueError:
        return None


def parse_price(text: str | None) -> tuple[float | None, str | None]:
    """``"1.550 €/mes"`` -> ``(1550.0, "month")``; ``"295.000 €"`` -> ``(295000.0, None)``."""
    amount = parse_amount(text)
    period = None
    if text and "/" in text:
        word = clean(text.rsplit("/", 1)[1]).lower().rstrip(".")
        period = PERIODS.get(word, word or None)
    return amount, period


def _percent(text: str | None) -> float | None:
    match = _PERCENT_RE.search(text or "")
    return float(match.group(1).replace(",", ".")) if match else None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def split_title(title: str | None) -> tuple[str | None, str | None]:
    """``"Piso en Calle Mayor, Sol, Madrid"`` -> ``("Piso", "Calle Mayor, Sol, Madrid")``."""
    match = _TITLE_RE.match(clean(title))
    if not match:
        return None, None
    return match.group(1), match.group(2)


def parse_floor(text: str) -> dict[str, Any] | None:
    """Read a floor line such as ``"2ª planta exterior con ascensor"``, ``"Piano rialzato
    senza ascensore"`` or ``"Rés do chão sem elevador"``; None for any other text."""
    lift = _LIFT_RE.search(text)
    side = _SIDE_RE.search(text)
    if not lift and not side and not _FLOOR_WORDS_RE.search(text):
        return None
    floor = _LIFT_RE.sub(" ", text)
    floor = clean(_SIDE_RE.sub(" ", floor)) or None
    number = None
    if floor:
        found = _FLOOR_NUMBER_RE.match(floor)
        if found:
            number = int(found.group(1))
        elif _GROUND_RE.match(floor):
            number = 0
    return {
        "floor": floor,
        "floor_number": number,
        "exterior": None if not side else side.group(1).lower() == "exterior",
        "lift": None if not lift else lift.group(1).lower() in ("con", "com"),
    }


def read_details(items: list[str]) -> dict[str, Any]:
    """Structured fields from the short facts of a card or listing header."""
    found: dict[str, Any] = {}
    for item in items:
        text = clean(item)
        if not text:
            continue
        if _PARKING_RE.match(text) and "parking" not in found:
            found["parking"] = "optional" if _OPTIONAL_RE.search(text) else "included"
            if found["parking"] == "optional":
                found["parking_price"] = parse_amount(text)
            continue
        match = _BEDROOMS_RE.match(text) or _TYPOLOGY_RE.match(text)
        if match and "bedrooms" not in found:
            found["bedrooms"] = int(match.group(1))
            continue
        match = _ROOMS_RE.match(text)
        if match and "rooms" not in found:
            found["rooms"] = int(match.group(1))
            continue
        match = _SIZE_RE.match(text)
        if match and "size_m2" not in found:
            found["size_m2"] = parse_amount(match.group(1))
            continue
        if "floor" not in found:
            floor = parse_floor(text)
            if floor is not None:
                found.update(floor)
    return found


def is_challenge(html: str) -> bool:
    """True when the HTML is a bot-challenge page rather than Idealista content."""
    head = html[:20000].lower()
    return any(marker in head for marker in _CHALLENGE_MARKERS)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "html.parser")


def _config_value(html: str, key: str) -> str | None:
    match = re.search(rf"\b{re.escape(key)}\s*:\s*'?([^,'\n}}]*)'?", html)
    value = match.group(1).strip() if match else None
    return value or None


# ---------------------------------------------------------------------- #
# Search pages
# ---------------------------------------------------------------------- #


def _media(card: Tag) -> list[str]:
    buttons = card.select(".item-multimedia-shortcuts.--mobile button[data-button-type]")
    if not buttons:
        buttons = card.select("button[data-button-type]")
    media: list[str] = []
    for button in buttons:
        kind = str(button.get("data-button-type") or "").strip().lower()
        if kind and kind != "map" and kind not in media:
            media.append(kind)
    return media


def parse_card(
    card: Tag, site: Site, *, position: int | None = None, page: int | None = None
) -> Listing | None:
    """One ``<article class="item">`` of a results page as a :class:`Listing`."""
    element_id = _int(card.get("data-element-id"))
    link = card.select_one("a.item-link")
    if element_id is None or link is None:
        return None
    title = clean(str(link.get("title") or "")) or _text(link) or ""
    property_type, address = split_title(title)
    price, period = parse_price(_text(card.select_one(".item-price")))
    drop = card.select_one(".pricedown")
    original = parse_amount(_text(drop.select_one(".pricedown_price"))) if drop else None
    details = [
        text for text in (_text(x) for x in card.select(".item-detail-char .item-detail")) if text
    ]
    tags = [text for text in (_text(x) for x in card.select(".listing-tags")) if text]
    logo = card.select_one(".logo-branding a")
    logo_img = card.select_one(".logo-branding img")
    agency = _text(card.select_one(".hightop-agent-name"))
    if not agency and logo is not None:
        agency = clean(str(logo.get("title") or "")) or None
    counter = _text(card.select_one(".item-multimedia-pictures__counter"))
    photos = _int(counter.split("/")[-1].strip()) if counter and "/" in counter else None
    image = card.select_one(".item-gallery img")
    professional = card.get("data-is-professional-ad")
    listing = Listing(
        listing_id=element_id,
        url=absolute(str(link.get("href") or ""), site) or site.base,
        title=title,
        site=site.code,
        property_type=property_type,
        address=address,
        price=price,
        price_period=period,
        original_price=original,
        price_drop_percent=_percent(_text(drop.select_one(".pricedown_icon"))) if drop else None,
        price_per_m2=parse_amount(_text(card.select_one(".item-price-by-area"))),
        details=details,
        tags=tags,
        description=_text(card.select_one(".item-description")),
        professional=None if professional is None else professional == "true",
        agency_name=agency,
        agency_url=absolute(str(logo.get("href")), site) if logo is not None else None,
        agency_logo=str(logo_img.get("src")) if logo_img is not None else None,
        photos=photos,
        media=_media(card),
        image=str(image.get("src")) if image is not None and image.get("src") else None,
        position=position,
        page=page,
    )
    for key, value in read_details(details).items():
        setattr(listing, key, value)
    return listing


def _option_slug(anchor: Tag | None, current: set[str]) -> str | None:
    """The slug an option link adds to (or, for a selected option, removes from) the URL."""
    if anchor is None:
        return None
    linked = set(url_filters(str(anchor.get("href") or "")))
    for changed in (linked - current, current - linked):
        if len(changed) == 1:
            return next(iter(changed))
    return None


def parse_filters(soup: BeautifulSoup, url: str) -> list[FilterGroup]:
    """The checkbox filters of the search sidebar, with the slug each one adds to the URL."""
    current = set(url_filters(url))
    groups: list[FilterGroup] = []
    for form in soup.select(".item-form"):
        title = form.find(class_="title-label", recursive=False) or form.select_one(".title-label")
        if title is None or title.find_parent(class_="item-form") is not form:
            continue
        options: list[FilterOption] = []
        for item in form.select("li"):
            box = item.select_one("input[type=checkbox], input[type=radio]")
            if box is None:
                continue
            anchor = item.select_one("a[href]")
            label = clean(str(box.get("aria-label") or "")) or _text(anchor) or _text(item) or ""
            slug = _option_slug(anchor, current)
            options.append(FilterOption(label=label, slug=slug, selected=box.has_attr("checked")))
        if options and any(option.slug for option in options):
            own = clean(" ".join(title.find_all(string=True, recursive=False)))
            groups.append(FilterGroup(label=own or _text(title) or "", options=options))
    return groups


def parse_search_page(html: str, url: str, page: int | None = None) -> SearchPage:
    """A results page as a :class:`SearchPage` (listings, total, filters, next page)."""
    site = site_for_url(url)
    soup = _soup(html)
    heading = soup.select_one("#h1-container")
    cards = soup.select("article.item[data-element-id]")
    if heading is None and not cards:
        reason = "a bot challenge" if is_challenge(html) else "no search results on it"
        raise IdealistaParseError(f"Idealista returned a page with {reason}: {url}")
    selected = _int(_text(soup.select_one(".pagination li.selected")))
    number = selected or _int(_config_value(html, "listingPage")) or page or 1
    listings: list[Listing] = []
    for index, card in enumerate(cards, start=1):
        listing = parse_card(card, site, position=index, page=number)
        if listing is not None:
            listings.append(listing)
    total = _int(_config_value(html, "totalResults"))
    if total is None and heading is not None:
        amount = parse_amount(_text(heading))
        total = int(amount) if amount is not None else None
    return SearchPage(
        url=url,
        site=site.code,
        page=number,
        listings=listings,
        total=total,
        heading=_text(heading),
        operation=_config_value(html, "operationName"),
        property_type=_config_value(html, "typologyName"),
        location=_config_value(html, "locationUri"),
        average_price_per_m2=parse_amount(_text(soup.select_one(".items-average-price"))),
        has_next=soup.select_one(".pagination li.next a") is not None,
        filters=parse_filters(soup, url),
    )


# ---------------------------------------------------------------------- #
# Listing pages
# ---------------------------------------------------------------------- #


def _rich_text(element: Tag | None) -> str | None:
    """Text with Idealista's line breaks kept (``<br>`` and paragraphs)."""
    if element is None:
        return None
    for br in element.find_all("br"):
        br.replace_with(_BREAK)
    for paragraph in element.find_all("p"):
        paragraph.append(_BREAK)
    text = clean(element.get_text(" "))
    lines = [line.strip() for line in text.replace(_BREAK, "\n").split("\n")]
    joined = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", joined) or None


def _energy(soup: BeautifulSoup) -> list[EnergyRating]:
    ratings: list[EnergyRating] = []
    for span in soup.select(".details-property [class*=icon-energy-c-]"):
        classes = " ".join(span.get("class") or [])
        code = _ENERGY_CLASS_RE.search(classes)
        title = clean(str(span.get("title") or ""))
        rating = None
        for candidate in (title, code.group(1) if code else ""):
            if candidate and _RATING_RE.match(candidate):
                rating = candidate.upper()
                break
        row = span.find_parent("li")
        value = _text(span)
        label = None
        if row is not None:
            first = row.find("span")
            if first is not None and first is not span:
                label = _text(first)
            whole = clean(row.get_text(" "))
            if label is None and ":" in whole:
                label = whole.split(":", 1)[0].strip()
            if value is None:
                rest = whole.split(":", 1)[1] if ":" in whole else ""
                value = clean(rest).strip("() ") or None
        ratings.append(
            EnergyRating(label=(label or "").rstrip(": ") or None, rating=rating, value=value)
        )
    return ratings


def _features(soup: BeautifulSoup) -> dict[str, list[str]]:
    features: dict[str, list[str]] = {}
    for heading in soup.select(".details-property h2.details-property-h2"):
        name = _text(heading)
        block = heading.find_next_sibling("div")
        if not name or block is None:
            continue
        items = [text for text in (_text(li) for li in block.select("li")) if text]
        if items:
            features.setdefault(name, items)
    return features


def _photos(html: str, site: Site) -> list[Photo]:
    start = html.find("fullScreenGalleryPics")
    if start < 0:
        return []
    bracket = html.find("[", start)
    photos: list[Photo] = []
    seen: set[str] = set()
    position = bracket + 1
    while True:
        while position < len(html) and html[position] in " \t\r\n,":
            position += 1
        match = _PHOTO_RE.match(html, position)
        if not match:
            break
        body = match.group(0)
        found = re.search(r'imageDataService"?\s*:\s*"([^"]+)"', body)
        if found and found.group(1) not in seen:
            seen.add(found.group(1))
            tag = re.search(r'\btag"?\s*:\s*"([^"]*)"', body)
            plan = re.search(r'"?isPlan"?\s*:\s*(true|false)', body)
            photos.append(
                Photo(
                    url=absolute(found.group(1), site) or found.group(1),
                    tag=(tag.group(1) or None) if tag else None,
                    floor_plan=bool(plan and plan.group(1) == "true"),
                )
            )
        position = match.end()
    return photos


def _tags(soup: BeautifulSoup) -> list[str]:
    box = soup.select_one(".detail-info-tags")
    if box is None:
        return []
    spans = [text for text in (_text(span) for span in box.select("span")) if text]
    tags: list[str] = []
    for tag in spans or [_text(box) or ""]:
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def parse_listing_page(html: str, url: str) -> ListingDetails:
    """A listing page as :class:`ListingDetails`."""
    site = site_for_url(url)
    soup = _soup(html)
    main = soup.select_one(".main-info__title-main")
    property_id = _int(_config_value(html, "propertyId"))
    if main is None and property_id is None:
        reason = "a bot challenge" if is_challenge(html) else "no listing on it"
        raise IdealistaParseError(f"Idealista returned a page with {reason}: {url}")
    price_box = soup.select_one(".info-data-price")
    price, period = parse_price(_text(price_box))
    drop = soup.select_one(".info-data .pricedown")
    price_details = [
        text
        for text in (_text(x) for x in soup.select(".price-features__container .flex-feature"))
        if text
    ]
    per_m2 = None
    for line in price_details:
        found = _M2_LINE_RE.search(line)
        if found:
            per_m2 = parse_amount(found.group(1))
            break
    summary = [text for text in (_text(x) for x in soup.select(".info-features > span")) if text]
    features = _features(soup)
    advertiser_link = soup.select_one(
        ".professional-name a[href*='/pro/'], .about-advertiser a[href*='/pro/'], "
        ".advertiser-name-container a[href*='/pro/']"
    )
    kind = soup.select_one(".professional-name .name")
    details = ListingDetails(
        listing_id=property_id or listing_id(urlsplit(url).path),
        url=url,
        site=site.code,
        title=_text(main),
        area=_text(soup.select_one(".main-info__title-minor")),
        operation=_config_value(html, "operation"),
        typology=_config_value(html, "typology"),
        price=price,
        price_period=period,
        original_price=parse_amount(_text(drop.select_one(".pricedown_price"))) if drop else None,
        price_drop_percent=_percent(_text(drop.select_one(".pricedown_icon"))) if drop else None,
        price_per_m2=per_m2,
        price_details=price_details,
        summary=summary,
        tags=_tags(soup),
        features=features,
        energy_certificate=_energy(soup),
        description=_rich_text(soup.select_one(".adCommentsLanguage")),
        location=[
            text
            for text in (_text(li) for li in soup.select("#headerMap li.header-map-list"))
            if text
        ],
        reference=_text(soup.select_one(".txt-ref")),
        advertiser_name=_text(soup.select_one(".about-advertiser-name"))
        or _text(soup.select_one(".advertiser-name")),
        advertiser_type=_text(kind),
        advertiser_url=absolute(str(advertiser_link.get("href")), site)
        if advertiser_link
        else None,
        last_updated=_text(soup.select_one(".stats-text"))
        or _text(soup.select_one(".date-update-block")),
        photos=_photos(html, site),
    )
    facts = read_details(summary)
    every_feature = [item for items in features.values() for item in items]
    for key, value in read_details(every_feature).items():
        facts.setdefault(key, value)
    for key, value in facts.items():
        setattr(details, key, value)
    for item in every_feature:
        found = _BATHROOMS_RE.match(item)
        if found:
            details.bathrooms = int(found.group(1))
            break
    return details


__all__ = [
    "IdealistaError",
    "IdealistaNotFoundError",
    "IdealistaParseError",
    "clean",
    "is_challenge",
    "parse_amount",
    "parse_card",
    "parse_filters",
    "parse_floor",
    "parse_listing_page",
    "parse_price",
    "parse_search_page",
    "read_details",
    "split_title",
]
