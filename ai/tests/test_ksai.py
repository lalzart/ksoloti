# SPDX-License-Identifier: GPL-3.0-or-later

import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

import ksai  # noqa: E402


OSCILLATOR_AXO = """\
<objdefs>
  <obj.normal id="sine" uuid="osc-uuid" sha="osc-sha">
    <upgradeSha>osc-old-sha</upgradeSha>
    <sDescription>sine wave oscillator</sDescription>
    <author>Test</author>
    <license>BSD</license>
    <inlets><frac32.bipolar name="pitch" description="pitch"/></inlets>
    <outlets><frac32buffer.bipolar name="wave" description="wave"/></outlets>
    <params><frac32.s.map.pitch name="pitch"/></params>
    <attribs/>
    <code.krate>control();</code.krate>
    <code.srate>sample();</code.srate>
  </obj.normal>
</objdefs>
"""


OUTPUT_AXO = """\
<objdefs>
  <obj.normal id="out stereo" uuid="out-uuid" sha="out-sha">
    <upgradeSha>out-old-sha</upgradeSha>
    <sDescription>stereo output</sDescription>
    <author>Test</author>
    <license>BSD</license>
    <inlets>
      <frac32buffer name="left"/>
      <frac32buffer name="right"/>
    </inlets>
    <outlets/>
    <params/>
    <attribs/>
    <code.krate>output();</code.krate>
  </obj.normal>
</objdefs>
"""


LEGACY_AXP = """\
<patch-1.0 appVersion="1.0.8">
  <obj type="osc/sine" sha="osc-old-sha" name="osc~1" x="14" y="14">
    <params><frac32.s.map name="pitch" value="0"/></params>
    <attribs/>
  </obj>
  <comment type="patch/comment" x="14" y="140" text="UI only"/>
  <obj type="audio/out stereo" uuid="out-uuid" name="out" x="238" y="14">
    <params/>
    <attribs/>
  </obj>
  <nets>
    <net>
      <source obj="osc~1" outlet="wave"/>
      <dest obj="out" inlet="left"/>
      <dest obj="out" inlet="right"/>
    </net>
  </nets>
  <settings><subpatchmode>no</subpatchmode></settings>
  <notes/>
  <windowPos><x>0</x><y>0</y><width>640</width><height>480</height></windowPos>
</patch-1.0>
"""


OVERLOADED_AXO = """\
<objdefs>
  <obj.normal id="mix" uuid="mix-frac">
    <upgradeSha>mix-old</upgradeSha>
    <inlets><frac32 name="a"/></inlets>
    <outlets><frac32 name="out"/></outlets>
    <params/><attribs/>
  </obj.normal>
  <obj.normal id="mix" uuid="mix-buffer">
    <upgradeSha>mix-old</upgradeSha>
    <inlets><frac32buffer name="a"/></inlets>
    <outlets><frac32buffer name="out"/></outlets>
    <params/><attribs/>
  </obj.normal>
</objdefs>
"""


ATTRIBUTE_AXO = """\
<objdefs>
  <obj.normal id="config" uuid="config-uuid">
    <inlets/><outlets/><params/>
    <attribs>
      <combo name="mode">
        <MenuEntries><string>clean</string><string>crunch</string></MenuEntries>
        <CEntries><string>0</string><string>1</string></CEntries>
      </combo>
      <spinner name="voices" MinValue="1" MaxValue="8" DefaultValue="4"/>
      <int name="offset" MinValue="-2" MaxValue="2" DefaultValue="0"/>
      <objref name="target"/>
      <table name="expression"/>
      <file name="sample"/>
      <text name="script"/>
    </attribs>
  </obj.normal>
</objdefs>
"""


TEXT_SINK_AXO = """\
<objdefs>
  <obj.normal id="text sink" uuid="text-sink-uuid">
    <inlets><charptr32 name="in"/></inlets>
    <outlets/><params/><attribs/>
  </obj.normal>
</objdefs>
"""


