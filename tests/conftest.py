"""Shared fixtures: synthetic Idealista pages and a fake ScrapeUnblocker client.

The pages mirror the markup Idealista renders on the server (result cards,
heading, pagination, filter sidebar, listing page sections), trimmed to what
the parsers read. No network access and no API credit are needed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest


def card(
    listing_id: int,
    *,
    title: str = "Piso en Calle Mayor, Sol, Madrid",
    price: str = "350.000 €",
    drop: tuple[str, str] | None = None,
    details: tuple[str, ...] = (
        "Garaje incluido",
        "3 hab.",
        "95 m²",
        "2ª planta exterior con ascensor",
    ),
    per_m2: str | None = None,
    tags: tuple[str, ...] = (),
    agency: str | None = "Inmobiliaria Ejemplo",
    professional: bool = True,
    photos: int = 12,
    media: tuple[str, ...] = ("PLAN", "VIDEO", "MAP"),
    path: str = "/inmueble/{id}/",
) -> str:
    """One ``<article class="item">`` result card."""
    href = path.format(id=listing_id)
    drop_html = (
        f'<span class="pricedown"><span class="pricedown_price">{drop[0]}</span>'
        f'<span class="pricedown_icon icon-pricedown">{drop[1]}</span></span>'
        if drop
        else ""
    )
    branding = (
        '<div class="featured-hightop-block-agent-container">'
        '<picture class="logo-branding"><a href="/pro/ejemplo/" title="Inmobiliaria Ejemplo">'
        '<img alt="logo" src="https://img.example.com/logo.gif"/></a></picture>'
        f'<div class="hightop-agent"><a href="/pro/ejemplo/"><span class="hightop-kind-agent">'
        f'Comercializa</span><span class="hightop-agent-name">\n  {agency}\n</span></a></div></div>'
        if agency
        else ""
    )
    buttons = "".join(f'<button data-button-type="{kind}"></button>' for kind in media)
    return f"""
<article class="item extended-item item-multimedia-container" data-element-id="{listing_id}"
    data-is-professional-ad="{"true" if professional else "false"}" data-online-booking="false">
  <picture class="item-multimedia">
    <div class="item-multimedia-pictures__counter"><span>1/</span><span> {photos} </span></div>
    <div class="item-gallery"><img src="https://img.example.com/{listing_id}.jpg"/></div>
    <div class="item-multimedia-shortcuts --mobile">{buttons}</div>
  </picture>
  <div class="item-info-container">
    {branding}
    <a class="item-link" href="{href}" title="{title}">
      {title}
    </a>
    <div class="price-row">
      <span class="item-price h2-simulated">
        {price.split(" ")[0]}
        <span class="txt-big">{" ".join(price.split(" ")[1:])}</span>
      </span>
      {drop_html}
      {f'<span class="item-price-by-area">{per_m2}</span>' if per_m2 else ""}
    </div>
    <div class="item-detail-char">
      {"".join(f'<span class="item-detail">{d}</span>' for d in details)}
    </div>
    <div class="item-description description"><p class="ellipsis">
      Luminoso piso
      reformado.
    </p></div>
    <div class="listing-tags-container">
      {"".join(f'<span class="listing-tags">{t}</span>' for t in tags)}
    </div>
  </div>
</article>"""


def sidebar(base: str = "/venta-viviendas/madrid-madrid/") -> str:
    def option(name: str, label: str, slug: str | None) -> str:
        link = f'<a href="{base}con-{slug}/">{label}</a>' if slug else label
        return (
            f'<li><label class="input-checkbox"><input aria-label="{label}" name="{name}" '
            f'type="checkbox" value="1"/><span><span>{link}</span></span></label></li>'
        )

    return f"""
<div class="item-form"><span class="title-label">Habitaciones</span><ul>
  {option("rooms_1", "1", "de-un-dormitorio")}
  {option("rooms_2", "2", "de-dos-dormitorios")}
</ul></div>
<div class="item-form"><span class="title-label">
  Eficiencia energética
  <span class="tooltip">Indica cuánta energía necesita una vivienda.</span>
</span><ul>
  {option("energy_high", "Alta", "eficiencia-energetica-alta")}
</ul></div>
<div class="item-form"><span class="title-label">Situación</span><ul>
  {option("free", "Disponible", None)}
</ul></div>"""


def search_html(
    cards: list[str],
    *,
    total: int = 1234,
    page: int = 1,
    has_next: bool = True,
    heading: str = "1.234 casas y pisos en Madrid",
    average: str = "Precio medio 4.500 eur/m²",
    operation: str = "sale",
    location: str = "madrid-madrid",
    with_sidebar: bool = True,
) -> str:
    """A results page: heading, cards, pagination, average price and filter sidebar."""
    nxt = '<li class="next"><a href="/next/">Siguiente</a></li>' if has_next else ""
    return f"""<!DOCTYPE html><html><head><title>idealista</title></head><body>
<script>
  var config = {{
    locale: 'es',
    operation: '1',
    operationName: '{operation}',
    typologyName: 'home',
    locationUri: '{location}',
    listingPage: {page},
    totalResults: {total}
  }};
</script>
{sidebar() if with_sidebar else ""}
<div class="listing-title"><h1 id="h1-container"><span id="h1-container__text">
  {heading}
</span></h1></div>
<div class="items-average-price">{average}</div>
<section class="items-container items-list">
{"".join(cards)}
<article class="adv noHover"><div>advert</div></article>
</section>
<div class="pagination"><ul>
  <li class="selected"><span>{page}</span></li>
  {nxt}
