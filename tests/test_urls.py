from __future__ import annotations

import pytest

from idealista_scraper.urls import (
    filter_slugs,
    get_site,
    listing_id,
    listing_url,
    normalize_sort,
    paginate,
    search_url,
    unfiltered,
    url_filters,
)


def test_spanish_search_url_with_filters_page_and_sort():
    url = search_url(
        "madrid-madrid",
        min_price=200000,
        max_price=500000,
        min_size=60,
        filters=["de-dos-dormitorios", "de-tres-dormitorios"],
        sort="newest",
        page=2,
    )
    assert url == (
        "https://www.idealista.com/venta-viviendas/madrid-madrid/"
        "con-precio-hasta_500000,precio-desde_200000,metros-cuadrados-mas-de_60,"
        "de-dos-dormitorios,de-tres-dormitorios/pagina-2.htm?ordenado-por=fecha-publicacion-desc"
    )


def test_page_one_and_relevance_add_nothing():
    assert search_url("madrid-madrid") == "https://www.idealista.com/venta-viviendas/madrid-madrid/"
    assert search_url("madrid-madrid", sort="relevance") == search_url("madrid-madrid")


def test_italian_and_portuguese_vocabulary():
    assert search_url(
        "milano-milano",
        site="it",
        min_price=300000,
        max_price=500000,
        min_size=60,
        page=2,
        sort="newest",
    ) == (
        "https://www.idealista.it/vendita-case/milano-milano/"
        "con-prezzo_500000,prezzo-min_300000,dimensione_60/lista-2.htm?ordine=pubblicazione-desc"
    )
    assert search_url(
        "lisboa",
        site="pt",
        min_price=300000,
        max_price=600000,
        min_size=60,
        page=2,
        sort="newest",
    ) == (
        "https://www.idealista.pt/comprar-casas/lisboa/"
        "com-preco-max_600000,preco-min_300000,tamanho-min_60/pagina-2?ordem=atualizado-desc"
    )
    assert search_url("roma-roma", site="it", operation="rent").startswith(
        "https://www.idealista.it/affitto-case/roma-roma/"
    )
    assert search_url("porto", site="pt", operation="rent", max_size=90).endswith(
        "/arrendar-casas/porto/com-tamanho-max_90/"
    )


def test_property_types_and_operations():
    assert "/alquiler-habitacion/" in search_url(
        "barcelona-barcelona", operation="rent", property_type="rooms"
    )
    assert "/venta-oficinas/" in search_url("madrid-madrid", property_type="offices")
    assert "/comprar-empreendimentos/" in search_url("lisboa", site="pt", property_type="new-homes")
    with pytest.raises(ValueError, match="rent-only"):
        search_url("madrid-madrid", property_type="rooms")
    with pytest.raises(ValueError, match="no 'rooms' search"):
        search_url("lisboa", site="pt", operation="rent", property_type="rooms")
    with pytest.raises(ValueError, match="unknown operation"):
        search_url("madrid-madrid", operation="lease")


def test_location_slug_is_validated():
    assert search_url("Madrid/Centro/").endswith("/venta-viviendas/madrid/centro/")
    with pytest.raises(ValueError, match="location slug"):
        search_url("Madrid Centro")


def test_filter_slugs_accept_prefixes_and_commas_and_reject_junk():
    assert filter_slugs("es", filters=["con-ascensor", "terraza, garaje", "ascensor"]) == [
        "ascensor",
        "terraza",
        "garaje",
    ]
    with pytest.raises(ValueError, match="filter slug"):
        filter_slugs("es", filters=["two words"])
    with pytest.raises(ValueError, match="min_price"):
        filter_slugs("es", min_price=5, max_price=1)


def test_sorts_are_mapped_per_site():
    assert normalize_sort("PRICE_ASC") == "price-asc"
    assert normalize_sort("relevance") is None
    with pytest.raises(ValueError, match="unknown sort"):
        normalize_sort("cheapest")
    assert search_url("roma-roma", site="it", sort="price-drop").endswith("?ordine=queda-desc")
    assert search_url("lisboa", site="pt", sort="price-m2-asc").endswith("?ordem=preco_medio-asc")


def test_paginate_keeps_filters_and_query_and_replaces_page_and_sort():
    url = (
        "https://www.idealista.com/venta-viviendas/madrid-madrid/con-precio-hasta_500000/"
        "pagina-3.htm?ordenado-por=precios-asc"
    )
    assert paginate(url, page=5, sort="price-drop", filters=["ascensor"]) == (
        "https://www.idealista.com/venta-viviendas/madrid-madrid/con-precio-hasta_500000,ascensor/"
        "pagina-5.htm?ordenado-por=rebajas-desc"
    )
    assert paginate(url, page=1) == (
        "https://www.idealista.com/venta-viviendas/madrid-madrid/con-precio-hasta_500000/"
        "?ordenado-por=precios-asc"
    )
    assert paginate("https://idealista.pt/comprar-casas/lisboa/pagina-4", page=2) == (
        "https://www.idealista.pt/comprar-casas/lisboa/pagina-2"
    )
    with pytest.raises(ValueError, match="not an Idealista URL"):
        paginate("https://example.com/venta-viviendas/madrid/", page=2)


def test_unfiltered_and_url_filters():
    url = "https://www.idealista.it/vendita-case/milano-milano/con-prezzo_500000,ascensori/lista-2.htm?ordine=x"
    assert url_filters(url) == ["prezzo_500000", "ascensori"]
    assert unfiltered(url) == "https://www.idealista.it/vendita-case/milano-milano/"


def test_listing_urls_and_ids():
    assert listing_url(112272495) == "https://www.idealista.com/inmueble/112272495/"
    assert listing_url("36193363", "it") == "https://www.idealista.it/immobile/36193363/"
    assert (
        listing_url("www.idealista.pt/imovel/34665653/?x=1")
        == "https://www.idealista.pt/imovel/34665653/"
    )
    assert listing_id("https://www.idealista.com/inmueble/42/foto/1/") == 42
    with pytest.raises(ValueError):
        listing_id("not-a-listing")
    with pytest.raises(ValueError, match="is on www.idealista.it"):
        listing_url("https://www.idealista.it/immobile/1/", "es")


def test_get_site_by_code_or_host():
    assert get_site("PT").host == "www.idealista.pt"
    assert get_site("https://www.idealista.it/x").code == "it"
    with pytest.raises(ValueError, match="unknown Idealista site"):
        get_site("fr")
