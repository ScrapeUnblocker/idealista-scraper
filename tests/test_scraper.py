from __future__ import annotations

import pytest
from conftest import TargetNotFoundError, TransientError, card, listing_html, search_html

from idealista_scraper import IdealistaNotFoundError, IdealistaScraper, Listing
from idealista_scraper.scraper import page_url

BASE = "https://www.idealista.com/venta-viviendas/madrid-madrid/"
PAGE2 = BASE + "pagina-2.htm"
PAGE3 = BASE + "pagina-3.htm"
LISTING = "https://www.idealista.com/inmueble/111/"


def test_fetch_routes_through_the_country_only_when_asked(make_scraper):
    scraper, client = make_scraper({BASE: search_html([card(1)])})
    scraper.search_page("madrid-madrid")
    assert client.calls == [(BASE, {})]

    scraper, client = make_scraper({BASE: search_html([card(1)])}, country="ES")
    scraper.search_page("madrid-madrid")
    assert client.calls == [(BASE, {"proxy_country": "es"})]


def test_transient_errors_are_retried_with_doubling_backoff(make_scraper):
    retries = []
    scraper, client = make_scraper(
        {BASE: [TransientError("timeout"), TransientError("outage"), search_html([card(1)])]},
        on_retry=lambda attempt, delay, error: retries.append((attempt, delay)),
    )
    page = scraper.search_page("madrid-madrid")
    assert [item.listing_id for item in page.listings] == [1]
    assert scraper.sleeps == [1.0, 2.0]
    assert retries == [(1, 1.0), (2, 2.0)]
    assert len(client.calls) == 3


def test_retries_give_up(make_scraper):
    scraper, client = make_scraper({BASE: [TransientError("down")]}, retries=2)
    with pytest.raises(TransientError):
        scraper.search_page("madrid-madrid")
    assert len(client.calls) == 3


def test_pages_without_content_are_retried(make_scraper):
    scraper, client = make_scraper({BASE: ["<html>challenge</html>", search_html([card(1)])]})
    assert scraper.search_page("madrid-madrid").listings[0].listing_id == 1
    assert len(client.calls) == 2


def test_backoff_is_capped(make_scraper):
    scraper, _ = make_scraper(
        {BASE: [TransientError("x")] * 4 + [search_html([card(1)])]},
        retries=4,
        backoff=10,
        max_backoff=25,
    )
    scraper.search_page("madrid-madrid")
    assert scraper.sleeps == [10.0, 20.0, 25.0, 25.0]


def test_not_found_is_not_retried_and_explains_itself(make_scraper):
    scraper, client = make_scraper({BASE: TargetNotFoundError("404")})
    with pytest.raises(IdealistaNotFoundError, match="unknown location or filter slug"):
        scraper.search("madrid-madrid")
    assert len(client.calls) == 1


def test_search_collects_pages_and_stops_at_the_last_one(make_scraper):
    pages = []
    scraper, client = make_scraper(
        {
            BASE: search_html([card(1), card(2)], page=1),
            PAGE2: search_html([card(3)], page=2, has_next=False),
        }
    )
    found = scraper.search("madrid-madrid", pages=5, on_page=pages.append)
    assert [item.listing_id for item in found] == [1, 2, 3]
    assert client.urls == [BASE, PAGE2]
    assert [page.page for page in pages] == [1, 2]
    assert {item.search for item in found} == {"madrid-madrid"}


def test_search_stops_when_a_later_page_is_gone(make_scraper):
    scraper, client = make_scraper(
        {BASE: search_html([card(1)]), PAGE2: TargetNotFoundError("404")}
    )
    assert [item.listing_id for item in scraper.search("madrid-madrid", pages=3)] == [1]
    assert client.urls == [BASE, PAGE2]


def test_search_stops_when_a_page_repeats_known_listings(make_scraper):
    scraper, client = make_scraper(
        {
            BASE: search_html([card(1), card(2)]),
            PAGE2: search_html([card(2), card(1)], page=2),
            PAGE3: search_html([card(9)], page=3),
        }
    )
    assert [item.listing_id for item in scraper.search("madrid-madrid", pages=3)] == [1, 2]
    assert client.urls == [BASE, PAGE2]


