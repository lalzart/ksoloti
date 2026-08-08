#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run semantic round trips against named patches in installed 1.1.0 libraries."""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
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
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).with_name("stock-roundtrip-v1.txt"),
    )
    args = parser.parse_args()

    root = args.library_root.expanduser().resolve()
    catalog, catalog_diagnostics = ksai.build_catalog(
        [(name, root / name) for name in LIBRARIES]
    )
    paths = [
        line.strip()
        for line in args.manifest.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    results = [ksai.roundtrip_legacy_axp(root / relative, catalog) for relative in paths]
    example_result = ksai.validate_patch(AI_DIR / "examples" / "minimal-sine.kpatch", catalog)
    example_bytes = None
    example_diagnostics = []
    if example_result["ok"]:
        example_bytes, example_diagnostics = ksai.emit_legacy_axp(
            example_result["patch_ir"], catalog
        )
    golden_bytes = (Path(__file__).parent / "fixtures" / "deterministic-minimal.axp").read_bytes()
    golden_equal = example_bytes == golden_bytes
    integer_result = ksai.validate_patch(
        Path(__file__).parent / "fixtures" / "int32-mini.kpatch", catalog
    )
    integer_bytes = None
    integer_diagnostics = []
    if integer_result["ok"]:
        integer_bytes, integer_diagnostics = ksai.emit_legacy_axp(
            integer_result["patch_ir"], catalog
        )
    integer_tag_ok = (
        integer_bytes is not None
        and ET.fromstring(integer_bytes).find("./obj/params/int32.small") is not None
    )
    ok = (
        not any(item.severity == "error" for item in catalog_diagnostics)
        and all(result["ok"] for result in results)
        and golden_equal
        and integer_tag_ok
    )
    catalog_bytes = (
        json.dumps(catalog, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    response = {
        "ok": ok,
        "catalog_sha256": ksai._sha256(catalog_bytes),
        "object_count": len(catalog["objects"]),
        "catalog_diagnostics": [item.to_dict() for item in catalog_diagnostics],
        "golden_example": {
            "ok": golden_equal,
            "sha256": ksai._sha256(example_bytes or b""),
            "diagnostics": example_result["diagnostics"]
            + [item.to_dict() for item in example_diagnostics],
        },
        "parameter_instance_mapping": {
            "ok": integer_tag_ok,
            "definition_type": "int32.mini",
            "instance_type": "int32.small",
            "diagnostics": integer_result["diagnostics"]
            + [item.to_dict() for item in integer_diagnostics],
        },
        "results": results,
    }
    print(json.dumps(response, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