</ul></div>
</body></html>"""


def listing_html(listing_id: int = 111, *, private: bool = False) -> str:
    """A listing page with every section the parser reads."""
    advertiser = (
        '<div class="professional-name"><div class="name">Particular</div></div>'
        '<div class="advertiser-name-container"><span class="advertiser-name">Ana</span></div>'
        if private
        else '<div class="professional-name"><div class="name">Profesional</div>'
        '<a href="/pro/ejemplo/">Inmobiliaria Ejemplo</a></div>'
        '<div class="about-advertiser"><span class="about-advertiser-name">'
        "Inmobiliaria Ejemplo</span></div>"
    )
    return f"""<!DOCTYPE html><html><head><title>idealista</title></head><body>
<script>
  var config = {{
    locale: 'es',
    propertyId: {listing_id},
    typology: 'home',
    operation: 'rent',
    detailUrl: '/inmueble/{listing_id}/'
  }};
</script>
<section class="main-info">
  <div class="main-info__title"><h1><span class="main-info__title-main">
    Alquiler de piso en Calle Mayor
  </span></h1><span class="main-info__title-block"><span class="main-info__title-minor">
    Sol, Madrid
  </span></span></div>
  <div class="info-data">
    <span class="info-data-price"><span class="txt-bold">1.450</span> €/mes</span>
    <span class="pricedown"><span class="pricedown_price">1.500 €</span>
      <span class="pricedown_icon icon-pricedown">3%</span></span>
  </div>
  <div class="info-features">
    <span><span>80</span> m²</span>
    <span><span>2</span> hab.</span>
    <span>3ª planta exterior con ascensor</span>
  </div>
  <div class="detail-info-tags"><span>Alquiler de temporada</span></div>
</section>
<div class="adCommentsLanguage expandable"><p>
  Piso luminoso
  en el centro.
  <br/>
  <br/>
  Disponible en noviembre.
</p></div>
<div class="details-property">
  <div class="details-property-feature-one">
    <h2 class="details-property-h2">Características básicas</h2>
    <div class="details-property_features"><ul>
      <li>80 m² construidos</li><li>2 habitaciones</li><li>1 baño</li><li>Balcón</li>
    </ul></div>
    <h2 class="details-property-h2">Edificio</h2>
    <div class="details-property_features"><ul>
      <li>3ª planta exterior</li><li>Con ascensor</li>
    </ul></div>
  </div>
  <div class="details-property-feature-two">
    <h2 class="details-property-h2">Certificado energético</h2>
    <div class="details-property_features"><ul>
      <li><span>Consumo:</span><span class="icon-energy-c-e">234 kWh/m² año</span></li>
      <li><span>Emisiones:</span><span class="icon-energy-c-d">42 kg CO2/m² año</span></li>
    </ul></div>
  </div>
</div>
<div class="price-features__container">
  <p class="flex-feature"><span>Precio del inmueble:</span><span>1.450 €/mes</span></p>
  <p class="flex-feature squaredmeterprice"><span>Precio por m²:</span><span>18,13 €/m²</span></p>
  <p class="flex-feature"><span>Fianza de 2 meses</span></p>
</div>
<div id="headerMap"><ul>
  <li class="header-map-list">Calle Mayor</li>
  <li class="header-map-list">Barrio Sol</li>
  <li class="header-map-list">Madrid</li>
</ul></div>
{advertiser}
<div class="ad-reference-container"><p class="txt-ref">REF-77</p></div>
<p class="stats-text">Anuncio actualizado el 9 de octubre</p>
<script>
  var adMultimediasInfo = {{ fullScreenGalleryPics: [
    {{aspectRatioId:1,"isPlan":false,imageDataService:"https://img.example.com/a.jpg",tag:"Salón"}},
    {{aspectRatioId:1,"isPlan":true,imageDataService:"https://img.example.com/plan.jpg",tag:"Plano"}},
    {{"isPlan":false,imageDataService:"https://img.example.com/a.jpg",tag:"Salón"}}
  ], other: 1 }};
</script>
</body></html>"""


class FakeClient:
    """Stands in for ``scrapeunblocker.Client``: answers from a URL -> response map.

    A response may be HTML, an exception instance (raised) or a list of those
    (consumed one per call, the last one repeating).
    """

    def __init__(self, responses: dict[str, Any] | Callable[[str], Any] | None = None) -> None:
        self.responses = responses if responses is not None else {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_page_source(self, url: str, **options: Any) -> Any:
        self.calls.append((url, options))
        if callable(self.responses):
            answer = self.responses(url)
        else:
            if url not in self.responses:
                raise AssertionError(f"unexpected URL fetched: {url}")
            answer = self.responses[url]
            if isinstance(answer, list):
                answer = answer.pop(0) if len(answer) > 1 else answer[0]
        if isinstance(answer, BaseException):
            raise answer
        return answer

    @property
    def urls(self) -> list[str]:
        return [url for url, _ in self.calls]


class TransientError(Exception):
    """Plays the part of a retryable SDK error (timeouts, outages, ...)."""


class TargetNotFoundError(Exception):
    """Same class name as the SDK's 404 error, which the scraper maps to not-found."""


@pytest.fixture
def make_scraper():
    from idealista_scraper import IdealistaScraper

    def build(responses: Any, **options: Any):
        client = FakeClient(responses)
        sleeps: list[float] = []
        options.setdefault("transient_errors", (TransientError,))
        options.setdefault("backoff", 1.0)
        scraper = IdealistaScraper(client=client, sleep=sleeps.append, **options)
        scraper.sleeps = sleeps  # type: ignore[attr-defined]
        return scraper, client

    return build
