from __future__ import annotations

import pytest
from conftest import card, listing_html, search_html

from idealista_scraper import IdealistaParseError, parse_listing_page, parse_search_page
from idealista_scraper.parsing import (
    parse_amount,
    parse_floor,
    parse_price,
    read_details,
    split_title,
)

URL = "https://www.idealista.com/venta-viviendas/madrid-madrid/"


def test_amounts_use_european_number_format():
    assert parse_amount("2.595.000 €") == 2595000.0
    assert parse_amount("28,18 €/m²") == 28.18
    assert parse_amount("Precio medio 6.919 eur/m²") == 6919.0
    assert parse_amount("sin precio") is None
    assert parse_price("1.550 €/mes") == (1550.0, "month")
    assert parse_price("295.000 €") == (295000.0, None)
    assert parse_price("80 €/día") == (80.0, "day")


def test_title_split_handles_three_languages():
    assert split_title("Piso en Calle Mayor, Sol, Madrid") == ("Piso", "Calle Mayor, Sol, Madrid")
    assert split_title("Casa o chalet independiente en Aravaca, Madrid") == (
        "Casa o chalet independiente",
        "Aravaca, Madrid",
    )
    assert split_title("Bilocale in Via Roma, 4, Milano") == ("Bilocale", "Via Roma, 4, Milano")
    assert split_title("Apartamento T2 na Rua Augusta, Baixa") == (
        "Apartamento T2",
        "Rua Augusta, Baixa",
    )
    assert split_title("Moradia em banda no Bairro Azul, Lisboa") == (
        "Moradia em banda",
        "Bairro Azul, Lisboa",
    )
    assert split_title("Untitled") == (None, None)


@pytest.mark.parametrize(
    ("text", "floor", "number", "exterior", "lift"),
    [
        ("2ª planta exterior con ascensor", "2ª planta", 2, True, True),
        ("Bajo interior sin ascensor", "Bajo", 0, False, False),
        ("exterior con ascensor", None, None, True, True),
        ("1º piano senza ascensore", "1º piano", 1, None, False),
        ("Piano rialzato con ascensore", "Piano rialzato", None, None, True),
        ("Rés do chão sem elevador", "Rés do chão", 0, None, False),
        ("7º andar com elevador", "7º andar", 7, None, True),
    ],
)
def test_floor_lines(text, floor, number, exterior, lift):
    assert parse_floor(text) == {
        "floor": floor,
        "floor_number": number,
        "exterior": exterior,
        "lift": lift,
    }


def test_floor_parser_ignores_other_facts():
    assert parse_floor("Publicado ayer") is None
    assert parse_floor("Garaje incluido") is None


def test_card_details_in_three_languages():
    assert read_details(["Garaje opc. 35.000 €", "3 hab.", "115 m²", "5ª planta exterior"]) == {
        "parking": "optional",
        "parking_price": 35000.0,
        "bedrooms": 3,
        "size_m2": 115.0,
        "floor": "5ª planta",
        "floor_number": 5,
        "exterior": True,
        "lift": None,
    }
    italian = read_details(["Box compreso", "3 locali", "76 m²", "1º piano con ascensore"])
    assert italian["parking"] == "included" and italian["rooms"] == 3 and "bedrooms" not in italian
    portuguese = read_details(["Garagem incluída", "T2", "151 m² área bruta", "Rés do chão"])
    assert portuguese["bedrooms"] == 2 and portuguese["size_m2"] == 151.0
    assert portuguese["floor_number"] == 0


def test_search_page_metadata():
    page = parse_search_page(search_html([card(1), card(2)], total=19085, page=1), URL)
    assert page.total == 19085
    assert page.page == 1
    assert page.heading == "1.234 casas y pisos en Madrid"
    assert page.operation == "sale"
    assert page.property_type == "home"
    assert page.location == "madrid-madrid"
    assert page.average_price_per_m2 == 4500.0
    assert page.has_next is True
    assert [item.listing_id for item in page.listings] == [1, 2]
    assert [item.position for item in page.listings] == [1, 2]


def test_card_fields():
    html = search_html(
        [
            card(
                112272495,
                price="2.595.000 €",
                drop=("2.695.000 €", "4%"),
                tags=("Lujo",),
                media=("PLAN", "VIRTUAL_TOUR_3D", "VIDEO", "MAP"),
                photos=39,
            )
        ]
    )
    item = parse_search_page(html, URL).listings[0]
    assert item.url == "https://www.idealista.com/inmueble/112272495/"
    assert item.title == "Piso en Calle Mayor, Sol, Madrid"
    assert item.property_type == "Piso"
    assert item.address == "Calle Mayor, Sol, Madrid"
    assert item.price == 2595000.0 and item.currency == "EUR" and item.price_period is None
    assert item.original_price == 2695000.0 and item.price_drop_percent == 4.0
    assert item.bedrooms == 3 and item.size_m2 == 95.0
    assert item.floor == "2ª planta" and item.floor_number == 2
    assert item.exterior is True and item.lift is True and item.parking == "included"
    assert item.tags == ["Lujo"]
    assert item.description == "Luminoso piso reformado."
    assert item.professional is True
    assert item.agency_name == "Inmobiliaria Ejemplo"
    assert item.agency_url == "https://www.idealista.com/pro/ejemplo/"
    assert item.photos == 39
    assert item.media == ["plan", "virtual_tour_3d", "video"]
    assert item.image == "https://img.example.com/112272495.jpg"


