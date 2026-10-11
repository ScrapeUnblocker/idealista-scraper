"""Write records as JSON, JSON Lines or CSV."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

LIST_SEPARATOR = " | "


def to_dict(record: Any) -> dict[str, Any]:
    """A record (dataclass with ``to_dict`` or a dict) as a plain dict."""
    if hasattr(record, "to_dict"):
        return record.to_dict()
    if isinstance(record, dict):
        return dict(record)
    raise TypeError(f"cannot export {type(record).__name__}")


def to_json(records: Iterable[Any], *, pretty: bool = False) -> str:
    """Serialize records as a JSON array."""
    data = [to_dict(r) for r in records]
    return json.dumps(data, ensure_ascii=False, indent=2 if pretty else None)


def to_jsonl(records: Iterable[Any]) -> str:
    """Serialize records as JSON Lines (one object per line)."""
    return "".join(json.dumps(to_dict(r), ensure_ascii=False) + "\n" for r in records)


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        if all(not isinstance(item, (dict, list)) for item in value):
            return LIST_SEPARATOR.join("" if item is None else str(item) for item in value)
        if all(isinstance(item, dict) and "url" in item for item in value):
            return LIST_SEPARATOR.join(str(item["url"]) for item in value)
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        if all(isinstance(item, list) for item in value.values()):
            return LIST_SEPARATOR.join(f"{k}: {', '.join(map(str, v))}" for k, v in value.items())
        return json.dumps(value, ensure_ascii=False)
    return value


def flatten(record: Any) -> dict[str, Any]:
    """A record as one flat CSV row: lists of values are joined with ``" | "``,
    feature groups become ``group: a, b | group: c``, photos become their URLs
    and other nested values become JSON."""
    row: dict[str, Any] = {}
    for key, value in to_dict(record).items():
        if key == "energy_certificate" and isinstance(value, list):
            row[key] = LIST_SEPARATOR.join(
                " ".join(
                    str(part) for part in (e.get("label"), e.get("rating"), e.get("value")) if part
                )
                for e in value
            )
        else:
            row[key] = _cell(value)
    return row


def csv_string(records: Iterable[Any], columns: Sequence[str] | None = None) -> str:
    """Records as CSV text (header + one row per record)."""
    rows = [flatten(record) for record in records]
    header: list[str] = list(columns) if columns else []
    if not header:
        for row in rows:
            for key in row:
                if key not in header:
                    header.append(key)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in header})
    return buffer.getvalue()


def write_csv(
    records: Iterable[Any], path: str | Path, columns: Sequence[str] | None = None
) -> int:
    """Write records to a UTF-8 CSV file (with a BOM, so Excel reads it). Returns the row count."""
    records = list(records)
    text = csv_string(records, columns)
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        handle.write(text)
    return len(records)


def write_json(records: Iterable[Any], path: str | Path, *, pretty: bool = True) -> int:
    """Write records to a UTF-8 JSON file. Returns the record count."""
    records = list(records)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(to_json(records, pretty=pretty) + "\n")
    return len(records)


__all__ = ["csv_string", "flatten", "to_dict", "to_json", "to_jsonl", "write_csv", "write_json"]
