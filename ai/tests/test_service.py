# SPDX-License-Identifier: GPL-3.0-or-later

import json
import sys
import unittest
from pathlib import Path


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

import ksai  # noqa: E402
from ksai_service import MAX_REQUEST_BYTES, ReadOnlyAPI, is_loopback_host  # noqa: E402
import test_ksai as fixtures  # noqa: E402


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.KSAITestCase("test_catalog_is_deterministic_and_preserves_variants")
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    def api(self):
        return ReadOnlyAPI(
            self.fixture.catalog(),
            search=ksai.search_catalog,
            inspect=ksai.inspect_catalog,
            validate_text=ksai.validate_patch_text,
            explain=ksai.explain_validated_patch,
        )

    def test_service_is_loopback_and_read_only(self):
        self.assertTrue(is_loopback_host("127.0.0.1"))
        self.assertTrue(is_loopback_host("::1"))
        self.assertFalse(is_loopback_host("0.0.0.0"))
        status, health = self.api().dispatch("GET", "/v1/health")
        self.assertEqual(200, status)
        self.assertEqual("disabled", health["mutation"])
        status, result = self.api().dispatch("POST", "/v1/patch/build", b"{}")
        self.assertEqual(404, status)
        self.assertEqual("E_ROUTE", result["diagnostics"][0]["code"])

    def test_service_search_validate_and_explain(self):
        api = self.api()
        status, result = api.dispatch("GET", "/v1/catalog/search?q=sine&limit=3")
        self.assertEqual(200, status)
        self.assertEqual("factory:osc/sine", result["matches"][0]["object"])

        source = """\
kpatch 1
patch service
target ksoloti-core@1.1.0
node osc factory:osc/sine
node out "factory:audio/out stereo"
connect osc.wave -> out.left,out.right
"""
        body = json.dumps({"source": source}).encode("utf-8")
        status, validated = api.dispatch("POST", "/v1/patch/validate", body)
        self.assertEqual(200, status)
        self.assertTrue(validated["ok"])
        status, explained = api.dispatch("POST", "/v1/patch/explain", body)
        self.assertEqual(200, status)
        self.assertEqual(2, explained["patch"]["node_count"])

    def test_service_rejects_bad_or_large_requests(self):
        api = self.api()
        status, result = api.dispatch("POST", "/v1/patch/validate", b"not-json")
        self.assertEqual(400, status)
        self.assertEqual("E_JSON", result["diagnostics"][0]["code"])
        status, result = api.dispatch(
            "POST", "/v1/patch/validate", b"x" * (MAX_REQUEST_BYTES + 1)
        )
        self.assertEqual(413, status)
        self.assertEqual("E_BODY_SIZE", result["diagnostics"][0]["code"])


if __name__ == "__main__":
    unittest.main()
