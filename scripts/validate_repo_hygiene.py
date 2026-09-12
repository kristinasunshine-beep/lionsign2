#!/usr/bin/env python3
"""Fail CI when tracked/generated/admin-only artifacts leak into the public Pages repository."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
errors = []

try:
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
except Exception:
    tracked = [str(p.relative_to(ROOT)).replace("\\", "/") for p in ROOT.rglob("*") if p.is_file()]

for relative in tracked:
    path = ROOT / relative
    # A cleanup step may have deleted a tracked artifact before the final commit.
    if not path.exists():
        continue
    normalized = relative.replace("\\", "/")
    if "/__pycache__/" in f"/{normalized}" or normalized.endswith(".pyc"):
        errors.append(f"tracked Python cache/bytecode present: {normalized}")

for relative in (
    "scripts/indexnow.py",
    "scripts/test_indexnow.py",
    "scripts/build_relationship_opportunities.py",
    "scripts/validate_relationship_opportunities.py",
    "data/relationship-opportunities.json",
):
    if (ROOT / relative).exists():
        errors.append(f"retired/admin-only artifact present: {relative}")

for relative in tracked:
    path = ROOT / relative
    if not path.exists():
        continue
    normalized = relative.replace("\\", "/")
    if "/evidence/" in f"/{normalized}" or "/source-documents/" in f"/{normalized}":
        errors.append(f"private evidence/source document present in public repo: {normalized}")

gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8") if (ROOT / ".gitignore").exists() else ""
for token in ("__pycache__/", "*.pyc", "media/**/evidence/", "private/", "vault/"):
    if token not in gitignore:
        errors.append(f".gitignore missing {token}")

if errors:
    print("Repository hygiene validation FAIL", file=sys.stderr)
    for error in errors:
        print(" -", error, file=sys.stderr)
    raise SystemExit(1)
print("Repository hygiene validation PASS")
