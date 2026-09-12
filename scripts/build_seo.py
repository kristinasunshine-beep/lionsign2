#!/usr/bin/env python3
"""Generate canonical record pages, SEO manifest and sitemap for GitHub Pages."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import struct
from pathlib import Path
from typing import Any
from urllib.parse import quote
from xml.etree import ElementTree as ET


ID_RE = re.compile(r"^DI-(M|F|K|L)-\d{6}$")
SITE_NAME = "Doberman Index"
SITE_DESCRIPTION = "A structured, searchable registry connecting Dobermans, pedigrees, kennels, litters and bloodlines."


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def origin_for(root: Path) -> str:
    host = (root / "CNAME").read_text(encoding="utf-8").strip().strip("/")
    if not host or any(char.isspace() for char in host):
        raise ValueError("CNAME must contain one public hostname")
    return f"https://{host}"


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def limit_words(value: str, maximum: int) -> str:
    value = clean_text(value)
    if len(value) <= maximum:
        return value
    shortened = value[: maximum + 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return shortened + "."


def absolute(origin: str, path: str) -> str:
    return f"{origin}/{quote(path.lstrip('/'), safe='/') }"


def record_url(origin: str, record_id: str) -> str:
    return f"{origin}/records/{record_id}/"


# QR Version 5-L is deliberately fixed here. Doberman Index canonical record URLs
# are comfortably below its byte-mode capacity, which lets us generate a valid,
# dependency-free QR SVG during the normal registry build.
QR_VERSION = 5
QR_SIZE = 17 + 4 * QR_VERSION
QR_DATA_CODEWORDS = 108
QR_ECC_CODEWORDS = 26


def _gf_tables() -> tuple[list[int], list[int]]:
    exp = [0] * 512
    log = [0] * 256
    value = 1
    for index in range(255):
        exp[index] = value
        log[value] = index
        value <<= 1
        if value & 0x100:
            value ^= 0x11D
    for index in range(255, 512):
        exp[index] = exp[index - 255]
    return exp, log


_QR_EXP, _QR_LOG = _gf_tables()


def _gf_mul(left: int, right: int) -> int:
    if not left or not right:
        return 0
    return _QR_EXP[_QR_LOG[left] + _QR_LOG[right]]


def _rs_generator(degree: int) -> list[int]:
    polynomial = [1]
    for index in range(degree):
        root = _QR_EXP[index]
        updated = [0] * (len(polynomial) + 1)
        for offset, coefficient in enumerate(polynomial):
            updated[offset] ^= coefficient
            updated[offset + 1] ^= _gf_mul(coefficient, root)
        polynomial = updated
    return polynomial


def _rs_remainder(data: list[int], degree: int) -> list[int]:
    generator = _rs_generator(degree)
    remainder = [0] * degree
    for byte in data:
        factor = byte ^ remainder[0]
        remainder = remainder[1:] + [0]
        if factor:
            for index in range(degree):
                remainder[index] ^= _gf_mul(generator[index + 1], factor)
    return remainder


def _format_bits(mask: int = 0) -> int:
    # Error correction level L = binary 01.
    value = (0b01 << 3) | mask
    remainder = value << 10
    generator = 0x537
    for bit in range(14, 9, -1):
        if (remainder >> bit) & 1:
            remainder ^= generator << (bit - 10)
    return ((value << 10) | (remainder & 0x3FF)) ^ 0x5412


def qr_matrix(value: str) -> list[list[bool]]:
    raw = value.encode("utf-8")
    if len(raw) > 106:
        raise ValueError("Owner Link Kit QR target exceeds Version 5-L byte capacity")

    bits: list[int] = []

    def append_bits(number: int, length: int) -> None:
        bits.extend((number >> bit) & 1 for bit in range(length - 1, -1, -1))

    append_bits(0b0100, 4)
    append_bits(len(raw), 8)
    for byte in raw:
        append_bits(byte, 8)

    target_bits = QR_DATA_CODEWORDS * 8
    bits.extend([0] * min(4, target_bits - len(bits)))
    while len(bits) % 8:
        bits.append(0)

    data: list[int] = []
    for index in range(0, len(bits), 8):
        byte = 0
        for bit in bits[index:index + 8]:
            byte = (byte << 1) | bit
        data.append(byte)

    pads = (0xEC, 0x11)
    pad_index = 0
    while len(data) < QR_DATA_CODEWORDS:
        data.append(pads[pad_index % 2])
        pad_index += 1

    codewords = data + _rs_remainder(data, QR_ECC_CODEWORDS)
    data_bits: list[int] = []
    for byte in codewords:
        data_bits.extend((byte >> bit) & 1 for bit in range(7, -1, -1))

    size = QR_SIZE
    matrix = [[False] * size for _ in range(size)]
    reserved = [[False] * size for _ in range(size)]

    def set_module(x: int, y: int, dark: bool, lock: bool = True) -> None:
        if 0 <= x < size and 0 <= y < size:
            matrix[y][x] = bool(dark)
            if lock:
                reserved[y][x] = True

    def finder(center_x: int, center_y: int) -> None:
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = center_x + dx, center_y + dy
                if not (0 <= x < size and 0 <= y < size):
                    continue
                dark = False
                if abs(dx) <= 3 and abs(dy) <= 3:
                    edge = max(abs(dx), abs(dy))
                    dark = edge == 3 or edge <= 1
                set_module(x, y, dark)

    finder(3, 3)
    finder(size - 4, 3)
    finder(3, size - 4)

    for index in range(8, size - 8):
        if not reserved[6][index]:
            set_module(index, 6, index % 2 == 0)
        if not reserved[index][6]:
            set_module(6, index, index % 2 == 0)

    for dy in range(-2, 3):
        for dx in range(-2, 3):
            set_module(30 + dx, 30 + dy, max(abs(dx), abs(dy)) != 1)

    primary_format: list[tuple[int, int]] = [(8, index) for index in range(6)]
    primary_format += [(8, 7), (8, 8), (7, 8)]
    primary_format += [(14 - index, 8) for index in range(9, 15)]
    secondary_format = [(size - 1 - index, 8) for index in range(8)]
    secondary_format += [(8, size - 15 + index) for index in range(8, 15)]
    for x, y in primary_format + secondary_format:
        set_module(x, y, False)
    set_module(8, size - 8, True)

    bit_index = 0
    upward = True
    x = size - 1
    while x > 0:
        if x == 6:
            x -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for y in rows:
            for column in (x, x - 1):
                if reserved[y][column]:
                    continue
                bit = data_bits[bit_index] if bit_index < len(data_bits) else 0
                bit_index += 1
                if (column + y) % 2 == 0:
                    bit ^= 1
                matrix[y][column] = bool(bit)
        upward = not upward
        x -= 2

    format_value = _format_bits(0)
    for index, (x, y) in enumerate(primary_format):
        matrix[y][x] = bool((format_value >> index) & 1)
    for index, (x, y) in enumerate(secondary_format):
        matrix[y][x] = bool((format_value >> index) & 1)
    matrix[size - 8][8] = True
    return matrix


def qr_svg(value: str, title: str) -> str:
    matrix = qr_matrix(value)
    quiet = 4
    size = len(matrix) + quiet * 2
    path = []
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                path.append(f"M{x + quiet} {y + quiet}h1v1h-1z")
    modules = "".join(path)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        'shape-rendering="crispEdges" role="img">'
        f'<title>{html.escape(title)}</title><metadata>{html.escape(value)}</metadata>'
        '<rect width="100%" height="100%" fill="#fff"/>'
        f'<path d="{modules}" fill="#000"/></svg>\n'
    )


def badge_svg(record_id: str) -> str:
    safe_id = html.escape(record_id)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="286" height="54" viewBox="0 0 286 54" role="img" aria-labelledby="title desc">
<title id="title">Indexed on Doberman Index</title><desc id="desc">Public record {safe_id}</desc>
<rect width="286" height="54" rx="5" fill="#0d0d0d"/><rect x="11" y="11" width="9" height="32" fill="#f3fe19"/>
<text x="31" y="24" fill="#ffffff" font-family="Arial,Helvetica,sans-serif" font-size="12" font-weight="700" letter-spacing=".8">INDEXED ON DOBERMAN INDEX</text>
<text x="31" y="41" fill="#f3fe19" font-family="Arial,Helvetica,sans-serif" font-size="11" font-weight="700">{safe_id}</text>
</svg>
'''


def owner_link_kit(origin: str, summary: dict[str, Any]) -> dict[str, Any]:
    record_id = summary["record_id"]
    name = display_name(summary)
    canonical = record_url(origin, record_id)
    entity_type = summary["entity_type"]
    if entity_type == "doberman":
        anchors = [
            f"{name} — Doberman Index record",
            f"{record_id} · Public record on Doberman Index",
            f"View {name}'s structured Doberman Index record",
        ]
    elif entity_type == "kennel":
        anchors = [
            f"{name} — Doberman Index kennel record",
            f"{record_id} · Public kennel record on Doberman Index",
            f"View {name}'s breeding-program record on Doberman Index",
        ]
    else:
        anchors = [
            f"{name} — Doberman Index litter record",
            f"{record_id} · Public litter record on Doberman Index",
            f"View {name}'s litter record on Doberman Index",
        ]
    badge_url = f"{canonical}indexed-badge.svg"
    return {
        "schema_version": "1.0.0",
        "record_id": record_id,
        "display_name": name,
        "canonical_url": canonical,
        "anchors": [
            {"text": anchor, "html": f'<a href="{canonical}">{html.escape(anchor)}</a>'}
            for anchor in anchors
        ],
        "qr": {"target_url": canonical, "asset_url": f"{canonical}owner-link-qr.svg"},
        "badge": {
            "label": "Indexed on Doberman Index",
            "asset_url": badge_url,
            "html": f'<a href="{canonical}"><img src="{badge_url}" alt="Indexed on Doberman Index · {record_id}"></a>',
        },
        "generated_from_record_updated_at": clean_text(summary.get("updated_at")),
    }


def write_owner_link_assets(destination_dir: Path, kit: dict[str, Any]) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    canonical = kit["canonical_url"]
    record_id = kit["record_id"]
    (destination_dir / "owner-link-kit.json").write_text(
        json.dumps(kit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (destination_dir / "owner-link-qr.svg").write_text(
        qr_svg(canonical, f"QR code for Doberman Index record {record_id}"), encoding="utf-8"
    )
    (destination_dir / "indexed-badge.svg").write_text(badge_svg(record_id), encoding="utf-8")


def render_owner_link_kit(kit: dict[str, Any]) -> str:
    canonical = kit["canonical_url"]
    anchors_html = "".join(
        f'<div class="owner-anchor"><code>{html.escape(item["text"])}</code><button class="copy-control" type="button" data-copy-html="{html.escape(item["html"], quote=True)}">Copy HTML</button></div>'
        for item in kit["anchors"]
    )
    badge_copy = html.escape(kit["badge"]["html"], quote=True)
    record_id = html.escape(kit["record_id"], quote=True)
    return f'''<section class="section owner-link-section" aria-labelledby="owner-link-kit-title">
      <details class="owner-link-kit" id="owner-link-kit">
        <summary><span>Owner Link Kit</span><small>Canonical sharing tools for this public record</small></summary>
        <div class="owner-link-kit__body">
          <div class="owner-link-kit__intro"><p class="section-label">Owner publishing tools</p><h2 id="owner-link-kit-title">Link this record.</h2><p>Use the permanent Doberman Index URL when referencing this record from a kennel site, Doberman profile, litter page or social profile.</p></div>
          <div class="owner-link-kit__grid">
            <div class="owner-link-card owner-link-card--wide"><h3>Canonical URL</h3><code class="owner-canonical">{html.escape(canonical)}</code><button class="copy-control" type="button" data-copy-text="{html.escape(canonical, quote=True)}">Copy URL</button><a class="micro-link" href="owner-link-kit.json" download>Download kit JSON</a></div>
            <div class="owner-link-card"><h3>QR code</h3><img class="owner-qr" src="owner-link-qr.svg" alt="QR code linking to {record_id} canonical record" width="180" height="180"><a class="micro-link" href="owner-link-qr.svg" download>Download QR SVG</a></div>
            <div class="owner-link-card"><h3>Indexed badge</h3><a href="{html.escape(canonical, quote=True)}"><img class="owner-badge" src="indexed-badge.svg" alt="Indexed on Doberman Index · {record_id}" width="286" height="54"></a><button class="copy-control" type="button" data-copy-html="{badge_copy}">Copy badge HTML</button><a class="micro-link" href="indexed-badge.svg" download>Download badge SVG</a></div>
            <div class="owner-link-card owner-link-card--anchors"><h3>Three natural anchor options</h3>{anchors_html}</div>
          </div>
          <p class="owner-link-note">Use the link because it helps visitors reach the structured public record. Publication, pricing or promotion is never conditional on linking back.</p>
        </div>
      </details>
    </section>'''




def image_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height, width = struct.unpack(">HH", data[index + 5 : index + 9])
                return width, height
            if index + 4 > len(data):
                break
            index += 2 + int.from_bytes(data[index + 2 : index + 4], "big")
    return None


def safe_image(root: Path, origin: str, value: Any) -> tuple[str, tuple[int, int] | None]:
    path = clean_text(value)
    if not re.fullmatch(r"media/(?:dobermans|kennels|litters)/[^\s]+\.(?:jpe?g|png|webp|avif)", path, re.I):
        return "", None
    local = root / Path(path)
    if not local.is_file():
        return "", None
    return absolute(origin, path), image_dimensions(local)


def display_name(summary: dict[str, Any]) -> str:
    return clean_text(summary.get("registered_name") if summary.get("entity_type") == "doberman" else summary.get("name")) or summary["record_id"]


def record_description(summary: dict[str, Any], name: str) -> str:
    record_id = summary["record_id"]
    entity = summary.get("entity_type")
    if entity == "doberman":
        sex = clean_text(summary.get("sex")).lower()
        place = clean_text(summary.get("location") or summary.get("country"))
        subject = f"published {sex + ' ' if sex else ''}Doberman record"
        location = f" from {place}" if place else ""
        return limit_words(f"{name} ({record_id}) is a {subject}{location}. Explore its pedigree, health, performance and connected records.", 158)
    if entity == "kennel":
        place = clean_text(summary.get("country"))
        location = f" from {place}" if place else ""
        return limit_words(f"{name} ({record_id}) is a published Doberman kennel record{location}. Explore its indexed dogs, litter connections and public program details.", 158)
    count = len(summary.get("puppy_ids") or [])
    return limit_words(f"{name} ({record_id}) is a published Doberman litter record. Explore its kennel, sire, dam, {count} indexed offspring and current puppy availability.", 158)


def metadata_for(root: Path, origin: str, summary: dict[str, Any]) -> dict[str, Any]:
    name = display_name(summary)
    canonical = record_url(origin, summary["record_id"])
    available = max(16, 64 - len(summary["record_id"]) - len(" ·  · Doberman Index"))
    title = f"{limit_words(name, available)} · {summary['record_id']} · Doberman Index"
    description = record_description(summary, name)
    image, dimensions = safe_image(root, origin, summary.get("hero"))
    return {"title": title, "description": description, "canonical": canonical, "image": image, "image_dimensions": dimensions}


def relation_ids(summary: dict[str, Any], records: list[dict[str, Any]]) -> list[tuple[str, str]]:
    record_id = summary["record_id"]
    entity = summary.get("entity_type")
    relations: list[tuple[str, str]] = []
    def add(label: str, value: Any) -> None:
        candidate = clean_text(value).upper()
        if candidate and ID_RE.fullmatch(candidate) and candidate != record_id and candidate not in {item[1] for item in relations}:
            relations.append((label, candidate))
    if entity == "doberman":
        add("Kennel", summary.get("kennel_id")); add("Sire", summary.get("sire_id")); add("Dam", summary.get("dam_id")); add("Birth litter", summary.get("litter_id"))
        for item in records:
            if item.get("entity_type") == "litter" and record_id in {item.get("sire_id"), item.get("dam_id")}:
                add("Litter", item.get("record_id"))
            if item.get("entity_type") == "doberman" and record_id in {item.get("sire_id"), item.get("dam_id")}:
                add("Offspring", item.get("record_id"))
            if summary.get("litter_id") and item.get("entity_type") == "doberman" and item.get("litter_id") == summary.get("litter_id"):
                add("Littermate", item.get("record_id"))
    elif entity == "kennel":
        for item in records:
            if item.get("kennel_id") == record_id:
                add("Doberman" if item.get("entity_type") == "doberman" else "Litter", item.get("record_id"))
    else:
        add("Kennel", summary.get("kennel_id")); add("Sire", summary.get("sire_id")); add("Dam", summary.get("dam_id"))
        for puppy_id in summary.get("puppy_ids") or []:
            add("Offspring", puppy_id)
    published_ids = {item["record_id"] for item in records}
    return [(label, related_id) for label, related_id in relations if related_id in published_ids]


def json_ld(origin: str, summary: dict[str, Any], metadata: dict[str, Any], related: list[tuple[str, str]]) -> dict[str, Any]:
    record_id = summary["record_id"]
    name = display_name(summary)
    canonical = metadata["canonical"]
    entity_type = "Organization" if summary.get("entity_type") == "kennel" else "Thing"
    page_type = "CollectionPage" if summary.get("entity_type") == "litter" else "WebPage"
    organization_id = f"{origin}/#organization"
    website_id = f"{origin}/#website"
    catalog_id = f"{origin}/records/#catalog"
    dataset_id = f"{canonical}#dataset"
    entity_id = f"{canonical}#record"

    variables = {
        "doberman": ["Identity", "Pedigree", "Health", "Temperament", "Performance", "Reproduction", "Media"],
        "kennel": ["Kennel identity", "Breeding program", "Indexed Dobermans", "Litters", "Media"],
        "litter": ["Litter identity", "Kennel", "Sire", "Dam", "Indexed offspring", "Availability", "Media"],
    }[summary["entity_type"]]

    entity: dict[str, Any] = {
        "@type": entity_type,
        "@id": entity_id,
        "name": name,
        "identifier": {"@type": "PropertyValue", "propertyID": "Doberman Index ID", "value": record_id},
        "description": metadata["description"],
        "mainEntityOfPage": {"@id": f"{canonical}#webpage"},
    }
    if metadata["image"]:
        entity["image"] = metadata["image"]
    if summary.get("entity_type") == "doberman":
        props = []
        for label, key in (("Sex", "sex"), ("Life stage", "life_stage"), ("Date of birth", "date_of_birth"), ("Registration authority", "registration_authority"), ("Registration number", "registration_number")):
            value = clean_text(summary.get(key))
            if value:
                props.append({"@type": "PropertyValue", "name": label, "value": value})
        if props:
            entity["additionalProperty"] = props

    dataset: dict[str, Any] = {
        "@type": "Dataset",
        "@id": dataset_id,
        "name": f"{name} · {record_id} structured record",
        "description": metadata["description"],
        "url": canonical,
        "identifier": {"@type": "PropertyValue", "propertyID": "Doberman Index ID", "value": record_id},
        "creator": {"@id": organization_id},
        "publisher": {"@id": organization_id},
        "includedInDataCatalog": {"@id": catalog_id},
        "about": {"@id": entity_id},
        "measurementTechnique": "Structured record compiled from submitted materials and supporting evidence under the Doberman Index data model; unavailable fields remain explicit.",
        "variableMeasured": [{"@type": "PropertyValue", "name": value} for value in variables],
        "keywords": ["Doberman Index", summary["entity_type"], record_id, name],
    }
    created = clean_text(summary.get("created_at"))
    modified = clean_text(summary.get("updated_at"))
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T[^\s]+", created):
        dataset["dateCreated"] = created
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T[^\s]+", modified):
        dataset["dateModified"] = modified
    place = clean_text(summary.get("location") or summary.get("country"))
    if place:
        dataset["spatialCoverage"] = {"@type": "Place", "name": place}
    if metadata["image"]:
        dataset["image"] = metadata["image"]

    page: dict[str, Any] = {
        "@type": page_type,
        "@id": f"{canonical}#webpage",
        "url": canonical,
        "name": metadata["title"],
        "description": metadata["description"],
        "inLanguage": "en",
        "isPartOf": {"@id": website_id},
        "mainEntity": {"@id": dataset_id},
        "about": {"@id": entity_id},
        "breadcrumb": {"@id": f"{canonical}#breadcrumb"},
    }
    if related:
        page["relatedLink"] = [record_url(origin, related_id) for _, related_id in related]
    if metadata["image"]:
        page["primaryImageOfPage"] = {"@type": "ImageObject", "url": metadata["image"]}
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T[^\s]+", modified):
        page["dateModified"] = modified

    organization = {
        "@type": "Organization", "@id": organization_id, "name": SITE_NAME, "url": f"{origin}/",
        "description": SITE_DESCRIPTION,
    }
    website = {
        "@type": "WebSite", "@id": website_id, "url": f"{origin}/", "name": SITE_NAME,
        "description": SITE_DESCRIPTION, "publisher": {"@id": organization_id}, "inLanguage": "en",
    }
    catalog = {
        "@type": "DataCatalog", "@id": catalog_id, "url": f"{origin}/records/", "name": "Doberman Index Public Registry",
        "description": "Canonical public catalog of published Doberman, kennel and litter records.",
        "creator": {"@id": organization_id}, "publisher": {"@id": organization_id},
    }
    return {
        "@context": "https://schema.org",
        "@graph": [
            website,
            organization,
            catalog,
            page,
            dataset,
            entity,
            {"@type": "BreadcrumbList", "@id": f"{canonical}#breadcrumb", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Doberman Index", "item": f"{origin}/"},
                {"@type": "ListItem", "position": 2, "name": "Records", "item": f"{origin}/records/"},
                {"@type": "ListItem", "position": 3, "name": name, "item": canonical},
            ]},
        ],
    }

def render_head(metadata: dict[str, Any], structured: dict[str, Any], asset_prefix: str) -> str:
    image_meta = ""
    preload = ""
    if metadata["image"]:
        image_meta = f'\n  <meta property="og:image" content="{html.escape(metadata["image"], quote=True)}">\n  <meta property="og:image:alt" content="{html.escape(metadata["title"], quote=True)}">\n  <meta name="twitter:image" content="{html.escape(metadata["image"], quote=True)}">\n  <meta name="twitter:image:alt" content="{html.escape(metadata["title"], quote=True)}">'
        preload = f'\n  <link rel="preload" as="image" href="{html.escape(metadata["image"], quote=True)}">'
    return f'''<meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <title>{html.escape(metadata["title"])}</title>
  <meta name="description" content="{html.escape(metadata["description"], quote=True)}">
  <link rel="canonical" href="{html.escape(metadata["canonical"], quote=True)}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Doberman Index">
  <meta property="og:title" content="{html.escape(metadata["title"], quote=True)}">
  <meta property="og:description" content="{html.escape(metadata["description"], quote=True)}">
  <meta property="og:url" content="{html.escape(metadata["canonical"], quote=True)}">{image_meta}
  <meta name="twitter:card" content="{'summary_large_image' if metadata['image'] else 'summary'}">
  <meta name="twitter:title" content="{html.escape(metadata["title"], quote=True)}">
  <meta name="twitter:description" content="{html.escape(metadata["description"], quote=True)}">{preload}
  <link rel="icon" href="{asset_prefix}favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="{asset_prefix}assets/css/seo-record.css">
  <script type="application/ld+json">{json.dumps(structured, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')}</script>'''


def render_record(root: Path, origin: str, summary: dict[str, Any], records: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
    related = relation_ids(summary, records)
    by_id = {item["record_id"]: item for item in records}
    structured = json_ld(origin, summary, metadata, related)
    name = display_name(summary)
    entity_label = {"doberman": "Doberman record", "kennel": "Kennel record", "litter": "Litter record"}[summary["entity_type"]]
    facts: list[tuple[str, Any]] = [("Permanent ID", summary["record_id"]), ("Record type", entity_label)]
    if summary["entity_type"] == "doberman":
        facts.extend([("Sex", summary.get("sex")), ("Life stage", summary.get("life_stage")), ("Date of birth", summary.get("date_of_birth")), ("Country", summary.get("country")), ("Location", summary.get("location"))])
    elif summary["entity_type"] == "kennel":
        facts.append(("Country", summary.get("country")))
    else:
        facts.extend([("Litter status", summary.get("litter_status") or summary.get("status_label")), ("Date of birth", summary.get("date_of_birth")), ("Planned date", summary.get("planned_date")), ("Indexed offspring", len(summary.get("puppy_ids") or [])), ("Available puppies", len(summary.get("available_puppy_ids") or []))])
    facts_html = "".join(f'<div class="fact"><dt>{html.escape(label)}</dt><dd>{html.escape(clean_text(value) or "Not published")}</dd></div>' for label, value in facts)
    relations_html = "".join(f'<a class="connection" href="../{related_id}/"><span>{html.escape(label)}</span><strong>{html.escape(display_name(by_id[related_id]))}</strong><small>{related_id}</small></a>' for label, related_id in related)
    if not relations_html:
        relations_html = '<p class="empty">No connected public records are available yet.</p>'
    if metadata["image"]:
        width, height = metadata["image_dimensions"] or (1200, 900)
        media_html = f'<img src="{html.escape(metadata["image"], quote=True)}" alt="{html.escape(name, quote=True)} — indexed {entity_label.lower()}" width="{width}" height="{height}" fetchpriority="high">'
    else:
        media_html = f'<div class="hero-placeholder" aria-hidden="true">{html.escape(summary["record_id"][:4])}</div>'
    kit = owner_link_kit(origin, summary)
    owner_kit_html = render_owner_link_kit(kit)
    return f'''<!doctype html>
<html lang="en">
<head>
  {render_head(metadata, structured, "../../")}
</head>
<body>
  <a class="skip" href="#main">Skip to record</a>
  <header class="site-header"><a class="brand" href="../../index.html"><span class="mark" aria-hidden="true"></span>DOBERMAN INDEX</a><nav aria-label="Primary navigation"><a href="../">Records</a><a href="../../about.html">About</a><a href="../../submit.html">Submit</a></nav></header>
  <nav class="breadcrumbs" aria-label="Breadcrumb"><ol><li><a href="../../index.html">Home</a></li><li><a href="../">Records</a></li><li aria-current="page">{html.escape(name)}</li></ol></nav>
  <main id="main">
    <section class="record-hero" aria-labelledby="record-title"><div class="record-hero-inner"><div class="record-copy"><p class="eyebrow">{html.escape(entity_label)} · {summary['record_id']}</p><h1 id="record-title">{html.escape(name)}</h1><p class="summary">{html.escape(metadata['description'])}</p></div><div class="hero-media">{media_html}</div></div></section>
    <section class="section" aria-labelledby="facts-title"><p class="section-label">Public registry facts</p><h2 id="facts-title">Record summary.</h2><dl class="facts">{facts_html}</dl></section>
    <section class="section" aria-labelledby="connections-title"><p class="section-label">Internal record network</p><h2 id="connections-title">Connected records.</h2><div class="connections">{relations_html}</div></section>
    <section class="section" aria-label="Record actions"><div class="actions"><a class="button primary" href="../../profile.html?id={summary['record_id']}">Open complete digital card</a><a class="button" href="../">Browse all records</a></div></section>
    {owner_kit_html}
  </main>
  <footer class="site-footer"><div><strong>DOBERMAN INDEX®</strong><br>Structured records. Connected bloodlines.</div><div>Permanent record<br><strong>{summary['record_id']}</strong></div><div>Platform architecture by LIONSIGN<br>2019–2026 · All rights reserved</div></footer>
  <script src="../../assets/js/owner-link-kit.js" defer></script>
</body>
</html>
'''


def directory_metadata(origin: str) -> dict[str, Any]:
    return {"title": "Published Records · Doberman Index", "description": "Browse published Doberman, kennel and litter records in the Doberman Index public registry.", "canonical": f"{origin}/records/", "image": "", "image_dimensions": None}


def render_directory(origin: str, records: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
    canonical = metadata["canonical"]
    organization_id = f"{origin}/#organization"
    website_id = f"{origin}/#website"
    catalog_id = f"{canonical}#catalog"
    dataset_refs = [{"@id": f"{record_url(origin, item['record_id'])}#dataset"} for item in records]
    structured = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "@id": website_id, "url": f"{origin}/", "name": SITE_NAME, "description": SITE_DESCRIPTION, "publisher": {"@id": organization_id}, "inLanguage": "en"},
        {"@type": "Organization", "@id": organization_id, "name": SITE_NAME, "url": f"{origin}/", "description": SITE_DESCRIPTION},
        {"@type": "DataCatalog", "@id": catalog_id, "url": canonical, "name": "Doberman Index Public Registry", "description": metadata["description"], "creator": {"@id": organization_id}, "publisher": {"@id": organization_id}, "dataset": dataset_refs},
        {"@type": "CollectionPage", "@id": f"{canonical}#webpage", "url": canonical, "name": metadata["title"], "description": metadata["description"], "isPartOf": {"@id": website_id}, "mainEntity": {"@id": catalog_id}},
        {"@type": "ItemList", "@id": f"{canonical}#list", "numberOfItems": len(records), "itemListElement": [{"@type": "ListItem", "position": index, "name": display_name(item), "url": record_url(origin, item["record_id"])} for index, item in enumerate(records, 1)]},
    ]}
    cards = "".join(f'<a class="directory-card" href="{item["record_id"]}/"><small>{item["record_id"]} · {html.escape(item["entity_type"])}</small><strong>{html.escape(display_name(item))}</strong><span>Open canonical public record →</span></a>' for item in records)
    if not cards:
        cards = '<p class="empty">No published records are available.</p>'
    return f'''<!doctype html>
<html lang="en">
<head>
  {render_head(metadata, structured, "../")}
</head>
<body>
  <a class="skip" href="#main">Skip to records</a>
  <header class="site-header"><a class="brand" href="../index.html"><span class="mark" aria-hidden="true"></span>DOBERMAN INDEX</a><nav aria-label="Primary navigation"><a href="../about.html">About</a><a href="../submit.html">Submit</a></nav></header>
  <nav class="breadcrumbs" aria-label="Breadcrumb"><ol><li><a href="../index.html">Home</a></li><li aria-current="page">Records</li></ol></nav>
  <main class="section" id="main"><p class="section-label">Public registry directory</p><h1>Published records.</h1><p class="directory-intro">{html.escape(metadata['description'])}</p><div class="directory-grid">{cards}</div></main>
  <footer class="site-footer"><div><strong>DOBERMAN INDEX®</strong><br>Structured records. Connected bloodlines.</div><div>{len(records)} published record{'s' if len(records)!=1 else ''}</div></footer>
</body>
</html>
'''

def build(root: Path) -> tuple[int, int]:
    origin = origin_for(root)
    registry = load_json(root / "data" / "registry.json")
    records = [item for item in registry.get("records", []) if isinstance(item, dict) and item.get("status") == "published" and ID_RE.fullmatch(clean_text(item.get("record_id")))]
    records.sort(key=lambda item: item["record_id"])
    records_root = root / "records"
    records_root.mkdir(exist_ok=True)
    expected = {item["record_id"] for item in records}
    for child in records_root.iterdir():
        if child.is_dir() and ID_RE.fullmatch(child.name) and child.name not in expected:
            shutil.rmtree(child)
    manifest_records: dict[str, Any] = {}
    sitemap_items: list[tuple[str, str | None]] = [(f"{origin}/", None), (f"{origin}/about.html", None), (f"{origin}/records/", None)]
    for summary in records:
        metadata = metadata_for(root, origin, summary)
        related = relation_ids(summary, records)
        metadata["json_ld"] = json_ld(origin, summary, metadata, related)
        manifest_records[summary["record_id"]] = {key: value for key, value in metadata.items() if key != "image_dimensions"}
        destination = records_root / summary["record_id"] / "index.html"
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_owner_link_assets(destination.parent, owner_link_kit(origin, summary))
        destination.write_text(render_record(root, origin, summary, records, metadata), encoding="utf-8")
        modified = clean_text(summary.get("updated_at"))[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", clean_text(summary.get("updated_at"))) else None
        sitemap_items.append((metadata["canonical"], modified))
    directory_meta = directory_metadata(origin)
    (records_root / "index.html").write_text(render_directory(origin, records, directory_meta), encoding="utf-8")
    manifest = {
        "schema_version": "1.0.0",
        "site_origin": origin,
        "generated_from_registry": registry.get("generated_at"),
        "static_pages": {
            "/": {"title": "Doberman Index · Connected Doberman Registry", "description": SITE_DESCRIPTION, "canonical": f"{origin}/"},
            "/about.html": {"title": "About · Doberman Index", "description": "Why Doberman Index exists: a structured, searchable registry for Dobermans, kennels, litters and bloodlines.", "canonical": f"{origin}/about.html"},
            "/records/": {key: value for key, value in directory_meta.items() if key != "image_dimensions"},
        },
        "records": manifest_records,
    }
    seo_data = root / "data" / "seo-manifest.json"
    seo_data.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ET.register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
    urlset = ET.Element("{http://www.sitemaps.org/schemas/sitemap/0.9}urlset")
    for location, modified in sitemap_items:
        node = ET.SubElement(urlset, "{http://www.sitemaps.org/schemas/sitemap/0.9}url")
        ET.SubElement(node, "{http://www.sitemaps.org/schemas/sitemap/0.9}loc").text = location
        if modified:
            ET.SubElement(node, "{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod").text = modified
    ET.ElementTree(urlset).write(root / "sitemap.xml", encoding="utf-8", xml_declaration=True)
    return len(records), len(sitemap_items)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        records, urls = build(args.root.resolve())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"SEO build failed: {exc}")
        return 1
    print(f"SEO build complete: {records} canonical record page(s), {urls} sitemap URL(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
