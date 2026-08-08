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


if __name__ == "__main__":
    unittest.main()
