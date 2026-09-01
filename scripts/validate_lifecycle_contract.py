#!/usr/bin/env python3
"""Validate the v1.1 Doberman lifecycle contract across public files."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "registry.schema.json").read_text(encoding="utf-8"))
PORTAL = (ROOT / "index.html").read_text(encoding="utf-8")
PROFILE = (ROOT / "profiles" / "male.html").read_text(encoding="utf-8")
BUILD = (ROOT / "scripts" / "build_registry.py").read_text(encoding="utf-8")
MIGRATE = (ROOT / "scripts" / "migrate_lifecycle_v1_1.py").read_text(encoding="utf-8")
errors: list[str] = []


identity = SCHEMA["$defs"]["doberman"]["properties"]["identity"]
if SCHEMA["properties"]["schema_version"].get("const") != "1.1.0":
    errors.append("canonical schema_version must be 1.1.0")
if set(identity["properties"]["life_stage"].get("enum", [])) != {"puppy", "junior", "adult", "veteran", "unknown"}:
    errors.append("life_stage must contain age categories only")
if set(identity["properties"]["life_status"].get("enum", [])) != {"living", "deceased", "unknown"}:
    errors.append("life_status enum is incomplete")
for field in ("life_stage", "life_status"):
    if field not in identity.get("required", []):
        errors.append(f"identity.{field} must be required")

for token in ('legacy_deceased = source_stage == "deceased"', 'identity["life_stage"] = "unknown" if legacy_deceased', '("deceased" if legacy_deceased else "unknown")'):
    if token not in MIGRATE:
        errors.append(f"legacy submission migration missing: {token}")
for token in ('"life_status": life_status', 'if life_status == "deceased"', '"schema_version": "1.1.0"'):
    if token not in BUILD:
        errors.append(f"registry builder lifecycle logic missing: {token}")
for token in ("record.life_status !== 'deceased'", "const publicDobermanStatus = value", "? 'DECEASED' : ''"):
    if token not in PORTAL:
        errors.append(f"portal lifecycle behavior missing: {token}")
for token in ('id="lifeStatusBadge"', 'lifeStatus:"Life status"', 'lifeSpan:"Life span"', 'const isDeceased=lifecycleState==="deceased"', 'lifecycleState==="living"?""'):
    if token not in PROFILE:
        errors.append(f"male profile lifecycle display missing: {token}")

if errors:
    print("Lifecycle contract FAIL", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)
print("Lifecycle contract PASS")
