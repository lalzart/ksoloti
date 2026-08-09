# SPDX-License-Identifier: GPL-3.0-or-later

import copy
import sys
import unittest
from pathlib import Path


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

import object_sdk  # noqa: E402


class ObjectSDKTestCase(unittest.TestCase):
    def setUp(self):
        self.root = AI_DIR / "sdk" / "example-library" / "objects" / "ai"
        self.path = self.root / "gain.manifest.json"
        self.manifest = object_sdk.load_manifest(self.path)

    def test_example_manifest_matches_deterministic_glue(self):
        diagnostics = object_sdk.validate_manifest(self.manifest, self.root)
        self.assertEqual([], diagnostics)
        self.assertEqual((self.root / "gain.axo").read_bytes(), object_sdk.render_axo(self.manifest))

    def test_manifest_rejects_code_injection_argument(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["implementation"]["arguments"][0] = "inlet_in); system(\"bad\")"
        diagnostics = object_sdk.validate_manifest(manifest, self.root)
        self.assertIn("E_SDK_ARGUMENT", {item["code"] for item in diagnostics})

    def test_manifest_rejects_generated_name_collisions_and_unknown_arguments(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["implementation"]["instance_name"] = "dsp"
        manifest["implementation"]["arguments"][0] = "inlet_missing"
        diagnostics = object_sdk.validate_manifest(manifest, self.root)
        codes = {item["code"] for item in diagnostics}
        self.assertIn("E_SDK_INSTANCE_RESERVED", codes)
        self.assertIn("E_SDK_ARGUMENT_REFERENCE", codes)

    def test_bounded_int32_parameter_renders_legacy_value_elements(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["parameters"].append(
            {
                "id": manifest["stable_id"] + ".count",
                "name": "count",
                "type": "int32",
                "default": "2",
                "minimum": 1,
                "maximum": 4,
            }
        )
        manifest["implementation"]["arguments"].append("param_count")
        self.assertEqual([], object_sdk.validate_manifest(manifest, self.root))
        rendered = object_sdk.render_axo(manifest).decode("utf-8")
        self.assertIn('<int32 name="count">', rendered)
        self.assertIn('<MinValue i="1"/>', rendered)
        self.assertIn('<MaxValue i="4"/>', rendered)

    def test_bounded_int32_parameter_rejects_missing_or_invalid_bounds(self):
        for minimum, maximum, default in ((None, None, "2"), (4, 1, "2"), (1, 4, "5")):
            with self.subTest(minimum=minimum, maximum=maximum, default=default):
                manifest = copy.deepcopy(self.manifest)
                parameter = {
                    "id": manifest["stable_id"] + ".count",
                    "name": "count",
                    "type": "int32",
                    "default": default,
                }
                if minimum is not None:
                    parameter["minimum"] = minimum
                if maximum is not None:
                    parameter["maximum"] = maximum
                manifest["parameters"].append(parameter)
                diagnostics = object_sdk.validate_manifest(manifest, self.root)
                codes = {item["code"] for item in diagnostics}
                expected = (
                    "E_SDK_PARAMETER_BOUNDS"
                    if minimum is None or minimum > maximum
                    else "E_SDK_PARAMETER_DEFAULT"
                )
                self.assertIn(expected, codes)

    def test_compatibility_metadata_is_reported_and_validated(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["compatibility"] = {
            "tier": "h7-recommended",
            "build_status": "host-verified",
            "tested_targets": ["host-c++17"],
            "notes": "Large fixed delay memory is better suited to H7 targets.",
        }
        self.assertEqual([], object_sdk.validate_manifest(manifest, self.root))
        manifest["compatibility"]["tier"] = "mystery-chip"
        diagnostics = object_sdk.validate_manifest(manifest, self.root)
        self.assertEqual(diagnostics[0]["code"], "E_SDK_COMPATIBILITY_TIER")

    def test_generated_argument_escapes_user_underscores_for_java_abi(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["parameters"].append(
            {
                "id": manifest["stable_id"] + ".minimum-frequency",
                "name": "minimum_frequency",
                "type": "int32",
                "default": "50",
                "minimum": 40,
                "maximum": 200,
            }
        )
        manifest["implementation"]["arguments"].append("param_minimum_frequency")
        rendered = object_sdk.render_axo(manifest).decode("utf-8")
        self.assertIn("param_minimum__frequency", rendered)
        self.assertNotIn("param_minimum_frequency,", rendered)


if __name__ == "__main__":
    unittest.main()