def test_limit_and_professional_filter(make_scraper):
    html = search_html([card(1), card(2, professional=False), card(3), card(4, professional=False)])
    scraper, _ = make_scraper({BASE: html})
    assert [item.listing_id for item in scraper.search("madrid-madrid", limit=2)] == [1, 2]
    assert [i.listing_id for i in scraper.search("madrid-madrid", professional=False)] == [2, 4]
    assert [i.listing_id for i in scraper.search("madrid-madrid", professional=True)] == [1, 3]


def test_search_many_dedupes_and_reports_unknown_locations(make_scraper):
    other = "https://www.idealista.com/venta-viviendas/getafe-madrid/"
    bad = "https://www.idealista.com/venta-viviendas/nowhere/"
    scraper, _ = make_scraper(
        {
            BASE: search_html([card(1), card(2)]),
            other: search_html([card(2), card(3)], has_next=False),
            bad: TargetNotFoundError("404"),
        }
    )
    errors = []
    found = scraper.search_many(
        ["madrid-madrid", "nowhere", "getafe-madrid"],
        on_error=lambda location, exc: errors.append(location),
    )
    assert [item.listing_id for item in found] == [1, 2, 3]
    assert errors == ["nowhere"]
    with pytest.raises(IdealistaNotFoundError):
        scraper.search_many(["nowhere"])


def test_search_builds_urls_from_options(make_scraper):
    url = (
        "https://www.idealista.com/alquiler-viviendas/barcelona-barcelona/"
        "con-precio-hasta_1500,de-dos-dormitorios/?ordenado-por=precios-asc"
    )
    scraper, client = make_scraper({url: search_html([card(1)], has_next=False)})
    scraper.search(
        "barcelona-barcelona",
        operation="rent",
        max_price=1500,
        filters=["de-dos-dormitorios"],
        sort="price-asc",
    )
    assert client.urls == [url]


def test_search_from_a_copied_url_paginates_it(make_scraper):
    copied = BASE + "con-ascensor/?ordenado-por=precios-asc"
    second = BASE + "con-ascensor/pagina-2.htm?ordenado-por=precios-asc"
    scraper, client = make_scraper(
        {copied: search_html([card(1)]), second: search_html([card(2)], has_next=False)}
    )
    found = scraper.search(url=copied, pages=2)
    assert [item.listing_id for item in found] == [1, 2]
    assert client.urls == [copied, second]


def test_page_url_rules():
    with pytest.raises(ValueError, match="not both"):
        page_url("madrid-madrid", url=BASE)
    with pytest.raises(ValueError, match="price and size bounds"):
        page_url(url=BASE, max_price=10)
    with pytest.raises(ValueError, match="location slug"):
        page_url()


def test_filters_reads_the_unfiltered_search(make_scraper):
    scraper, client = make_scraper({BASE: search_html([card(1)])})
    page = scraper.filters(url=BASE + "con-ascensor/pagina-3.htm?ordenado-por=precios-asc")
    assert client.urls == [BASE]
    assert page.filters[0].slugs == ["de-un-dormitorio", "de-dos-dormitorios"]


def test_listing_by_id_url_or_search_result(make_scraper):
    scraper, client = make_scraper({LISTING: listing_html(111)})
    assert scraper.listing(111).listing_id == 111
    assert scraper.listing(LISTING + "?x=1").listing_id == 111
    item = Listing(listing_id=111, url=LISTING, title="Piso", site="es")
    assert scraper.listing(item).price == 1450.0
    assert client.urls == [LISTING] * 3


def test_listings_collects_errors(make_scraper):
    missing = "https://www.idealista.com/inmueble/222/"
    scraper, _ = make_scraper({LISTING: listing_html(111), missing: TargetNotFoundError("404")})
    errors = []
    found = scraper.listings(
        [111, 222], on_error=lambda item, exc: errors.append((item, type(exc)))
    )
    assert [item.listing_id for item in found] == [111]
    assert errors == [("222", IdealistaNotFoundError)]
    with pytest.raises(IdealistaNotFoundError):
        scraper.listings([222])


def test_default_client_comes_from_the_sdk(monkeypatch):
    sdk = pytest.importorskip("scrapeunblocker")
    monkeypatch.setenv("SCRAPEUNBLOCKER_KEY", "test-key-not-real")
    scraper = IdealistaScraper()
    assert isinstance(scraper._client, sdk.Client)