LEGACY_ATTRIBUTES_AXP = """\
<patch-1.0 appVersion="1.1.0">
  <obj type="osc/sine" uuid="osc-uuid" name="osc~1" x="14" y="14">
    <params/><attribs/>
  </obj>
  <obj type="attr/config" uuid="config-uuid" name="config" x="238" y="14">
    <params/>
    <attribs>
      <combo attributeName="mode" selection="crunch"/>
      <spinner attributeName="voices" value="6"/>
      <int attributeName="offset" value="-1"/>
      <objref attributeName="target" obj="osc~1"/>
      <table attributeName="expression" table="outlet_out=inlet_in&gt;0?inlet_in:0"/>
      <file attributeName="sample" file="samples/demo.wav"/>
      <text attributeName="script"><sText><![CDATA[line one
line two]]></sText></text>
    </attribs>
  </obj>
  <nets/>
  <settings><subpatchmode>no</subpatchmode></settings>
</patch-1.0>
"""


class KSAITestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "factory"
        (self.root / "objects" / "osc").mkdir(parents=True)
        (self.root / "objects" / "audio").mkdir(parents=True)
        (self.root / "objects" / "mix").mkdir(parents=True)
        (self.root / "objects" / "attr").mkdir(parents=True)
        (self.root / "objects" / "sink").mkdir(parents=True)
        (self.root / "objects" / "osc" / "sine.axo").write_text(OSCILLATOR_AXO, encoding="utf-8")
        (self.root / "objects" / "audio" / "out stereo.axo").write_text(OUTPUT_AXO, encoding="utf-8")
        (self.root / "objects" / "mix" / "mix.axo").write_text(OVERLOADED_AXO, encoding="utf-8")
        (self.root / "objects" / "attr" / "config.axo").write_text(ATTRIBUTE_AXO, encoding="utf-8")
        (self.root / "objects" / "sink" / "text sink.axo").write_text(TEXT_SINK_AXO, encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def catalog(self):
        catalog, diagnostics = ksai.build_catalog([("factory", self.root)])
        self.assertEqual([], diagnostics)
        return catalog

    def write_patch(self, text):
        path = Path(self.temp.name) / "test.kpatch"
        path.write_text(text, encoding="utf-8")
        return path

    def test_catalog_is_deterministic_and_preserves_variants(self):
        first = self.catalog()
        second = self.catalog()
        first_json = json.dumps(first, sort_keys=True, separators=(",", ":"))
        second_json = json.dumps(second, sort_keys=True, separators=(",", ":"))
        self.assertEqual(first_json, second_json)
        self.assertEqual(6, len(first["objects"]))
        self.assertRegex(first["libraries"][0]["content_sha256"], r"^[0-9a-f]{64}$")
        refs = [obj["ref"] for obj in first["objects"]]
        self.assertIn("factory:osc/sine@osc-uuid", refs)
        self.assertIn("factory:mix/mix@mix-frac", refs)
        oscillator = next(obj for obj in first["objects"] if obj["ref"].endswith("@osc-uuid"))
        self.assertEqual(["control", "sample"], oscillator["implementation"]["code_sections"])
        self.assertEqual("objects/osc/sine.axo", oscillator["source"]["path"])
        self.assertEqual(["osc-old-sha", "osc-sha"], oscillator["source"]["legacy_hashes"])
        self.assertEqual("frac32.s.map", oscillator["parameters"][0]["instance_type"])
        self.assertEqual("int32.small", ksai._parameter_instance_type("int32.mini"))
        config = next(obj for obj in first["objects"] if obj["id"] == "attr/config")
        mode = next(item for item in config["attributes"] if item["name"] == "mode")
        voices = next(item for item in config["attributes"] if item["name"] == "voices")
        self.assertEqual(["clean", "crunch"], mode["choices"])
        self.assertEqual((1, 8, 4), (voices["minimum"], voices["maximum"], voices["default"]))
        self.assertEqual(
            ("2147483647", None),
            ksai._normalize_parameter_value(
                {"type": "bin16", "instance_type": "bin16"}, "2147483647"
            ),
        )

    def test_catalog_carries_validated_object_sdk_compatibility(self):
        library = AI_DIR / "sdk" / "example-library"
        catalog, diagnostics = ksai.build_catalog([("sdk", library)])
        self.assertEqual([], diagnostics)
        gain = next(item for item in catalog["objects"] if item["id"] == "ai/gain")
        self.assertEqual("core", gain["sdk"]["compatibility"]["tier"])
        self.assertEqual("host-verified", gain["sdk"]["compatibility"]["build_status"])
        searched = ksai.search_catalog(catalog, "gain", 1)["matches"][0]
        self.assertEqual(gain["sdk"], searched["sdk"])
        inspected = ksai.inspect_catalog(catalog, "sdk:ai/gain")
        self.assertEqual(gain["sdk"], inspected["variants"][0]["sdk"])

    def test_search_groups_overloads_and_returns_compact_signatures(self):
        result = ksai.search_catalog(self.catalog(), "mix", 5)
        self.assertEqual(1, len(result["matches"]))
        match = result["matches"][0]
        self.assertEqual("factory:mix/mix", match["object"])
        self.assertEqual(2, match["variant_count"])
        self.assertNotIn("implementation", match)

        config = ksai.search_catalog(self.catalog(), "config", 5)["matches"][0]
        contracts = config["variants"][0]["attrs"]
        mode = next(item for item in contracts if item["name"] == "mode")
        voices = next(item for item in contracts if item["name"] == "voices")
        self.assertEqual(["clean", "crunch"], mode["choices"])
        self.assertEqual((1, 8, 4), (voices["minimum"], voices["maximum"], voices["default"]))

    def test_inspect_explain_diff_and_repair_are_compact_and_read_only(self):
        catalog = self.catalog()
        inspected = ksai.inspect_catalog(catalog, "factory:osc/sine")
        self.assertTrue(inspected["ok"])
        self.assertEqual(1, inspected["variant_count"])
        self.assertNotIn("code", inspected["variants"][0]["implementation"])

        valid = self.write_patch(
            """\
kpatch 1
patch explain
target ksoloti-core@1.1.0
node osc factory:osc/sine
node out "factory:audio/out stereo"
param osc.pitch 0
connect osc.wave -> out.left,out.right
"""
        )
        validated = ksai.validate_patch(valid, catalog)
        explained = ksai.explain_validated_patch(validated, catalog)
        self.assertEqual((2, 2), (explained["patch"]["node_count"], explained["patch"]["edge_count"]))
        self.assertTrue(ksai.diff_validated_patches(validated, validated)["equal"])

        broken = self.write_patch(
            """\
kpatch 1
patch repair
target ksoloti-core@1.1.0
node osc factory:osc/sine
param osc.pich 0
"""
        )
        repair = ksai.repair_plan(ksai.validate_patch(broken, catalog))
        self.assertFalse(repair["ok"])
        self.assertFalse(repair["changed"])
        self.assertEqual(["pitch"], repair["repairs"][0]["candidates"])

    def test_minimal_patch_resolves_and_validates(self):
        path = self.write_patch(
            """\
kpatch 1
patch test
target ksoloti-core@1.1.0
node osc factory:osc/sine
node out "factory:audio/out stereo"
param osc.pitch 0
connect osc.wave -> out.left,out.right
assert output=finite
"""
        )
        result = ksai.validate_patch(path, self.catalog())
        self.assertTrue(result["ok"], result["diagnostics"])
        self.assertEqual("pass", result["evidence"]["graph_structure"])
        self.assertEqual("not_run", result["evidence"]["arm_compile_link"])
        self.assertEqual("factory:osc/sine@osc-uuid", result["patch_ir"]["nodes"][0]["resolved_ref"])

    def test_overload_requires_exact_legacy_uuid(self):
        path = self.write_patch(
            """\
kpatch 1
patch ambiguous
target ksoloti-core@1.1.0
node mix factory:mix/mix
"""
        )
        result = ksai.validate_patch(path, self.catalog())
        self.assertFalse(result["ok"])
        self.assertIn("E_OBJECT_AMBIGUOUS", {item["code"] for item in result["diagnostics"]})

    def test_exact_overload_variant_resolves(self):
        path = self.write_patch(
            """\
kpatch 1
patch exact
target ksoloti-core@1.1.0
node mix factory:mix/mix@mix-frac
"""
        )
        result = ksai.validate_patch(path, self.catalog())
        self.assertTrue(result["ok"], result["diagnostics"])
        self.assertEqual("factory:mix/mix@mix-frac", result["patch_ir"]["nodes"][0]["resolved_ref"])

    def test_graph_constraints_resolve_kpatch_overload_deterministically(self):
        path = self.write_patch(
            """\
kpatch 1
patch constrained
target ksoloti-core@1.1.0
node osc factory:osc/sine
node mix factory:mix/mix
node out "factory:audio/out stereo"
connect osc.wave -> mix.a
connect mix.out -> out.left
"""
        )
        result = ksai.validate_patch(path, self.catalog())
        self.assertTrue(result["ok"], result["diagnostics"])
        mix = next(node for node in result["patch_ir"]["nodes"] if node["id"] == "mix")
        self.assertEqual("factory:mix/mix@mix-buffer", mix["resolved_ref"])
        self.assertIn(
            "W_OBJECT_OVERLOAD_CONSTRAINED",
            {item["code"] for item in result["diagnostics"]},
        )

    def test_graph_constraints_with_zero_valid_overloads_fail_closed(self):
        path = self.write_patch(
            """\
kpatch 1
patch impossible-overload
target ksoloti-core@1.1.0
node mix factory:mix/mix
node sink "factory:sink/text sink@text-sink-uuid"
connect mix.out -> sink.in
"""
        )
        result = ksai.validate_patch(path, self.catalog())
        self.assertFalse(result["ok"])
        self.assertIn(
            "E_OBJECT_OVERLOAD_CONSTRAINT",
            {item["code"] for item in result["diagnostics"]},
        )

    def test_unknown_parameter_and_port_fail_closed(self):
        path = self.write_patch(
            """\
kpatch 1
patch broken
target ksoloti-core@1.1.0
node osc factory:osc/sine
node out "factory:audio/out stereo"
param osc.frequency 440
connect osc.missing -> out.left
"""
        )
        result = ksai.validate_patch(path, self.catalog())
        codes = {item["code"] for item in result["diagnostics"]}
        self.assertFalse(result["ok"])
        self.assertIn("E_PARAM_UNKNOWN", codes)
        self.assertIn("E_EDGE_SOURCE_PORT", codes)

    def test_multiple_drivers_are_rejected(self):
        path = self.write_patch(
            """\
kpatch 1
patch drivers
target ksoloti-core@1.1.0
node a factory:osc/sine
node b factory:osc/sine
node out "factory:audio/out stereo"
connect a.wave -> out.left
connect b.wave -> out.left
"""
        )
        result = ksai.validate_patch(path, self.catalog())
        self.assertFalse(result["ok"])
        self.assertIn("E_MULTIPLE_DRIVERS", {item["code"] for item in result["diagnostics"]})

    def test_legacy_axp_import_preserves_name_and_resolves_upgrade_sha(self):
        result = ksai.import_legacy_axp_bytes(
            LEGACY_AXP.encode("utf-8"), self.catalog(), "legacy"
        )
        self.assertTrue(result["ok"], result["diagnostics"])
        oscillator = result["patch_ir"]["nodes"][0]
        self.assertEqual("osc_1", oscillator["id"])
        self.assertEqual("osc~1", oscillator["name"])
        self.assertEqual("factory:osc/sine@osc-uuid", oscillator["resolved_ref"])
        self.assertEqual("0.0", oscillator["parameters"]["pitch"])
        self.assertIn("W_AXP_UI_IGNORED", {item["code"] for item in result["diagnostics"]})

    def test_kpatch_and_axp_rendering_are_deterministic_and_semantic(self):
        imported = ksai.import_legacy_axp_bytes(
            LEGACY_AXP.encode("utf-8"), self.catalog(), "legacy"
        )
        self.assertTrue(imported["ok"], imported["diagnostics"])
        first_kpatch = ksai.render_kpatch(imported["patch_ir"])
        second_kpatch = ksai.render_kpatch(imported["patch_ir"])
        self.assertEqual(first_kpatch, second_kpatch)
        self.assertIn("node osc_1 factory:osc/sine@osc-uuid 'osc~1'", first_kpatch)

        reparsed = ksai.validate_patch_text(first_kpatch, self.catalog())
        self.assertTrue(reparsed["ok"], reparsed["diagnostics"])
        first_axp, first_diagnostics = ksai.emit_legacy_axp(reparsed["patch_ir"], self.catalog())
        second_axp, second_diagnostics = ksai.emit_legacy_axp(reparsed["patch_ir"], self.catalog())
        self.assertEqual([], first_diagnostics)
        self.assertEqual([], second_diagnostics)
        self.assertEqual(first_axp, second_axp)
        self.assertIsNotNone(first_axp)
        emitted_root = ET.fromstring(first_axp)
        emitted_parameter = emitted_root.find("./obj/params/frac32.s.map")
        self.assertIsNotNone(emitted_parameter)
        self.assertEqual("0.0", emitted_parameter.attrib["value"])

        reimported = ksai.import_legacy_axp_bytes(first_axp, self.catalog(), "legacy")
        self.assertTrue(reimported["ok"], reimported["diagnostics"])
        self.assertEqual(
            ksai.semantic_patch_signature(imported["patch_ir"]),
            ksai.semantic_patch_signature(reimported["patch_ir"]),
        )

    def test_roundtrip_command_core_works_on_legacy_fixture(self):
        path = Path(self.temp.name) / "legacy.axp"
        path.write_text(LEGACY_AXP, encoding="utf-8")
        result = ksai.roundtrip_legacy_axp(path, self.catalog())
        self.assertTrue(result["ok"], result["diagnostics"])
        self.assertEqual("pass", result["evidence"]["semantic_roundtrip"])
        self.assertRegex(result["axp_sha256"], r"^[0-9a-f]{64}$")

    def test_typed_attributes_roundtrip_including_objref_and_multiline_text(self):
        imported = ksai.import_legacy_axp_bytes(
            LEGACY_ATTRIBUTES_AXP.encode("utf-8"), self.catalog(), "attributes"
        )
        self.assertTrue(imported["ok"], imported["diagnostics"])
        config = next(node for node in imported["patch_ir"]["nodes"] if node["id"] == "config")
        self.assertEqual("osc_1", config["attributes"]["target"])
        self.assertEqual("line one\nline two", config["attributes"]["script"])

        rendered = ksai.render_kpatch(imported["patch_ir"])
        self.assertIn("attr config.mode crunch", rendered)
        self.assertIn("attr config.script json:", rendered)
        reparsed = ksai.validate_patch_text(rendered, self.catalog())
        self.assertTrue(reparsed["ok"], reparsed["diagnostics"])
        emitted, emit_diagnostics = ksai.emit_legacy_axp(reparsed["patch_ir"], self.catalog())
        self.assertEqual([], emit_diagnostics)
        self.assertIsNotNone(emitted)
        self.assertEqual(
            (AI_DIR / "tests" / "fixtures" / "typed-attributes.axp").read_bytes(),
            emitted,
        )
        emitted_root = ET.fromstring(emitted)
        objref = emitted_root.find("./obj[@name='config']/attribs/objref")
        text = emitted_root.find("./obj[@name='config']/attribs/text/sText")
        self.assertEqual("osc~1", objref.attrib["obj"])
        self.assertEqual("line one\nline two", text.text)

        reimported = ksai.import_legacy_axp_bytes(emitted, self.catalog(), "attributes")
        self.assertTrue(reimported["ok"], reimported["diagnostics"])
        self.assertEqual(
            ksai.semantic_patch_signature(imported["patch_ir"]),
            ksai.semantic_patch_signature(reimported["patch_ir"]),
        )

    def test_attribute_choice_range_and_reference_fail_closed(self):
        path = self.write_patch(
            """\
kpatch 1
patch bad-attributes
target ksoloti-core@1.1.0
node config factory:attr/config@config-uuid
attr config.mode fuzzy
attr config.voices 99
attr config.target missing
"""
        )
        result = ksai.validate_patch(path, self.catalog())
        self.assertFalse(result["ok"])
        self.assertEqual(
            3,
            sum(item["code"] == "E_ATTR_VALUE" for item in result["diagnostics"]),
        )

    def test_legacy_sha_overload_is_resolved_only_by_graph_constraints(self):
        constrained = """\
<patch-1.0 appVersion="1.0.8">
  <obj type="osc/sine" uuid="osc-uuid" name="osc" x="14" y="14"><params/><attribs/></obj>
  <obj type="mix/mix" sha="mix-old" name="mix" x="238" y="14"><params/><attribs/></obj>
  <obj type="audio/out stereo" uuid="out-uuid" name="out" x="462" y="14"><params/><attribs/></obj>
  <nets>
    <net><source obj="osc" outlet="wave"/><dest obj="mix" inlet="a"/></net>
    <net><source obj="mix" outlet="out"/><dest obj="out" inlet="left"/></net>
  </nets>
  <settings><subpatchmode>no</subpatchmode></settings>
</patch-1.0>
"""
        result = ksai.import_legacy_axp_bytes(
            constrained.encode("utf-8"), self.catalog(), "constrained"
        )
        self.assertTrue(result["ok"], result["diagnostics"])
        mix = next(node for node in result["patch_ir"]["nodes"] if node["id"] == "mix")
        self.assertEqual("factory:mix/mix@mix-buffer", mix["resolved_ref"])
        self.assertIn(
            "W_AXP_OVERLOAD_CONSTRAINED",
            {item["code"] for item in result["diagnostics"]},
        )

    def test_legacy_semantic_constructs_fail_closed(self):
        with_attribute = LEGACY_AXP.replace(
            "<attribs/>",
            '<attribs><combo attributeName="mode" selection="x"/></attribs>',
            1,
        )
        result = ksai.import_legacy_axp_bytes(
            with_attribute.encode("utf-8"), self.catalog(), "legacy"
        )
        self.assertFalse(result["ok"])
        self.assertIn("E_ATTR_UNKNOWN", {item["code"] for item in result["diagnostics"]})

        with_unknown_setting = LEGACY_AXP.replace(
            "</settings>", "<UnknownRuntime>2</UnknownRuntime></settings>"
        )
        result = ksai.import_legacy_axp_bytes(
            with_unknown_setting.encode("utf-8"), self.catalog(), "legacy"
        )
        self.assertFalse(result["ok"])
        self.assertIn("E_AXP_SETTINGS_UNSUPPORTED", {item["code"] for item in result["diagnostics"]})

    def test_parameter_metadata_presets_and_patch_settings_roundtrip(self):
        legacy = LEGACY_AXP.replace(
            '<frac32.s.map name="pitch" value="0"/>',
            '<frac32.s.map name="pitch" MidiCC="7" onParent="true" value="0">'
            '<presets><preset index="1"><f v="12.5"/></preset></presets>'
            '</frac32.s.map>',
        ).replace(
            "</settings>",
            "<MidiChannel>2</MidiChannel><NPresets>8</NPresets>"
            "<NPresetEntries>32</NPresetEntries></settings>",
        )
        imported = ksai.import_legacy_axp_bytes(
            legacy.encode("utf-8"), self.catalog(), "metadata"
        )
        self.assertTrue(imported["ok"], imported["diagnostics"])
        oscillator = imported["patch_ir"]["nodes"][0]
        self.assertEqual(
            {
                "midi_cc": 7,
                "on_parent": True,
                "presets": [{"index": 1, "kind": "f", "value": "12.5"}],
            },
            oscillator["parameter_metadata"]["pitch"],
        )
        self.assertEqual("2", imported["patch_ir"]["settings"]["MidiChannel"])

        rendered = ksai.render_kpatch(imported["patch_ir"])
        self.assertIn("setting MidiChannel 2", rendered)
        self.assertIn("parammeta osc_1.pitch midi_cc=7 on_parent=true", rendered)
        self.assertIn("preset osc_1.pitch 1 f 12.5", rendered)
        reparsed = ksai.validate_patch_text(rendered, self.catalog())
        self.assertTrue(reparsed["ok"], reparsed["diagnostics"])
        emitted, diagnostics = ksai.emit_legacy_axp(reparsed["patch_ir"], self.catalog())
        self.assertEqual([], diagnostics)
        reimported = ksai.import_legacy_axp_bytes(emitted, self.catalog(), "metadata")
        self.assertTrue(reimported["ok"], reimported["diagnostics"])
        self.assertEqual(
            ksai.semantic_patch_signature(imported["patch_ir"]),
            ksai.semantic_patch_signature(reimported["patch_ir"]),
        )

    def test_compile_protocol_finds_last_json_record(self):
        self.assertEqual(
            {"ok": True, "value": 2},
            ksai._last_json_object("loader log\n{not json}\n{\"ok\":true,\"value\":2}\n"),
        )

    def test_legacy_overload_without_known_identity_fails_closed(self):
        ambiguous = """\
<patch-1.0 appVersion="1.0.8">
  <obj type="mix/mix" sha="unrecognized" name="mix" x="14" y="14">
    <params/><attribs/>
  </obj>
  <nets/>
  <settings><subpatchmode>no</subpatchmode></settings>
</patch-1.0>
"""
        result = ksai.import_legacy_axp_bytes(
            ambiguous.encode("utf-8"), self.catalog(), "ambiguous"
        )
        self.assertFalse(result["ok"])
        self.assertIn("E_AXP_TYPE_AMBIGUOUS", {item["code"] for item in result["diagnostics"]})

    def test_parameter_values_must_be_legacy_numeric_literals(self):
        path = self.write_patch(
            """\
kpatch 1
patch units
target ksoloti-core@1.1.0
node osc factory:osc/sine@osc-uuid
param osc.pitch 440Hz
"""
        )
        result = ksai.validate_patch(path, self.catalog())
        self.assertFalse(result["ok"])
        self.assertIn("E_PARAM_VALUE", {item["code"] for item in result["diagnostics"]})

    def test_wrong_input_format_has_one_compact_diagnostic(self):
        result = ksai.validate_patch_text("<patch-1.0><nets/></patch-1.0>", self.catalog())
        self.assertFalse(result["ok"])
        self.assertEqual(["E_FORMAT"], [item["code"] for item in result["diagnostics"]])

    def test_legacy_emitter_rejects_non_110_target(self):
        path = self.write_patch(
            """\
kpatch 1
patch wrong-target
target future-core@2.0.0
node osc factory:osc/sine@osc-uuid
"""
        )
        validated = ksai.validate_patch(path, self.catalog())
        self.assertTrue(validated["ok"], validated["diagnostics"])
        output, diagnostics = ksai.emit_legacy_axp(validated["patch_ir"], self.catalog())
        self.assertIsNone(output)
        self.assertIn("E_AXP_TARGET", {item.code for item in diagnostics})


if __name__ == "__main__":
    unittest.main()
