#!/usr/bin/env python3
"""Validate the repository's GitHub Actions workflow and required QA steps."""

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build-registry.yml"


def fail(message: str) -> None:
    print(f"GitHub Actions workflow contract FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if not WORKFLOW.is_file():
        fail("build-registry.yml is missing")

    text = WORKFLOW.read_text(encoding="utf-8")
    lines = text.splitlines()

    if "\t" in text:
        fail("tabs are not valid indentation")

    # This workflow deliberately uses a conservative YAML subset. Validate its
    # indentation and mapping/list shape without adding a third-party dependency.
    previous_significant = ""
    previous_indent = 0
    in_block_scalar = False
    block_indent = 0
    for number, raw in enumerate(lines, start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        if indent % 2:
            fail(f"line {number} uses odd indentation")

        if in_block_scalar:
            if indent > block_indent:
                continue
            in_block_scalar = False

        if indent > previous_indent + 2:
            fail(f"line {number} jumps more than one indentation level")
        if indent > previous_indent and not (
            previous_significant.endswith(":")
            or previous_significant.endswith("|")
            or previous_significant.startswith("-")
        ):
            fail(f"line {number} is nested below a scalar")

        if not (
            stripped.startswith("-")
            or re.match(r"^[A-Za-z0-9_.-]+\s*:", stripped)
        ):
            fail(f"line {number} is outside the supported workflow YAML shape")

        if stripped.endswith("|"):
            in_block_scalar = True
            block_indent = indent
        previous_significant = stripped
        previous_indent = indent

    required_fragments = (
        "name: Rebuild Doberman Index Registry",
        "actions/checkout@v5",
        "actions/setup-python@v5",
        "python-version: \"3.12\"",
        "actions/setup-node@v4",
        "node-version: \"20\"",
        "python scripts/validate_workflow_contract.py",
        "python scripts/validate_submission_visual_master.py",
        "python scripts/validate_assessment_standard.py",
        "python scripts/validate_lifecycle_contract.py",
        "python scripts/apply_lifecycle_policy.py --write",
        "python scripts/validate_v63_contract.py",
        "python scripts/validate_male_profile_contract.py",
        "python scripts/validate_male_visual_master.py",
        "python scripts/validate_homepage.py",
        "python scripts/validate_promotion_belt.py",
        "python scripts/validate_targeted_production_patch.py",
        "python scripts/test_registry_consistency.py",
        "python scripts/validate_gallery_schema_contract.py",
        "node scripts/test_display_name.js",
        "node scripts/test_lifecycle.js",
        "node scripts/test_public_ui.js",
        "node scripts/test_media_presentation.js",
        "node scripts/test_litter_profile.js",
        "python scripts/validate_litter_contract.py",
        "python scripts/build_seo.py",
        "python scripts/validate_seo.py",
        "python scripts/validate_repo_hygiene.py",
        "rm -rf scripts/__pycache__",
        "rm -f scripts/indexnow.py scripts/test_indexnow.py",
        "rm -f scripts/build_relationship_opportunities.py scripts/validate_relationship_opportunities.py",
        "rm -f data/relationship-opportunities.json",
        "find media -type d -name evidence -prune -exec rm -rf {} +",
        "python scripts/sanitize_public_evidence.py",
        "python scripts/validate_owner_link_kit.py",
        "assets/js/owner-link-kit.js",
        "python scripts/audit_performance.py",
        "node scripts/test_seo_runtime.js",
    )
    missing = [fragment for fragment in required_fragments if fragment not in text]
    if missing:
        fail("missing required workflow entries: " + ", ".join(missing))

    if text.count("jobs:") != 1 or text.count("steps:") != 1:
        fail("expected exactly one jobs mapping and one steps list")

    print("GitHub Actions workflow contract PASS")


if __name__ == "__main__":
    main()
