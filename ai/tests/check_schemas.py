#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate AI schemas and one minimal instance of each schema."""

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


AI_DIR = Path(__file__).resolve().parents[1]
SCHEMA_DIR = AI_DIR / "schemas"


def load(name):
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def main() -> int:
    patch_schema = load("patch-v1.schema.json")
    catalog_schema = load("catalog-v1.schema.json")
    object_schema = load("object-manifest-v1.schema.json")
    Draft202012Validator.check_schema(patch_schema)
    Draft202012Validator.check_schema(catalog_schema)
    Draft202012Validator.check_schema(object_schema)

    patch = {
        "schema_version": 1,
        "patch": {"id": "schema-probe", "target": "ksoloti-core@1.1.0"},
        "settings": {},
        "nodes": [],
        "edges": [],
        "assertions": {},
    }
    catalog = {
        "schema_version": 1,
        "source_format": "axo-1.x",
        "libraries": [],
        "objects": [],
    }
    Draft202012Validator(patch_schema).validate(patch)
    Draft202012Validator(catalog_schema).validate(catalog)
    manifest = json.loads(
        (AI_DIR / "sdk" / "example-library" / "objects" / "ai" / "gain.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(object_schema, format_checker=FormatChecker()).validate(manifest)
    bounded = copy.deepcopy(manifest)
    bounded["parameters"].append(
        {
            "id": bounded["stable_id"] + ".count",
            "name": "count",
            "type": "int32",
            "default": "2",
            "minimum": 1,
            "maximum": 4,
        }
    )
    object_validator = Draft202012Validator(object_schema, format_checker=FormatChecker())
    object_validator.validate(bounded)
    del bounded["parameters"][-1]["maximum"]
    if not list(object_validator.iter_errors(bounded)):
        raise AssertionError("object schema accepted int32 without maximum")
    print("JSON schemas: 3 passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
