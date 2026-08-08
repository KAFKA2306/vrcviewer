from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from . import __version__

REQUIRED_COLUMNS = ("ID", "Name", "Author ID", "Author Name", "Thumbnail")
UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
ID_PATTERNS = {
    "avatar": re.compile(rf"^avtr_{UUID}$"),
    "world": re.compile(rf"^wrld_{UUID}$"),
}
AUTHOR_ID_PATTERN = re.compile(rf"^usr_{UUID}$")


class BuildError(ValueError):
    pass


@dataclass(frozen=True)
class Record:
    resource_id: str
    name: str
    author_id: str
    author_name: str
    thumbnail: str
    category: str
    source_file: str
    row_number: int


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalize_category(path: Path) -> str:
    raw = path.stem.removeprefix("worlds_")
    value = unicodedata.normalize("NFKC", raw).strip().casefold()
    value = re.sub(r"\s+", "-", value)
    if not value:
        raise BuildError(f"{path}: category name is empty")
    return value


def validate_https_url(value: str, source: Path, row_number: int, field: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise BuildError(
            f"{source}:{row_number}: {field} must be an absolute https URL, got {value!r}"
        )


def read_csv(path: Path, kind: str, category: str) -> list[Record]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise BuildError(f"{path}: input must be UTF-8") from exc

    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise BuildError(f"{path}: missing CSV header")
    if tuple(reader.fieldnames) != REQUIRED_COLUMNS:
        raise BuildError(
            f"{path}: expected columns {list(REQUIRED_COLUMNS)!r}, got {reader.fieldnames!r}"
        )

    records: list[Record] = []
    seen_rows: set[tuple[str, ...]] = set()
    seen_ids: dict[str, int] = {}
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise BuildError(f"{path}:{row_number}: malformed CSV row")
        values = tuple((row[column] or "").strip() for column in REQUIRED_COLUMNS)
        if not any(values):
            continue
        if values in seen_rows:
            raise BuildError(f"{path}:{row_number}: exact duplicate row")
        seen_rows.add(values)

        resource_id, name, author_id, author_name, thumbnail = values
        for field, value in (("ID", resource_id), ("Name", name), ("Author ID", author_id), ("Author Name", author_name), ("Thumbnail", thumbnail)):
            if not value:
                raise BuildError(f"{path}:{row_number}: {field} must not be empty")

        if not ID_PATTERNS[kind].fullmatch(resource_id):
            raise BuildError(f"{path}:{row_number}: invalid {kind} ID {resource_id!r}")
        if not AUTHOR_ID_PATTERN.fullmatch(author_id):
            raise BuildError(f"{path}:{row_number}: invalid author ID {author_id!r}")
        validate_https_url(thumbnail, path, row_number, "Thumbnail")

        if resource_id in seen_ids:
            first = seen_ids[resource_id]
            raise BuildError(
                f"{path}:{row_number}: duplicate ID {resource_id!r}; first seen on row {first}"
            )
        seen_ids[resource_id] = row_number
        records.append(
            Record(resource_id, name, author_id, author_name, thumbnail, category, path.name, row_number)
        )
    return records


def load_catalog(root: Path) -> tuple[list[Record], list[Record], list[Path]]:
    avatar_path = root / "sample_avatars.csv"
    if not avatar_path.is_file():
        raise BuildError("sample_avatars.csv is required")

    avatars = read_csv(avatar_path, "avatar", "avatar")
    world_paths = sorted(root.glob("worlds_*.csv"), key=lambda p: p.name.casefold())
    if not world_paths:
        raise BuildError("at least one worlds_*.csv file is required")

    worlds: list[Record] = []
    seen_world_ids: dict[str, tuple[str, int]] = {}
    categories: set[str] = set()
    for path in world_paths:
        category = normalize_category(path)
        if category in categories:
            raise BuildError(f"{path}: normalized category {category!r} is duplicated")
        categories.add(category)
        for record in read_csv(path, "world", category):
            if record.resource_id in seen_world_ids:
                first_file, first_row = seen_world_ids[record.resource_id]
                raise BuildError(
                    f"{path}:{record.row_number}: world ID {record.resource_id!r} already exists in "
                    f"{first_file}:{first_row}"
                )
            seen_world_ids[record.resource_id] = (record.source_file, record.row_number)
            worlds.append(record)
    return avatars, worlds, [avatar_path, *world_paths]


def e(value: str) -> str:
    return html.escape(value, quote=True)


def card(record: Record, kind: str) -> str:
    detail_url = f"https://vrchat.com/home/{kind}/{record.resource_id}"
    classes = f"card {kind}-card"
    category = f' data-category="{e(record.category)}"' if kind == "world" else ""
    return (
        f'<article class="{classes}" data-name="{e(record.name.casefold())}" '
        f'data-author="{e(record.author_name.casefold())}"{category}>'
        f'<a class="image-container" href="{e(detail_url)}" target="_blank" rel="noopener noreferrer">'
        f'<img class="image" src="{e(record.thumbnail)}" alt="{e(record.name)}" loading="lazy">'
        '<span class="image-overlay">VRChatで見る</span></a>'
        '<div class="info">'
        f'<div class="name">{e(record.name)}</div>'
        f'<div class="author">作者: {e(record.author_name)}</div>'
        f'<div class="id">ID: {e(record.resource_id)}</div>'
        '</div></article>'
    )


def render_page(root: Path) -> tuple[str, dict[str, int], list[Path]]:
    avatars, worlds, input_paths = load_catalog(root)
    template_path = root / "templates" / "index.html"
    if not template_path.is_file():
        raise BuildError("templates/index.html is required")
    template = template_path.read_text(encoding="utf-8")

    categories = sorted({record.category for record in worlds})
    category_buttons = "\n".join(
        f'<button class="filter-btn" type="button" data-filter="{e(category)}">{e(category)}</button>'
        for category in categories
    )
    avatar_cards = "\n".join(card(record, "avatar") for record in avatars)
    world_cards = "\n".join(card(record, "world") for record in worlds)

    replacements = {
        "{{AVATAR_CARDS}}": avatar_cards,
        "{{WORLD_CARDS}}": world_cards,
        "{{WORLD_FILTERS}}": category_buttons,
    }
    for marker, value in replacements.items():
        if template.count(marker) != 1:
            raise BuildError(f"template marker {marker} must appear exactly once")
        template = template.replace(marker, value)

    counts = {"avatars": len(avatars), "worlds": len(worlds)}
    for category in categories:
        counts[f"worlds:{category}"] = sum(1 for record in worlds if record.category == category)
    return template.rstrip() + "\n", counts, input_paths


def git_value(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def build_manifest(root: Path, output: bytes, counts: dict[str, int], input_paths: list[Path]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "generator_version": __version__,
        "commit_sha": os.environ.get("GITHUB_SHA") or git_value(root, "rev-parse", "HEAD") or "unknown",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "inputs": [
            {"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)}
            for path in input_paths
        ],
        "counts": counts,
        "total_unique_records": counts["avatars"] + counts["worlds"],
        "output": {"path": "index.html", "sha256": sha256_bytes(output)},
    }


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(dir=path.parent, delete=False)
    tmp = Path(handle.name)
    try:
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def run(root: Path, check: bool) -> int:
    html_text, counts, input_paths = render_page(root)
    output = html_text.encode("utf-8")
    manifest = build_manifest(root, output, counts, input_paths)
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

    output_path = root / "index.html"
    manifest_path = root / "build-manifest.json"
    if check:
        if not output_path.is_file() or output_path.read_bytes() != output:
            raise BuildError("index.html is stale; run `python -m vrcviewer.build` and commit the result")
        atomic_write(manifest_path, manifest_bytes)
        return 0

    atomic_write(output_path, output)
    atomic_write(manifest_path, manifest_bytes)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate CSV inputs and deterministically build index.html")
    parser.add_argument("--check", action="store_true", help="fail if tracked index.html differs from generated output")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    args = parser.parse_args(argv)
    try:
        return run(args.root.resolve(), args.check)
    except BuildError as exc:
        parser.exit(1, f"build error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
