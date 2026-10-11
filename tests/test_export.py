from __future__ import annotations

import json

from conftest import listing_html

from idealista_scraper import (
    Listing,
    csv_string,
    flatten,
    parse_listing_page,
    to_json,
    to_jsonl,
    write_csv,
    write_json,
)


def make(listing_id: int = 1) -> Listing:
    return Listing(
        listing_id=listing_id,
        url=f"https://www.idealista.com/inmueble/{listing_id}/",
        title="Ático en Calle Mayor, Madrid",
        site="es",
        price=450000.0,
        size_m2=82.5,
        lift=True,
        tags=["Lujo", "Ático"],
    )


def test_json_and_jsonl_keep_unicode():
    assert json.loads(to_json([make()]))[0]["title"] == "Ático en Calle Mayor, Madrid"
    assert "Ático" in to_json([make()])
    lines = to_jsonl([make(1), make(2)]).splitlines()
    assert [json.loads(line)["listing_id"] for line in lines] == [1, 2]


def test_flatten_cells():
    row = flatten(make())
    assert row["price"] == 450000 and row["size_m2"] == 82.5
    assert row["lift"] == "true" and row["exterior"] == ""
    assert row["tags"] == "Lujo | Ático"


def test_details_flatten_features_energy_and_photos():
    details = parse_listing_page(listing_html(111), "https://www.idealista.com/inmueble/111/")
    row = flatten(details)
    assert row["features"].startswith("Características básicas: 80 m² construidos, 2 habitaciones")
    assert row["energy_certificate"] == "Consumo E 234 kWh/m² año | Emisiones D 42 kg CO2/m² año"
    assert row["photos"] == "https://img.example.com/a.jpg | https://img.example.com/plan.jpg"


def test_csv_header_and_files(tmp_path):
    text = csv_string([make(1), make(2)])
    assert text.splitlines()[0].startswith("listing_id,url,title,site,")
    path = tmp_path / "out.csv"
    assert write_csv([make()], path) == 1
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    path = tmp_path / "out.json"
    assert write_json([make()], path) == 1
    assert json.loads(path.read_text(encoding="utf-8"))[0]["listing_id"] == 1
