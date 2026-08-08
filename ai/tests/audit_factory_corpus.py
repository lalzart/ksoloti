#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Audit every factory AXP with compact, reproducible compatibility totals."""

import argparse
import collections
import json
import sys
from pathlib import Path


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

import ksai  # noqa: E402


LIBRARIES = (
    "axoloti-factory",
    "ksoloti-objects",
    "axoloti-contrib",
    "ksoloti-contrib",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-root", type=Path, required=True)
    parser.add_argument("--expect-accepted", type=int)
    parser.add_argument("--expect-rejected", type=int)
    args = parser.parse_args()

    root = args.library_root.expanduser().resolve()
    catalog, catalog_diagnostics = ksai.build_catalog(
        [(name, root / name) for name in LIBRARIES]
    )
    patches = sorted((root / "axoloti-factory" / "patches").rglob("*.axp"))
    accepted = 0
    rejected = 0
    roundtrip_failures = 0
    diagnostics = collections.Counter()
    fingerprint_rows = []
    for path in patches:
        imported = ksai.import_legacy_axp(path, catalog)
        relative = path.relative_to(root).as_posix()
        codes = sorted(item["code"] for item in imported["diagnostics"])
        error_codes = sorted(
            item["code"]
            for item in imported["diagnostics"]
            if item.get("severity") == "error"
        )
        fingerprint_rows.append([relative, imported["ok"], codes])
        if imported["ok"]:
            accepted += 1
            if not ksai.roundtrip_legacy_axp(path, catalog)["ok"]:
                roundtrip_failures += 1
        else:
            rejected += 1
            diagnostics.update(error_codes)

    expected_match = (
        (args.expect_accepted is None or accepted == args.expect_accepted)
        and (args.expect_rejected is None or rejected == args.expect_rejected)
    )
    catalog_ok = not any(item.severity == "error" for item in catalog_diagnostics)
    response = {
        "ok": catalog_ok and roundtrip_failures == 0 and expected_match,
        "factory_patch_count": len(patches),
        "accepted": accepted,
        "rejected": rejected,
        "accepted_roundtrip_failures": roundtrip_failures,
        "diagnostic_occurrences": dict(sorted(diagnostics.items())),
        "result_sha256": ksai._sha256(
            json.dumps(fingerprint_rows, separators=(",", ":")).encode("utf-8")
        ),
        "catalog_object_count": len(catalog.get("objects", [])),
        "catalog_diagnostics": [item.to_dict() for item in catalog_diagnostics],
        "expected_match": expected_match,
    }
    print(json.dumps(response, sort_keys=True, separators=(",", ":")))
    return 0 if response["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
