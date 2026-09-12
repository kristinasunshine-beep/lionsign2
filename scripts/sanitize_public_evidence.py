#!/usr/bin/env python3
"""Remove public evidence-file references from source JSON before publication.

Raw evidence belongs in a separate private vault, never in the public Pages repo.
This script deliberately leaves public facts/results intact while clearing only
keys named evidence_file.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = (ROOT / "data" / "dobermans", ROOT / "data" / "kennels", ROOT / "data" / "litters")


def scrub(value):
    changed = False
    if isinstance(value, dict):
        for key in list(value):
            if key == "evidence_file" and value[key] not in (None, ""):
                value[key] = None
                changed = True
            else:
                child_changed = scrub(value[key])
                changed = changed or child_changed
    elif isinstance(value, list):
        for item in value:
            changed = scrub(item) or changed
    return changed


def main():
    changed_files = []
    for directory in SOURCE_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("DI-*.json")):
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if scrub(data):
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                changed_files.append(str(path.relative_to(ROOT)))
    print(f"Public evidence reference scrub: {len(changed_files)} file(s) updated")
    for item in changed_files:
        print(" -", item)


if __name__ == "__main__":
    main()
