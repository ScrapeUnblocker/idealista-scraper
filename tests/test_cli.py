from __future__ import annotations

import csv
import io
import json

import pytest
from conftest import TargetNotFoundError, card, listing_html, search_html

from idealista_scraper import Listing
from idealista_scraper.cli import build_parser, main, order_listings

BASE = "https://www.idealista.com/venta-viviendas/madrid-madrid/"
LISTING = "https://www.idealista.com/inmueble/111/"


def test_parser_defaults_and_options():
    args = build_parser().parse_args(["search", "madrid-madrid"])
    assert args.locations == ["madrid-madrid"]
    assert (args.site, args.operation, args.property_type) == ("es", "sale", "homes")
    assert args.pages == 1 and args.format == "json" and args.country is None

    args = build_parser().parse_args(
        [
            "search",
            "lisboa",
            "porto",
            "--site",
            "pt",
            "--rent",
            "--type",
            "offices",
            "--sort",
            "price-drop",
            "--min-price",
            "500",
            "--max-size",
            "90",
            "--filter",
            "t2",
            "--filter",
            "elevador,garagem",
            "--private-only",
            "--order",
            "price-m2",
            "-p",
            "3",
            "-n",
            "50",
            "--details",
            "-f",
            "csv",
        ]
    )
    assert args.locations == ["lisboa", "porto"]
    assert (args.site, args.operation, args.property_type) == ("pt", "rent", "offices")
    assert args.sort == "price-drop" and args.min_price == 500 and args.max_size == 90
    assert args.filters == ["t2", "elevador,garagem"]
    assert args.private_only and args.order == "price-m2"
    assert (args.pages, args.limit, args.details, args.format) == (3, 50, True, "csv")


def test_parser_rejects_bad_choices():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["search", "x", "--site", "fr"])
    with pytest.raises(SystemExit):
        build_parser().parse_args(["search", "x", "--professional-only", "--private-only"])


def test_dry_run_prints_urls_without_calls(capsys):
    code = main(
        [
            "search",
            "madrid-madrid",
            "getafe-madrid",
            "--max-price",
            "300000",
            "--sort",
            "newest",
            "--dry-run",
        ]
    )
    assert code == 0
    assert capsys.readouterr().out.splitlines() == [
        BASE + "con-precio-hasta_300000/?ordenado-por=fecha-publicacion-desc",
        "https://www.idealista.com/venta-viviendas/getafe-madrid/"
        "con-precio-hasta_300000/?ordenado-por=fecha-publicacion-desc",
    ]


def test_search_json_output(make_scraper, capsys):
    scraper, _ = make_scraper({BASE: search_html([card(1), card(2)], has_next=False)})
    assert main(["search", "madrid-madrid", "-q"], scraper=scraper) == 0
    data = json.loads(capsys.readouterr().out)
    assert [row["listing_id"] for row in data] == [1, 2]
    assert data[0]["bedrooms"] == 3


def test_search_csv_to_file(make_scraper, tmp_path):
    scraper, _ = make_scraper(
        {BASE: search_html([card(1, tags=("Lujo", "Ático"))], has_next=False)}
    )
    out = tmp_path / "homes.csv"
    assert (
        main(["search", "madrid-madrid", "-q", "-f", "csv", "-o", str(out)], scraper=scraper) == 0
    )
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM for Excel
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    assert rows[0]["listing_id"] == "1"
    assert rows[0]["price"] == "350000"
    assert rows[0]["tags"] == "Lujo | Ático"
    assert rows[0]["exterior"] == "true"


def test_search_details_reads_listing_pages(make_scraper, capsys):
    html = search_html([card(111)], has_next=False)
    scraper, client = make_scraper({BASE: html, LISTING: listing_html(111)})
    assert main(["search", "madrid-madrid", "-q", "--details"], scraper=scraper) == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["bathrooms"] == 1 and data[0]["photos"][0]["tag"] == "Salón"
    assert client.urls == [BASE, LISTING]


def test_unknown_location_fails_cleanly(make_scraper, capsys):
    scraper, _ = make_scraper({BASE: TargetNotFoundError("404")})
    assert main(["search", "madrid-madrid"], scraper=scraper) == 1
    assert "IdealistaNotFoundError" in capsys.readouterr().err


def test_listing_command(make_scraper, capsys):
    scraper, _ = make_scraper({LISTING: listing_html(111)})
    assert main(["listing", "111", "-q", "--pretty"], scraper=scraper) == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["reference"] == "REF-77"


def test_listing_command_reports_missing_listings(make_scraper, capsys):
    scraper, _ = make_scraper({LISTING: TargetNotFoundError("404")})
    assert main(["listing", LISTING], scraper=scraper) == 1
    assert "IdealistaNotFoundError" in capsys.readouterr().err


def test_filters_command(make_scraper, capsys):
    scraper, _ = make_scraper({BASE: search_html([card(1)])})
    assert main(["filters", "madrid-madrid"], scraper=scraper) == 0
    out = capsys.readouterr().out
    assert "de-dos-dormitorios" in out and "Habitaciones" in out
    scraper, _ = make_scraper({BASE: search_html([card(1)])})
    assert main(["filters", "madrid-madrid", "--json"], scraper=scraper) == 0
    groups = json.loads(capsys.readouterr().out)
    assert groups[0]["options"][1]["slug"] == "de-dos-dormitorios"


def test_bad_input_is_an_error_not_a_traceback(capsys):
    assert main(["search", "Madrid Centro", "--dry-run"]) == 2
    assert "location slug" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["search"])


def test_order_listings_puts_unknown_values_last():
    def make(listing_id, price):
        return Listing(listing_id=listing_id, url="u", title="t", site="es", price=price)

    items = [make(1, 300.0), make(2, None), make(3, 100.0)]
    assert [i.listing_id for i in order_listings(items, "price")] == [3, 1, 2]
    assert [i.listing_id for i in order_listings(items, "price-desc")] == [1, 3, 2]
    assert order_listings(items, None) == items