def test_rent_card_private_seller_and_price_per_m2():
    html = search_html(
        [card(5, price="1.234 €/mes", agency=None, professional=False, per_m2="17,63 €/m²")]
    )
    item = parse_search_page(
        html, "https://www.idealista.com/alquiler-viviendas/barcelona-barcelona/"
    ).listings[0]
    assert item.price == 1234.0 and item.price_period == "month"
    assert item.price_per_m2 == 17.63
    assert item.professional is False and item.agency_name is None and item.agency_url is None


def test_italian_card_urls_are_absolute_to_the_right_site():
    html = search_html(
        [card(36193363, title="Bilocale in Via Roma, Milano", path="/immobile/{id}/")]
    )
    item = parse_search_page(html, "https://www.idealista.it/vendita-case/milano-milano/").listings[
        0
    ]
    assert item.url == "https://www.idealista.it/immobile/36193363/"
    assert item.site == "it"


def test_sidebar_filters_with_slugs_and_clean_labels():
    page = parse_search_page(search_html([card(1)]), URL)
    assert [group.label for group in page.filters] == ["Habitaciones", "Eficiencia energética"]
    rooms = page.filters[0]
    assert rooms.slugs == ["de-un-dormitorio", "de-dos-dormitorios"]
    assert [option.label for option in rooms.options] == ["1", "2"]


def test_last_page_and_missing_total():
    html = search_html([card(1)], has_next=False).replace("totalResults: 1234", "")
    page = parse_search_page(html, URL)
    assert page.has_next is False
    assert page.total == 1234  # from the heading


def test_page_without_results_is_a_parse_error():
    with pytest.raises(IdealistaParseError, match="bot challenge"):
        parse_search_page(
            '<html><script src="https://ct.captcha-delivery.com/c.js"></script></html>', URL
        )
    with pytest.raises(IdealistaParseError, match="no search results"):
        parse_search_page("<html><body>maintenance</body></html>", URL)


def test_listing_page():
    url = "https://www.idealista.com/inmueble/111/"
    item = parse_listing_page(listing_html(111), url)
    assert item.listing_id == 111
    assert item.title == "Alquiler de piso en Calle Mayor"
    assert item.area == "Sol, Madrid"
    assert item.operation == "rent" and item.typology == "home"
    assert item.price == 1450.0 and item.price_period == "month"
    assert item.original_price == 1500.0 and item.price_drop_percent == 3.0
    assert item.price_per_m2 == 18.13
    assert item.price_details[-1] == "Fianza de 2 meses"
    assert item.summary == ["80 m²", "2 hab.", "3ª planta exterior con ascensor"]
    assert (item.size_m2, item.bedrooms, item.bathrooms) == (80.0, 2, 1)
    assert item.floor_number == 3 and item.exterior is True and item.lift is True
    assert item.tags == ["Alquiler de temporada"]
    assert item.features["Edificio"] == ["3ª planta exterior", "Con ascensor"]
    assert [(e.label, e.rating, e.value) for e in item.energy_certificate] == [
        ("Consumo", "E", "234 kWh/m² año"),
        ("Emisiones", "D", "42 kg CO2/m² año"),
    ]
    assert item.description == "Piso luminoso en el centro.\n\nDisponible en noviembre."
    assert item.location == ["Calle Mayor", "Barrio Sol", "Madrid"]
    assert item.reference == "REF-77"
    assert item.advertiser_name == "Inmobiliaria Ejemplo"
    assert item.advertiser_type == "Profesional"
    assert item.advertiser_url == "https://www.idealista.com/pro/ejemplo/"
    assert item.last_updated == "Anuncio actualizado el 9 de octubre"
    assert [(p.url, p.tag, p.floor_plan) for p in item.photos] == [
        ("https://img.example.com/a.jpg", "Salón", False),
        ("https://img.example.com/plan.jpg", "Plano", True),
    ]


def test_private_listing_has_no_agency_link():
    item = parse_listing_page(
        listing_html(5, private=True), "https://www.idealista.com/inmueble/5/"
    )
    assert item.advertiser_type == "Particular"
    assert item.advertiser_name == "Ana"
    assert item.advertiser_url is None


def test_listing_without_content_is_a_parse_error():
    with pytest.raises(IdealistaParseError):
        parse_listing_page("<html></html>", "https://www.idealista.com/inmueble/5/")
