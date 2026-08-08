#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic catalog, compact patch validator, and legacy AXP bridge."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import os
import re
import shlex
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCHEMA_VERSION = 1
NODE_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
LIBRARY_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
INTEGER_RE = re.compile(r"^[+-]?[0-9]+$")
NUMBER_RE = re.compile(
    r"^[+-]?(?:(?:[0-9]+(?:\.[0-9]*)?)|(?:\.[0-9]+))(?:[eE][+-]?[0-9]+)?$"
)
AXP_VERSION = "1.1.0"
AXP_TARGET = "ksoloti-core@1.1.0"
AXP_OBJECT_ATTRIBUTES = {"type", "uuid", "sha", "name", "x", "y"}
AXP_ENDPOINT_ATTRIBUTES = {
    "source": {"obj", "outlet"},
    "dest": {"obj", "inlet"},
}
ATTRIBUTE_VALUE_FIELDS = {
    "combo": "selection",
    "spinner": "value",
    "int": "value",
    "objref": "obj",
    "table": "table",
    "file": "file",
}
ATTRIBUTE_TYPES = set(ATTRIBUTE_VALUE_FIELDS) | {"text"}
AXP_SETTING_CONTRACTS = {
    "subpatchmode": (
        "enum",
        {"no", "normal", "normalBypass", "polyphonic", "polychannel", "polyexpression"},
    ),
    "MidiChannel": ("int", 1, 16),
    "HasMidiChannelSelector": ("bool",),
    "NPresets": ("int", 0, 255),
    "NPresetEntries": ("int", 0, 255),
    "NModulationSources": ("int", 0, 255),
    "NModulationTargetsPerSource": ("int", 0, 255),
    "Author": ("text",),
    "License": ("text",),
    "Attributions": ("text",),
    "Saturate": ("bool",),
    "MPENumberOfMemberChannels": ("int", 1, 15),
    "MPEZone": ("int", 0, 1),
}


class KSAIError(Exception):
    """Expected user-facing failure."""


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    message: str
    line: Optional[int] = None
    context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        return {key: value for key, value in result.items() if value is not None}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(parent: ET.Element, child_name: str) -> str:
    for child in parent:
        if _local_name(child.tag) == child_name:
            return (child.text or "").strip()
    return ""


def _section(parent: ET.Element, name: str) -> Optional[ET.Element]:
    for child in parent:
        if _local_name(child.tag) == name:
            return child
    return None


def _atoms(parent: ET.Element, section_name: str) -> List[Dict[str, str]]:
    section = _section(parent, section_name)
    if section is None:
        return []
    atoms: List[Dict[str, str]] = []
    for child in section:
        name = child.attrib.get("name", "").strip()
        if not name:
            continue
        atom = {"name": name, "type": _local_name(child.tag)}
        description = child.attrib.get("description", "").strip()
        if description:
            atom["description"] = description
        atoms.append(atom)
    return atoms


def _ordered_strings(parent: ET.Element, section_name: str) -> List[str]:
    section = _section(parent, section_name)
    if section is None:
        return []
    return [
        child.text or ""
        for child in section
        if _local_name(child.tag) == "string"
    ]


def _attribute_definitions(parent: ET.Element) -> List[Dict[str, Any]]:
    """Extract the typed attribute contract carried by an .axo definition."""
    section = _section(parent, "attribs")
    if section is None:
        return []
    definitions: List[Dict[str, Any]] = []
    for child in section:
        name = child.attrib.get("name", "").strip()
        if not name:
            continue
        definition: Dict[str, Any] = {
            "name": name,
            "type": _local_name(child.tag),
            "instance_type": _local_name(child.tag),
        }
        description = child.attrib.get("description", "").strip()
        if description:
            definition["description"] = description
        if definition["type"] == "combo":
            definition["choices"] = _ordered_strings(child, "MenuEntries")
            definition["c_values"] = _ordered_strings(child, "CEntries")
        elif definition["type"] in {"spinner", "int"}:
            for xml_name, output_name in (
                ("MinValue", "minimum"),
                ("MaxValue", "maximum"),
                ("DefaultValue", "default"),
            ):
                raw_value = child.attrib.get(xml_name, "")
                if INTEGER_RE.fullmatch(raw_value):
                    definition[output_name] = int(raw_value, 10)
        definitions.append(definition)
    return definitions


def _string_list(parent: ET.Element, section_name: str) -> List[str]:
    section = _section(parent, section_name)
    if section is None:
        return []
    return sorted(
        value
        for value in ((child.text or "").strip() for child in section)
        if value
    )


def _child_texts(parent: ET.Element, child_name: str) -> List[str]:
    return sorted(
        {
            (child.text or "").strip()
            for child in parent
            if _local_name(child.tag) == child_name and (child.text or "").strip()
        }
    )


def _parameter_instance_type(definition_type: str) -> str:
    """Map an .axo parameter definition tag to its serialized .axp tag."""
    for prefix in (
        "frac32.s.mapvsl",
        "frac32.u.mapvsl",
        "frac32.s.map",
        "frac32.u.map",
    ):
        if definition_type == prefix or definition_type.startswith(prefix + "."):
            return prefix
    if definition_type in {
        "int32",
        "int32.hradio",
        "int32.vradio",
        "int2x16",
        "bin8",
        "bin12",
        "bin16",
        "bin32",
        "bool32.tgl",
        "bool32.mom",
    }:
        return definition_type
    if definition_type in {"int32.mini", "int32.small"}:
        return "int32.small"
    return ""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_object_id(relative_file: Path, local_id: str) -> str:
    folder = relative_file.parent.as_posix()
    if folder == ".":
        return local_id
    return f"{folder}/{local_id}"


def _locate_objects_dir(path: Path) -> Tuple[Path, Path]:
    resolved = path.expanduser().resolve()
    if resolved.name == "objects" and resolved.is_dir():
        return resolved.parent, resolved
    objects_dir = resolved / "objects"
    if objects_dir.is_dir():
        return resolved, objects_dir
    raise KSAIError(f"library has no objects directory: {path}")


def parse_library_spec(spec: str) -> Tuple[str, Path]:
    if "=" not in spec:
        raise KSAIError(f"library must be NAME=PATH: {spec}")
    name, raw_path = spec.split("=", 1)
    name = name.strip()
    if not LIBRARY_NAME_RE.fullmatch(name):
        raise KSAIError(f"invalid library name: {name}")
    if not raw_path.strip():
        raise KSAIError(f"library path is empty: {name}")
    return name, Path(raw_path)


def _parse_object_file(
    library_name: str,
    library_root: Path,
    objects_dir: Path,
    path: Path,
) -> Tuple[List[Dict[str, Any]], List[Diagnostic]]:
    relative_object_file = path.relative_to(objects_dir)
    relative_source = path.relative_to(library_root).as_posix()
    raw = path.read_bytes()
    source_sha256 = _sha256(raw)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return [], [
            Diagnostic(
                "error",
                "E_AXO_XML",
                f"cannot parse {relative_source}: {exc}",
                context={"library": library_name, "source": relative_source},
            )
        ]

    objects: List[Dict[str, Any]] = []
    for element in root:
        if _local_name(element.tag) != "obj.normal":
            continue
        local_id = element.attrib.get("id", "").strip()
        if not local_id:
            continue
        canonical_id = _canonical_object_id(relative_object_file, local_id)
        legacy_uuid = element.attrib.get("uuid", "").strip()
        legacy_sha = element.attrib.get("sha", "").strip()
        legacy_hashes = sorted(
            {value for value in [legacy_sha, *_child_texts(element, "upgradeSha")] if value}
        )
        object_sha256 = _sha256(ET.tostring(element, encoding="utf-8"))
        variant_id = legacy_uuid or legacy_sha or object_sha256[:20]
        base_ref = f"{library_name}:{canonical_id}"
        ref = f"{base_ref}@{variant_id}"

        parameters = _atoms(element, "params")
        for parameter in parameters:
            parameter["instance_type"] = _parameter_instance_type(parameter["type"])

        code_names = {
            "code.declaration": "declaration",
            "code.init": "init",
            "code.dispose": "dispose",
            "code.krate": "control",
            "code.srate": "sample",
            "code.midihandler": "midi",
        }
        code_sections = sorted(
            output_name
            for child in element
            for tag_name, output_name in code_names.items()
            if _local_name(child.tag) == tag_name and (child.text or "").strip()
        )

        objects.append(
            {
                "ref": ref,
                "base_ref": base_ref,
                "library": library_name,
                "id": canonical_id,
                "legacy_uuid": legacy_uuid,
                "description": _text(element, "sDescription"),
                "author": _text(element, "author"),
                "license": _text(element, "license"),
                "source": {
                    "path": relative_source,
                    "sha256": source_sha256,
                    "object_sha256": object_sha256,
                    "legacy_sha": legacy_sha,
                    "legacy_hashes": legacy_hashes,
                },
                "inlets": _atoms(element, "inlets"),
                "outlets": _atoms(element, "outlets"),
                "parameters": parameters,
                "attributes": _attribute_definitions(element),
                "implementation": {
                    "code_sections": code_sections,
                    "includes": _string_list(element, "includes"),
                    "depends": _string_list(element, "depends"),
                },
            }
        )
    return objects, []


def build_catalog(libraries: Sequence[Tuple[str, Path]]) -> Tuple[Dict[str, Any], List[Diagnostic]]:
    if not libraries:
        raise KSAIError("at least one --library NAME=PATH is required")
    names = [name for name, _ in libraries]
    if len(names) != len(set(names)):
        raise KSAIError("library names must be unique")

    all_objects: List[Dict[str, Any]] = []
    diagnostics: List[Diagnostic] = []
    library_rows: List[Dict[str, Any]] = []
    seen_refs: Dict[str, str] = {}

    for name, requested_path in sorted(libraries, key=lambda item: item[0]):
        root, objects_dir = _locate_objects_dir(requested_path)
        library_objects: List[Dict[str, Any]] = []
        file_fingerprints: List[str] = []
        object_files = sorted(objects_dir.rglob("*.axo"), key=lambda item: item.as_posix())
        for path in object_files:
            relative_source = path.relative_to(root).as_posix()
            file_fingerprints.append(f"{relative_source}\0{_sha256(path.read_bytes())}")
            parsed, file_diagnostics = _parse_object_file(name, root, objects_dir, path)
            library_objects.extend(parsed)
            diagnostics.extend(file_diagnostics)

        for obj in library_objects:
            previous = seen_refs.get(obj["ref"])
            if previous is not None:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_DUPLICATE_OBJECT_REF",
                        f"duplicate object ref {obj['ref']}",
                        context={"first": previous, "second": obj["source"]["path"]},
                    )
                )
            else:
                seen_refs[obj["ref"]] = obj["source"]["path"]
        all_objects.extend(library_objects)
        library_rows.append(
            {
                "name": name,
                "object_count": len(library_objects),
                "content_sha256": _sha256("\n".join(file_fingerprints).encode("utf-8")),
            }
        )

    all_objects.sort(key=lambda obj: (obj["library"], obj["id"], obj["ref"]))
    catalog = {
        "schema_version": SCHEMA_VERSION,
        "source_format": "axo-1.x",
        "libraries": library_rows,
        "objects": all_objects,
    }
    return catalog, diagnostics


def _load_catalog(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise KSAIError(f"catalog does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise KSAIError(f"invalid catalog JSON: {exc}") from exc
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("objects"), list):
        raise KSAIError(f"unsupported or malformed catalog: {path}")
    return data


def _compact_atom(atom: Dict[str, Any]) -> str:
    return f"{atom.get('name', '')}:{atom.get('type', '')}"


def _compact_attribute_contract(attribute: Dict[str, Any]) -> Dict[str, Any]:
    contract = {"name": attribute.get("name", ""), "type": attribute.get("type", "")}
    if attribute.get("type") == "combo":
        contract["choices"] = list(attribute.get("choices", []))
    elif attribute.get("type") in {"spinner", "int"}:
        for field in ("minimum", "maximum", "default"):
            if field in attribute:
                contract[field] = attribute[field]
    return contract


def search_catalog(catalog: Dict[str, Any], query: str, limit: int) -> Dict[str, Any]:
    words = [word for word in query.lower().split() if word]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for obj in catalog["objects"]:
        grouped.setdefault(obj["base_ref"], []).append(obj)

    ranked: List[Tuple[int, str, List[Dict[str, Any]]]] = []
    for base_ref, variants in grouped.items():
        first = variants[0]
        haystack = " ".join(
            [base_ref, first.get("id", ""), first.get("description", ""), first.get("author", "")]
        ).lower()
        if words and not all(word in haystack for word in words):
            continue
        score = 0
        query_lower = query.lower().strip()
        if query_lower and query_lower == first.get("id", "").lower():
            score += 1000
        if query_lower and query_lower in base_ref.lower():
            score += 300
        score += sum(50 if word in first.get("id", "").lower() else 10 for word in words)
        ranked.append((score, base_ref, variants))

    ranked.sort(key=lambda row: (-row[0], row[1]))
    matches: List[Dict[str, Any]] = []
    for _, base_ref, variants in ranked[:limit]:
        first = variants[0]
        matches.append(
            {
                "object": base_ref,
                "description": first.get("description", ""),
                "license": first.get("license", ""),
                "variant_count": len(variants),
                "variants": [
                    {
                        "ref": variant["ref"],
                        "in": [_compact_atom(atom) for atom in variant.get("inlets", [])],
                        "out": [_compact_atom(atom) for atom in variant.get("outlets", [])],
                        "params": [_compact_atom(atom) for atom in variant.get("parameters", [])],
                        "attrs": [
                            _compact_attribute_contract(attribute)
                            for attribute in variant.get("attributes", [])
                        ],
                    }
                    for variant in variants
                ],
            }
        )
    return {"schema_version": SCHEMA_VERSION, "query": query, "matches": matches}


def inspect_catalog(catalog: Dict[str, Any], requested: str) -> Dict[str, Any]:
    matches = [
        item
        for item in catalog["objects"]
        if requested in {item["ref"], item["base_ref"], item["id"]}
    ]
    if not matches:
        references = sorted({item["base_ref"] for item in catalog["objects"]})
        return {
            "ok": False,
            "object": requested,
            "diagnostics": [
                Diagnostic(
                    "error",
                    "E_OBJECT_NOT_FOUND",
                    f"object not found: {requested}",
                    context={
                        "suggestions": difflib.get_close_matches(
                            requested, references, n=5, cutoff=0.35
                        )
                    },
                ).to_dict()
            ],
        }
    variants = []
    for item in sorted(matches, key=lambda candidate: candidate["ref"]):
        variants.append(
            {
                "ref": item["ref"],
                "description": item["description"],
                "author": item["author"],
                "license": item["license"],
                "inlets": item["inlets"],
                "outlets": item["outlets"],
                "parameters": item["parameters"],
                "attributes": item["attributes"],
                "source": item["source"],
                "implementation": item["implementation"],
            }
        )
    return {
        "ok": True,
        "object": requested,
        "variant_count": len(variants),
        "variants": variants,
    }


def explain_validated_patch(result: Dict[str, Any], catalog: Dict[str, Any]) -> Dict[str, Any]:
    response: Dict[str, Any] = {
        "ok": result["ok"],
        "evidence": result["evidence"],
        "diagnostics": result["diagnostics"],
    }
    if not result["ok"]:
        return response
    by_ref = {item["ref"]: item for item in catalog["objects"]}
    ir = result["patch_ir"]
    fanout: Dict[str, int] = {}
    for edge in ir["edges"]:
        fanout[edge["from"]] = fanout.get(edge["from"], 0) + 1
    response["patch"] = {
        "id": ir["patch"]["id"],
        "target": ir["patch"]["target"],
        "settings": ir.get("settings", {}),
        "node_count": len(ir["nodes"]),
        "edge_count": len(ir["edges"]),
        "assertions": ir["assertions"],
    }
    response["nodes"] = [
        {
            "id": node["id"],
            "object": node["resolved_ref"],
            "description": by_ref[node["resolved_ref"]]["description"],
            "parameters": node["parameters"],
            "attributes": node["attributes"],
            "outgoing_edges": sum(
                count
                for endpoint, count in fanout.items()
                if endpoint.startswith(node["id"] + ".")
            ),
        }
        for node in ir["nodes"]
    ]
    response["connections"] = ir["edges"]
    return response


def diff_validated_patches(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    if not before["ok"] or not after["ok"]:
        return {
            "ok": False,
            "before_ok": before["ok"],
            "after_ok": after["ok"],
            "diagnostics": before["diagnostics"] + after["diagnostics"],
        }
    left = before["patch_ir"]
    right = after["patch_ir"]
    left_nodes = {node["id"]: node for node in left["nodes"]}
    right_nodes = {node["id"]: node for node in right["nodes"]}
    changed = [
        {"id": node_id, "before": left_nodes[node_id], "after": right_nodes[node_id]}
        for node_id in sorted(set(left_nodes) & set(right_nodes))
        if left_nodes[node_id] != right_nodes[node_id]
    ]
    left_edges = {(edge["from"], edge["to"]) for edge in left["edges"]}
    right_edges = {(edge["from"], edge["to"]) for edge in right["edges"]}
    return {
        "ok": True,
        "equal": semantic_patch_signature(left) == semantic_patch_signature(right)
        and left["assertions"] == right["assertions"],
        "nodes": {
            "added": sorted(set(right_nodes) - set(left_nodes)),
            "removed": sorted(set(left_nodes) - set(right_nodes)),
            "changed": changed,
        },
        "edges": {
            "added": [
                {"from": source, "to": destination}
                for source, destination in sorted(right_edges - left_edges)
            ],
            "removed": [
                {"from": source, "to": destination}
                for source, destination in sorted(left_edges - right_edges)
            ],
        },
        "settings_changed": left.get("settings", {}) != right.get("settings", {}),
        "assertions_changed": left["assertions"] != right["assertions"],
    }


def repair_plan(result: Dict[str, Any]) -> Dict[str, Any]:
    repairs = []
    for diagnostic in result["diagnostics"]:
        suggestions = diagnostic.get("context", {}).get("suggestions", [])
        if suggestions:
            repairs.append(
                {
                    "diagnostic": diagnostic["code"],
                    "action": "replace_reference",
                    "candidates": suggestions,
                    "automatic": len(suggestions) == 1,
                }
            )
        elif diagnostic["code"] in {"E_EDGE_SOURCE_PORT", "E_EDGE_DEST_PORT"}:
            repairs.append(
                {
                    "diagnostic": diagnostic["code"],
                    "action": "choose_declared_port",
                    "candidates": diagnostic.get("context", {}).get("available", []),
                    "automatic": False,
                }
            )
    return {
        "ok": result["ok"],
        "changed": False,
        "repairs": repairs,
        "diagnostics": result["diagnostics"],
    }


def _endpoint(
    value: str,
    line: Optional[int],
    diagnostics: List[Diagnostic],
) -> Optional[Tuple[str, str]]:
    if "." not in value:
        diagnostics.append(
            Diagnostic("error", "E_ENDPOINT", f"endpoint must be NODE.PORT: {value}", line)
        )
        return None
    node, port = value.rsplit(".", 1)
    if not NODE_ID_RE.fullmatch(node) or not port:
        diagnostics.append(Diagnostic("error", "E_ENDPOINT", f"invalid endpoint: {value}", line))
        return None
    return node, port


def _decode_attribute_value(
    tokens: Sequence[str],
    line_number: int,
    diagnostics: List[Diagnostic],
) -> Optional[str]:
    value = " ".join(tokens)
    if not value.startswith("json:"):
        return value
    try:
        decoded = json.loads(value[5:])
    except json.JSONDecodeError as exc:
        diagnostics.append(
            Diagnostic(
                "error",
                "E_ATTR_ENCODING",
                f"invalid json: attribute value: {exc.msg}",
                line_number,
            )
        )
        return None
    if not isinstance(decoded, str):
        diagnostics.append(
            Diagnostic(
                "error",
                "E_ATTR_ENCODING",
                "json: attribute values must decode to a string",
                line_number,
            )
        )
        return None
    return decoded


def parse_patch_text(text: str) -> Tuple[Dict[str, Any], Dict[str, Any], List[Diagnostic]]:
    lines = text.splitlines()

    diagnostics: List[Diagnostic] = []
    version: Optional[str] = None
    patch_id: Optional[str] = None
    target: Optional[str] = None
    nodes: List[Dict[str, Any]] = []
    parameter_ops: List[Tuple[str, str, str, int]] = []
    parameter_metadata_ops: List[Tuple[str, str, List[str], int]] = []
    preset_ops: List[Tuple[str, str, str, str, str, int]] = []
    modulation_ops: List[Tuple[str, str, str, str, str, int]] = []
    attribute_ops: List[Tuple[str, str, str, int]] = []
    edges: List[Dict[str, Any]] = []
    assertions: Dict[str, str] = {}
    settings: Dict[str, str] = {}

    first_character = text.lstrip()[:1]
    if first_character in {"<", "{"}:
        found = "legacy XML" if first_character == "<" else "JSON"
        ir = {
            "schema_version": SCHEMA_VERSION,
            "patch": {"id": "", "target": ""},
            "settings": {},
            "nodes": [],
            "edges": [],
            "assertions": {},
        }
        return (
            ir,
            {"node_map": {}},
            [
                Diagnostic(
                    "error",
                    "E_FORMAT",
                    f"expected kpatch source, found {found}; use the matching import command",
                )
            ],
        )

    for line_number, raw_line in enumerate(lines, 1):
        try:
            tokens = shlex.split(raw_line, comments=True, posix=True)
        except ValueError as exc:
            diagnostics.append(Diagnostic("error", "E_QUOTING", str(exc), line_number))
            continue
        if not tokens:
            continue
        directive = tokens[0]

        if directive == "kpatch":
            if len(tokens) != 2:
                diagnostics.append(Diagnostic("error", "E_KPATCH", "expected: kpatch VERSION", line_number))
            elif version is not None:
                diagnostics.append(Diagnostic("error", "E_KPATCH_DUP", "duplicate kpatch directive", line_number))
            else:
                version = tokens[1]
        elif directive == "patch":
            if len(tokens) != 2:
                diagnostics.append(Diagnostic("error", "E_PATCH", "expected: patch ID", line_number))
            elif patch_id is not None:
                diagnostics.append(Diagnostic("error", "E_PATCH_DUP", "duplicate patch directive", line_number))
            else:
                patch_id = tokens[1]
        elif directive == "target":
            if len(tokens) != 2:
                diagnostics.append(Diagnostic("error", "E_TARGET", "expected: target ID", line_number))
            elif target is not None:
                diagnostics.append(Diagnostic("error", "E_TARGET_DUP", "duplicate target directive", line_number))
            else:
                target = tokens[1]
        elif directive == "node":
            if len(tokens) not in {3, 4}:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_NODE",
                        "expected: node ID OBJECT_REF [LEGACY_INSTANCE_NAME]",
                        line_number,
                    )
                )
            else:
                nodes.append(
                    {
                        "id": tokens[1],
                        "name": tokens[3] if len(tokens) == 4 else tokens[1],
                        "object": tokens[2],
                        "parameters": {},
                        "parameter_metadata": {},
                        "attributes": {},
                        "_line": line_number,
                    }
                )
        elif directive == "param":
            if len(tokens) < 3:
                diagnostics.append(Diagnostic("error", "E_PARAM", "expected: param NODE.PARAM VALUE", line_number))
            else:
                parsed = _endpoint(tokens[1], line_number, diagnostics)
                if parsed is not None:
                    parameter_ops.append((parsed[0], parsed[1], " ".join(tokens[2:]), line_number))
        elif directive == "parammeta":
            if len(tokens) < 3:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_PARAMMETA",
                        "expected: parammeta NODE.PARAM KEY=VALUE [...]",
                        line_number,
                    )
                )
            else:
                parsed = _endpoint(tokens[1], line_number, diagnostics)
                if parsed is not None:
                    parameter_metadata_ops.append(
                        (parsed[0], parsed[1], tokens[2:], line_number)
                    )
        elif directive == "preset":
            if len(tokens) != 5:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_PRESET",
                        "expected: preset NODE.PARAM INDEX i|f VALUE",
                        line_number,
                    )
                )
            else:
                parsed = _endpoint(tokens[1], line_number, diagnostics)
                if parsed is not None:
                    preset_ops.append(
                        (parsed[0], parsed[1], tokens[2], tokens[3], tokens[4], line_number)
                    )
        elif directive == "modulate":
            if len(tokens) != 5:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_MODULATION",
                        "expected: modulate NODE.PARAM SOURCE MODULATOR|- VALUE",
                        line_number,
                    )
                )
            else:
                parsed = _endpoint(tokens[1], line_number, diagnostics)
                if parsed is not None:
                    modulation_ops.append(
                        (parsed[0], parsed[1], tokens[2], tokens[3], tokens[4], line_number)
                    )
        elif directive == "attr":
            if len(tokens) < 3:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_ATTR",
                        "expected: attr NODE.ATTRIBUTE VALUE",
                        line_number,
                    )
                )
            else:
                parsed = _endpoint(tokens[1], line_number, diagnostics)
                value = _decode_attribute_value(tokens[2:], line_number, diagnostics)
                if parsed is not None and value is not None:
                    attribute_ops.append((parsed[0], parsed[1], value, line_number))
        elif directive == "connect":
            if len(tokens) < 4 or tokens[2] != "->":
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_CONNECT",
                        "expected: connect NODE.PORT -> NODE.PORT[,NODE.PORT]",
                        line_number,
                    )
                )
            else:
                source = tokens[1]
                destinations = [item for item in "".join(tokens[3:]).split(",") if item]
                if not destinations:
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "E_CONNECT_DEST",
                            "connection has no destination",
                            line_number,
                        )
                    )
                for destination in destinations:
                    edges.append({"from": source, "to": destination, "_line": line_number})
        elif directive == "assert":
            if len(tokens) == 2 and "=" in tokens[1]:
                key, value = tokens[1].split("=", 1)
            elif len(tokens) == 3:
                key, value = tokens[1], tokens[2]
            else:
                diagnostics.append(Diagnostic("error", "E_ASSERT", "expected: assert NAME=VALUE", line_number))
                continue
            if not key or not value:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_ASSERT",
                        "assertion name and value are required",
                        line_number,
                    )
                )
            elif key in assertions:
                diagnostics.append(Diagnostic("error", "E_ASSERT_DUP", f"duplicate assertion: {key}", line_number))
            else:
                assertions[key] = value
        elif directive == "setting":
            if len(tokens) < 3:
                diagnostics.append(
                    Diagnostic(
                        "error", "E_SETTING", "expected: setting NAME VALUE", line_number
                    )
                )
            elif tokens[1] in settings:
                diagnostics.append(
                    Diagnostic(
                        "error", "E_SETTING_DUP", f"duplicate setting: {tokens[1]}", line_number
                    )
                )
            else:
                settings[tokens[1]] = " ".join(tokens[2:])
        else:
            diagnostics.append(Diagnostic("error", "E_DIRECTIVE", f"unknown directive: {directive}", line_number))

    if version is None:
        diagnostics.append(Diagnostic("error", "E_KPATCH_MISSING", "missing kpatch directive"))
    elif version != str(SCHEMA_VERSION):
        diagnostics.append(Diagnostic("error", "E_KPATCH_VERSION", f"unsupported kpatch version: {version}"))
    if not patch_id:
        diagnostics.append(Diagnostic("error", "E_PATCH_MISSING", "missing patch directive"))
    if not target:
        diagnostics.append(Diagnostic("error", "E_TARGET_MISSING", "missing target directive"))

    node_map: Dict[str, Dict[str, Any]] = {}
    instance_names: Dict[str, str] = {}
    for node in nodes:
        node_id = node["id"]
        if not NODE_ID_RE.fullmatch(node_id):
            diagnostics.append(Diagnostic("error", "E_NODE_ID", f"invalid node ID: {node_id}", node["_line"]))
        if node_id in node_map:
            diagnostics.append(Diagnostic("error", "E_NODE_DUP", f"duplicate node ID: {node_id}", node["_line"]))
        else:
            node_map[node_id] = node
        instance_name = node["name"]
        if not instance_name:
            diagnostics.append(Diagnostic("error", "E_NODE_NAME", "instance name cannot be empty", node["_line"]))
        elif instance_name in instance_names:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_NODE_NAME_DUP",
                    f"duplicate legacy instance name: {instance_name}",
                    node["_line"],
                    {"first_node": instance_names[instance_name], "second_node": node_id},
                )
            )
        else:
            instance_names[instance_name] = node_id

    seen_parameters: set[Tuple[str, str]] = set()
    for node_id, parameter, value, line_number in parameter_ops:
        node = node_map.get(node_id)
        if node is None:
            diagnostics.append(Diagnostic("error", "E_PARAM_NODE", f"unknown parameter node: {node_id}", line_number))
            continue
        key = (node_id, parameter)
        if key in seen_parameters:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_PARAM_DUP",
                    f"duplicate parameter assignment: {node_id}.{parameter}",
                    line_number,
                )
            )
            continue
        seen_parameters.add(key)
        node["parameters"][parameter] = value

    for node_id, parameter, entries, line_number in parameter_metadata_ops:
        node = node_map.get(node_id)
        if node is None:
            diagnostics.append(
                Diagnostic("error", "E_PARAMMETA_NODE", f"unknown parameter node: {node_id}", line_number)
            )
            continue
        metadata_value = node["parameter_metadata"].setdefault(parameter, {})
        for entry in entries:
            if "=" not in entry:
                diagnostics.append(
                    Diagnostic("error", "E_PARAMMETA", f"expected KEY=VALUE: {entry}", line_number)
                )
                continue
            key, value = entry.split("=", 1)
            if key in metadata_value:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_PARAMMETA_DUP",
                        f"duplicate parameter metadata: {node_id}.{parameter}.{key}",
                        line_number,
                    )
                )
            else:
                metadata_value[key] = [] if key == "presets" and value == "true" else value

    for node_id, parameter, index, kind, value, line_number in preset_ops:
        node = node_map.get(node_id)
        if node is None:
            diagnostics.append(
                Diagnostic("error", "E_PRESET_NODE", f"unknown parameter node: {node_id}", line_number)
            )
            continue
        metadata_value = node["parameter_metadata"].setdefault(parameter, {})
        metadata_value.setdefault("presets", []).append(
            {"index": index, "kind": kind, "value": value, "_line": line_number}
        )

    for node_id, parameter, source, modulator, value, line_number in modulation_ops:
        node = node_map.get(node_id)
        if node is None:
            diagnostics.append(
                Diagnostic("error", "E_MODULATION_NODE", f"unknown parameter node: {node_id}", line_number)
            )
            continue
        metadata_value = node["parameter_metadata"].setdefault(parameter, {})
        metadata_value.setdefault("modulations", []).append(
            {
                "source": source,
                "modulator": "" if modulator == "-" else modulator,
                "value": value,
                "_line": line_number,
            }
        )

    seen_attributes: set[Tuple[str, str]] = set()
    for node_id, attribute, value, line_number in attribute_ops:
        node = node_map.get(node_id)
        if node is None:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_ATTR_NODE",
                    f"unknown attribute node: {node_id}",
                    line_number,
                )
            )
            continue
        key = (node_id, attribute)
        if key in seen_attributes:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_ATTR_DUP",
                    f"duplicate attribute assignment: {node_id}.{attribute}",
                    line_number,
                )
            )
            continue
        seen_attributes.add(key)
        node["attributes"][attribute] = value

    ir = {
        "schema_version": SCHEMA_VERSION,
        "patch": {"id": patch_id or "", "target": target or ""},
        "settings": settings,
        "nodes": nodes,
        "edges": edges,
        "assertions": assertions,
    }
    metadata = {"node_map": node_map}
    return ir, metadata, diagnostics


def parse_patch(path: Path) -> Tuple[Dict[str, Any], Dict[str, Any], List[Diagnostic]]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise KSAIError(f"patch does not exist: {path}") from exc
    return parse_patch_text(text)


def _data_family(type_name: str) -> str:
    for prefix in ("frac32buffer", "frac32", "int32", "bool32", "charptr32"):
        if type_name == prefix or type_name.startswith(prefix + "."):
            return prefix
    return type_name


def _convertible(source_type: str, destination_type: str) -> bool:
    source = _data_family(source_type)
    destination = _data_family(destination_type)
    conversions = {
        "frac32buffer": {"frac32buffer", "frac32", "int32", "bool32"},
        "frac32": {"frac32", "int32", "bool32"},
        "int32": {"int32", "frac32", "bool32"},
        "bool32": {"bool32", "int32", "frac32"},
        "charptr32": {"charptr32"},
    }
    return destination in conversions.get(source, {source})


def _find_atom(atoms: Iterable[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    for atom in atoms:
        if atom.get("name") == name:
            return atom
    return None


def _normalize_parameter_value(
    definition: Dict[str, Any],
    raw_value: str,
) -> Tuple[Optional[str], Optional[str]]:
    instance_type = definition.get("instance_type") or _parameter_instance_type(
        definition.get("type", "")
    )
    if not instance_type:
        return None, f"unsupported legacy parameter type: {definition.get('type', '')}"

    value = raw_value.strip()
    if instance_type.startswith("frac32."):
        if not NUMBER_RE.fullmatch(value):
            return None, f"fractional parameter requires a numeric literal: {raw_value}"
        parsed = float(value)
        if not math.isfinite(parsed):
            return None, f"fractional parameter must be finite: {raw_value}"
        if parsed == 0.0:
            return "0.0", None
        return repr(parsed), None

    if not INTEGER_RE.fullmatch(value):
        return None, f"integer parameter requires an integer literal: {raw_value}"
    parsed_int = int(value, 10)
    if not -(2**31) <= parsed_int <= 2**31 - 1:
        return None, f"integer parameter is outside the signed 32-bit range: {raw_value}"
    if instance_type in {"bool32.tgl", "bool32.mom"} and parsed_int not in {0, 1}:
        return None, f"boolean parameter must be 0 or 1: {raw_value}"
    return str(parsed_int), None


def _normalize_attribute_value(
    definition: Dict[str, Any],
    raw_value: str,
    known_nodes: Optional[set[str]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    attribute_type = definition.get("instance_type") or definition.get("type", "")
    if attribute_type not in ATTRIBUTE_TYPES:
        return None, f"unsupported legacy attribute type: {attribute_type}"
    if not all(
        character in "\t\n\r"
        or 0x20 <= ord(character) <= 0xD7FF
        or 0xE000 <= ord(character) <= 0xFFFD
        or 0x10000 <= ord(character) <= 0x10FFFF
        for character in raw_value
    ):
        return None, "value contains a character forbidden by XML 1.0"

    if attribute_type == "combo":
        choices = definition.get("choices", [])
        if raw_value not in choices:
            return None, f"selection is not one of the declared choices: {raw_value}"
        return raw_value, None

    if attribute_type in {"spinner", "int"}:
        if not INTEGER_RE.fullmatch(raw_value):
            return None, f"{attribute_type} attribute requires an integer literal: {raw_value}"
        value = int(raw_value, 10)
        minimum = definition.get("minimum")
        maximum = definition.get("maximum")
        if not isinstance(minimum, int) or not isinstance(maximum, int):
            return None, f"{attribute_type} definition has no integer bounds"
        if value < minimum or value > maximum:
            return None, f"value {value} is outside the declared range {minimum}..{maximum}"
        return str(value), None

    if attribute_type == "objref":
        if not raw_value:
            return None, "object reference cannot be empty"
        if known_nodes is not None and raw_value not in known_nodes:
            return None, f"object reference names an unknown node: {raw_value}"
        return raw_value, None

    if attribute_type == "text":
        return raw_value.replace("\r\n", "\n").replace("\r", "\n"), None

    return raw_value, None


def _candidate_matches_node(node: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
    if node.get("_constrain_legacy_type") and candidate.get("id") != node.get("_legacy_type"):
        return False
    parameter_types = node.get("_parameter_types", {})
    for name, value in node.get("parameters", {}).items():
        definition = _find_atom(candidate.get("parameters", []), name)
        if definition is None:
            return False
        serialized_type = parameter_types.get(name)
        expected_type = definition.get("instance_type") or _parameter_instance_type(
            definition.get("type", "")
        )
        if serialized_type is not None and serialized_type != expected_type:
            return False
        if _normalize_parameter_value(definition, value)[1] is not None:
            return False

    attribute_types = node.get("_attribute_types", {})
    for name, value in node.get("attributes", {}).items():
        definition = _find_atom(candidate.get("attributes", []), name)
        if definition is None:
            return False
        serialized_type = attribute_types.get(name)
        expected_type = definition.get("instance_type") or definition.get("type", "")
        if serialized_type is not None and serialized_type != expected_type:
            return False
        if _normalize_attribute_value(definition, value)[1] is not None:
            return False
    return True


def _edge_parts(edge: Dict[str, Any]) -> Optional[Tuple[str, str, str, str]]:
    source = edge.get("from", "").rsplit(".", 1)
    destination = edge.get("to", "").rsplit(".", 1)
    if len(source) != 2 or len(destination) != 2:
        return None
    return source[0], source[1], destination[0], destination[1]


def _candidate_edge_compatible(
    source_object: Dict[str, Any],
    source_port: str,
    destination_object: Dict[str, Any],
    destination_port: str,
) -> bool:
    source_atom = _find_atom(source_object.get("outlets", []), source_port)
    destination_atom = _find_atom(destination_object.get("inlets", []), destination_port)
    return bool(
        source_atom is not None
        and destination_atom is not None
        and _convertible(source_atom["type"], destination_atom["type"])
    )


def _node_object_candidates(
    requested: str,
    catalog: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Optional[Diagnostic]]:
    by_ref = {obj["ref"]: obj for obj in catalog["objects"]}
    if requested in by_ref:
        return [by_ref[requested]], None
    if "@" in requested:
        suggestions = difflib.get_close_matches(requested, list(by_ref), n=5, cutoff=0.35)
        return [], Diagnostic(
            "error",
            "E_OBJECT_NOT_FOUND",
            f"object variant not found: {requested}",
            context={"suggestions": suggestions},
        )
    if ":" in requested:
        candidates = [obj for obj in catalog["objects"] if obj["base_ref"] == requested]
    else:
        candidates = [obj for obj in catalog["objects"] if obj["id"] == requested]
    if candidates:
        return sorted(candidates, key=lambda obj: obj["ref"]), None
    base_refs = sorted({obj["base_ref"] for obj in catalog["objects"]})
    return [], Diagnostic(
        "error",
        "E_OBJECT_NOT_FOUND",
        f"object not found: {requested}",
        context={"suggestions": difflib.get_close_matches(requested, base_refs, n=5, cutoff=0.35)},
    )


def _resolve_graph_overloads(
    ir: Dict[str, Any],
    diagnostics: List[Diagnostic],
    catalog: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Resolve only when explicit node and graph constraints yield one assignment."""
    domains: Dict[str, List[Dict[str, Any]]] = {}
    initially_ambiguous: set[str] = set()
    initial_candidate_counts: Dict[str, int] = {}
    nodes_by_id = {node["id"]: node for node in ir["nodes"]}

    for node in ir["nodes"]:
        if node.get("_resolution_failed"):
            continue
        fixed = node.get("_resolved_object")
        if fixed is not None:
            candidates = [fixed]
        elif "_candidate_objects" in node:
            candidates = sorted(node["_candidate_objects"], key=lambda obj: obj["ref"])
        else:
            candidates, diagnostic = _node_object_candidates(node["object"], catalog)
            if diagnostic is not None:
                diagnostics.append(
                    Diagnostic(
                        diagnostic.severity,
                        diagnostic.code,
                        diagnostic.message,
                        node.get("_line"),
                        diagnostic.context,
                    )
                )
                node["_resolution_failed"] = True
                continue
        if len(candidates) > 1:
            initially_ambiguous.add(node["id"])
            initial_candidate_counts[node["id"]] = len(candidates)
            candidates = [
                candidate
                for candidate in candidates
                if _candidate_matches_node(node, candidate)
            ]
        if not candidates:
            diagnostics.append(
                Diagnostic(
                    "error",
                    node.get("_constraint_code", "E_OBJECT_OVERLOAD_CONSTRAINT"),
                    f"no object variant satisfies the explicit constraints for {node['id']}",
                    node.get("_line"),
                    {"requested": node.get("object", "")},
                )
            )
            node["_resolution_failed"] = True
            continue
        domains[node["id"]] = candidates

    graph_edges: List[Tuple[str, str, str, str]] = []
    for edge in ir["edges"]:
        parts = _edge_parts(edge)
        if (
            parts is not None
            and parts[0] in domains
            and parts[2] in domains
            and (parts[0] in initially_ambiguous or parts[2] in initially_ambiguous)
        ):
            graph_edges.append(parts)

    changed = True
    while changed:
        changed = False
        for source_node, source_port, destination_node, destination_port in graph_edges:
            source_domain = domains[source_node]
            destination_domain = domains[destination_node]
            if source_node in initially_ambiguous:
                filtered_source = [
                    source_object
                    for source_object in source_domain
                    if any(
                        _candidate_edge_compatible(
                            source_object,
                            source_port,
                            destination_object,
                            destination_port,
                        )
                        for destination_object in destination_domain
                    )
                ]
                if len(filtered_source) != len(source_domain):
                    domains[source_node] = filtered_source
                    source_domain = filtered_source
                    changed = True
            if destination_node in initially_ambiguous:
                filtered_destination = [
                    destination_object
                    for destination_object in destination_domain
                    if any(
                        _candidate_edge_compatible(
                            source_object,
                            source_port,
                            destination_object,
                            destination_port,
                        )
                        for source_object in source_domain
                    )
                ]
                if len(filtered_destination) != len(destination_domain):
                    domains[destination_node] = filtered_destination
                    changed = True

    empty_nodes = [node_id for node_id, domain in domains.items() if not domain]
    for node_id in empty_nodes:
        node = nodes_by_id[node_id]
        diagnostics.append(
            Diagnostic(
                "error",
                node.get("_constraint_code", "E_OBJECT_OVERLOAD_CONSTRAINT"),
                f"graph constraints eliminate every object variant for {node_id}",
                node.get("_line"),
                {"requested": node.get("object", "")},
            )
        )
        node["_resolution_failed"] = True
        domains.pop(node_id)

    ambiguous_domains = {
        node_id: domain
        for node_id, domain in domains.items()
        if node_id in initially_ambiguous and len(domain) > 1
    }
    solutions: List[Dict[str, Dict[str, Any]]] = []
    search_steps = 0
    search_limited = False

    def compatible_partial(assignment: Dict[str, Dict[str, Any]]) -> bool:
        for source_node, source_port, destination_node, destination_port in graph_edges:
            source_object = assignment.get(source_node)
            destination_object = assignment.get(destination_node)
            if source_object is not None and destination_object is not None:
                if not _candidate_edge_compatible(
                    source_object, source_port, destination_object, destination_port
                ):
                    return False
            elif source_object is not None:
                if not any(
                    _candidate_edge_compatible(
                        source_object, source_port, candidate, destination_port
                    )
                    for candidate in domains[destination_node]
                ):
                    return False
            elif destination_object is not None:
                if not any(
                    _candidate_edge_compatible(
                        candidate, source_port, destination_object, destination_port
                    )
                    for candidate in domains[source_node]
                ):
                    return False
        return True

    def search(assignment: Dict[str, Dict[str, Any]]) -> None:
        nonlocal search_steps, search_limited
        if len(solutions) >= 2 or search_limited:
            return
        search_steps += 1
        if search_steps > 100000:
            search_limited = True
            return
        if len(assignment) == len(domains):
            solutions.append(dict(assignment))
            return
        remaining = [node_id for node_id in domains if node_id not in assignment]
        node_id = min(remaining, key=lambda item: (len(domains[item]), item))
        for candidate in domains[node_id]:
            assignment[node_id] = candidate
            if compatible_partial(assignment):
                search(assignment)
            assignment.pop(node_id)

    if ambiguous_domains:
        search(
            {
                node_id: domain[0]
                for node_id, domain in domains.items()
                if len(domain) == 1
            }
        )
    else:
        solutions = [{node_id: domain[0] for node_id, domain in domains.items()}]

    if search_limited:
        diagnostics.append(
            Diagnostic(
                "error",
                "E_OVERLOAD_SEARCH_LIMIT",
                "overload resolution exceeded the deterministic search bound",
                context={"steps": search_steps, "limit": 100000},
            )
        )
    elif not solutions and ambiguous_domains:
        diagnostics.append(
            Diagnostic(
                "error",
                "E_OVERLOAD_GRAPH_CONFLICT",
                "no complete overload assignment satisfies the graph",
                context={"nodes": sorted(ambiguous_domains)},
            )
        )

    resolved_nodes: Dict[str, Dict[str, Any]] = {}
    unique_solution = len(solutions) == 1 and not search_limited
    for node_id, domain in domains.items():
        node = nodes_by_id[node_id]
        if unique_solution:
            selected = solutions[0][node_id]
        elif len(domain) == 1:
            selected = domain[0]
        else:
            diagnostic_code = node.get("_ambiguity_code", "E_OBJECT_AMBIGUOUS")
            diagnostics.append(
                Diagnostic(
                    "error",
                    diagnostic_code,
                    f"explicit constraints leave {len(domain)} valid variants for {node_id}",
                    node.get("_line"),
                    {"choices": [candidate["ref"] for candidate in domain]},
                )
            )
            node["_resolution_failed"] = True
            continue
        node["_resolved_object"] = selected
        node["resolved_ref"] = selected["ref"]
        resolved_nodes[node_id] = selected
        if node_id in initially_ambiguous:
            diagnostics.append(
                Diagnostic(
                    "warning",
                    node.get("_constrained_warning", "W_OBJECT_OVERLOAD_CONSTRAINED"),
                    f"explicit node and graph constraints select {selected['ref']}",
                    node.get("_line"),
                    {
                        "node": node_id,
                        "selected": selected["ref"],
                        "candidate_count": initial_candidate_counts[node_id],
                    },
                )
            )
    return resolved_nodes


def _normalize_setting(name: str, value: str) -> Tuple[Optional[str], Optional[str]]:
    contract = AXP_SETTING_CONTRACTS.get(name)
    if contract is None:
        return None, f"unknown patch setting: {name}"
    kind = contract[0]
    if kind == "text":
        return value, None
    if kind == "bool":
        normalized = value.lower()
        if normalized not in {"true", "false"}:
            return None, "expected true or false"
        return normalized, None
    if kind == "enum":
        if value not in contract[1]:
            return None, f"expected one of: {', '.join(sorted(contract[1]))}"
        return value, None
    if not INTEGER_RE.fullmatch(value):
        return None, "expected an integer"
    numeric = int(value)
    if numeric < contract[1] or numeric > contract[2]:
        return None, f"expected {contract[1]}..{contract[2]}"
    return str(numeric), None


def _normalize_parameter_metadata(
    node: Dict[str, Any],
    parameter_definitions: Dict[str, Dict[str, Any]],
    known_nodes: set[str],
    diagnostics: List[Diagnostic],
) -> Dict[str, Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}
    for parameter, raw_metadata in node.get("parameter_metadata", {}).items():
        definition = parameter_definitions.get(parameter)
        if definition is None or parameter not in node.get("parameters", {}):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_PARAMMETA_PARAMETER",
                    f"metadata requires an assigned parameter: {node['id']}.{parameter}",
                    node.get("_line"),
                )
            )
            continue
        unknown = sorted(
            set(raw_metadata) - {"midi_cc", "on_parent", "presets", "modulations"}
        )
        if unknown:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_PARAMMETA_KEY",
                    f"unknown metadata on {node['id']}.{parameter}",
                    node.get("_line"),
                    {"keys": unknown},
                )
            )
        item: Dict[str, Any] = {}
        if "midi_cc" in raw_metadata:
            value = str(raw_metadata["midi_cc"])
            if not INTEGER_RE.fullmatch(value) or not 0 <= int(value) <= 127:
                diagnostics.append(
                    Diagnostic(
                        "error", "E_PARAMMETA_MIDI_CC", "midi_cc must be 0..127", node.get("_line")
                    )
                )
            else:
                item["midi_cc"] = int(value)
        if "on_parent" in raw_metadata:
            value = str(raw_metadata["on_parent"]).lower()
            if value not in {"true", "false"}:
                diagnostics.append(
                    Diagnostic(
                        "error", "E_PARAMMETA_ON_PARENT", "on_parent must be true or false", node.get("_line")
                    )
                )
            else:
                item["on_parent"] = value == "true"
        if "presets" in raw_metadata:
            presets = raw_metadata["presets"]
            if not isinstance(presets, list):
                diagnostics.append(
                    Diagnostic(
                        "error", "E_PRESET_ENCODING", "presets metadata must be a list", node.get("_line")
                    )
                )
            else:
                normalized_presets = []
                seen_indexes = set()
                instance_type = definition.get("instance_type", "")
                expected_kind = "f" if instance_type.startswith("frac32") else "i"
                for preset in presets:
                    line = preset.get("_line", node.get("_line"))
                    index = str(preset.get("index", ""))
                    kind = str(preset.get("kind", ""))
                    value = str(preset.get("value", ""))
                    if not INTEGER_RE.fullmatch(index) or not 1 <= int(index) <= 255:
                        diagnostics.append(
                            Diagnostic("error", "E_PRESET_INDEX", "preset index must be 1..255", line)
                        )
                        continue
                    if int(index) in seen_indexes:
                        diagnostics.append(
                            Diagnostic("error", "E_PRESET_DUP", f"duplicate preset index: {index}", line)
                        )
                        continue
                    seen_indexes.add(int(index))
                    if kind != expected_kind:
                        diagnostics.append(
                            Diagnostic(
                                "error",
                                "E_PRESET_KIND",
                                f"preset kind for {node['id']}.{parameter} must be {expected_kind}",
                                line,
                            )
                        )
                    if not NUMBER_RE.fullmatch(value):
                        diagnostics.append(
                            Diagnostic("error", "E_PRESET_VALUE", "preset value must be numeric", line)
                        )
                    normalized_presets.append(
                        {"index": int(index), "kind": kind, "value": value}
                    )
                item["presets"] = sorted(normalized_presets, key=lambda preset: preset["index"])
        if "modulations" in raw_metadata:
            modulations = raw_metadata["modulations"]
            if not isinstance(modulations, list):
                diagnostics.append(
                    Diagnostic(
                        "error", "E_MODULATION_ENCODING", "modulations metadata must be a list", node.get("_line")
                    )
                )
            else:
                normalized_modulations = []
                seen_modulations = set()
                for modulation in modulations:
                    line = modulation.get("_line", node.get("_line"))
                    source = str(modulation.get("source", ""))
                    modulator = str(modulation.get("modulator", ""))
                    value = str(modulation.get("value", ""))
                    if source not in known_nodes:
                        diagnostics.append(
                            Diagnostic(
                                "error", "E_MODULATION_SOURCE", f"unknown modulation source: {source}", line
                            )
                        )
                    if not NUMBER_RE.fullmatch(value):
                        diagnostics.append(
                            Diagnostic("error", "E_MODULATION_VALUE", "modulation value must be numeric", line)
                        )
                    key = (source, modulator)
                    if key in seen_modulations:
                        diagnostics.append(
                            Diagnostic(
                                "error", "E_MODULATION_DUP", f"duplicate modulation source: {source}", line
                            )
                        )
                        continue
                    seen_modulations.add(key)
                    normalized_modulations.append(
                        {"source": source, "modulator": modulator, "value": value}
                    )
                item["modulations"] = sorted(
                    normalized_modulations,
                    key=lambda modulation: (modulation["source"], modulation["modulator"]),
                )
        normalized[parameter] = item
    return dict(sorted(normalized.items()))


def _validate_ir(
    ir: Dict[str, Any],
    metadata: Dict[str, Any],
    diagnostics: List[Diagnostic],
    catalog: Dict[str, Any],
) -> Dict[str, Any]:
    parse_has_errors = any(item.severity == "error" for item in diagnostics)
    resolved_nodes = _resolve_graph_overloads(ir, diagnostics, catalog)
    known_nodes = set(metadata["node_map"])
    normalized_settings: Dict[str, str] = {}
    for name, value in ir.get("settings", {}).items():
        normalized, error = _normalize_setting(name, str(value))
        if error is not None:
            diagnostics.append(
                Diagnostic("error", "E_SETTING_VALUE", f"{name}: {error}")
            )
        else:
            assert normalized is not None
            normalized_settings[name] = normalized

    for node in ir["nodes"]:
        line_number = node.get("_line")
        if node.get("_resolution_failed"):
            continue
        resolved = resolved_nodes.get(node["id"])
        if resolved is None:
            continue
        assert resolved is not None
        node["resolved_ref"] = resolved["ref"]
        legacy_type = node.get("_legacy_type")
        if legacy_type and legacy_type != resolved.get("id"):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W_AXP_TYPE_MISMATCH",
                    f"legacy type name differs from the resolved catalog object: {legacy_type}",
                    line_number,
                    {"resolved_id": resolved.get("id", ""), "resolved_ref": resolved["ref"]},
                )
            )
        parameter_definitions = {
            item["name"]: item for item in resolved.get("parameters", [])
        }
        for parameter, value in list(node["parameters"].items()):
            definition = parameter_definitions.get(parameter)
            if definition is None:
                suggestions = difflib.get_close_matches(
                    parameter, sorted(parameter_definitions), n=3
                )
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_PARAM_UNKNOWN",
                        f"unknown parameter {node['id']}.{parameter}",
                        line_number,
                        {"suggestions": suggestions},
                    )
                )
                continue
            serialized_type = node.get("_parameter_types", {}).get(parameter)
            expected_type = definition.get("instance_type") or _parameter_instance_type(
                definition.get("type", "")
            )
            if serialized_type is not None and serialized_type != expected_type:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_AXP_PARAMETER_TYPE",
                        f"legacy parameter tag does not match the resolved object: {node['name']}.{parameter}",
                        line_number,
                        {"found": serialized_type, "expected": expected_type},
                    )
                )
            normalized_value, error = _normalize_parameter_value(definition, value)
            if error is not None:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_PARAM_VALUE",
                        f"{node['id']}.{parameter}: {error}",
                        line_number,
                        {
                            "definition_type": definition.get("type", ""),
                            "instance_type": definition.get("instance_type", ""),
                        },
                    )
                )
            else:
                assert normalized_value is not None
                node["parameters"][parameter] = normalized_value

        node["parameter_metadata"] = _normalize_parameter_metadata(
            node, parameter_definitions, known_nodes, diagnostics
        )

        attribute_definitions = {
            item["name"]: item for item in resolved.get("attributes", [])
        }
        for attribute, value in list(node.get("attributes", {}).items()):
            definition = attribute_definitions.get(attribute)
            if definition is None:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_ATTR_UNKNOWN",
                        f"unknown attribute {node['id']}.{attribute}",
                        line_number,
                        {
                            "suggestions": difflib.get_close_matches(
                                attribute, sorted(attribute_definitions), n=3
                            )
                        },
                    )
                )
                continue
            serialized_type = node.get("_attribute_types", {}).get(attribute)
            expected_type = definition.get("instance_type") or definition.get("type", "")
            if serialized_type is not None and serialized_type != expected_type:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_AXP_ATTRIBUTE_TYPE",
                        f"legacy attribute tag does not match the resolved object: {node['name']}.{attribute}",
                        line_number,
                        {"found": serialized_type, "expected": expected_type},
                    )
                )
            normalized_value, error = _normalize_attribute_value(
                definition, value, known_nodes
            )
            if error is not None:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_ATTR_VALUE",
                        f"{node['id']}.{attribute}: {error}",
                        line_number,
                        {"attribute_type": expected_type},
                    )
                )
            else:
                assert normalized_value is not None
                node["attributes"][attribute] = normalized_value

    catalog_error_codes = {
        "E_AXP_UUID_AMBIGUOUS",
        "E_AXP_SHA_AMBIGUOUS",
        "E_AXP_TYPE_AMBIGUOUS",
        "E_AXP_OVERLOAD_CONSTRAINT",
        "E_AXP_IDENTITY_CONFLICT",
        "E_AXP_OBJECT_NOT_FOUND",
        "E_OVERLOAD_GRAPH_CONFLICT",
        "E_OVERLOAD_SEARCH_LIMIT",
    }
    catalog_has_errors = any(
        item.severity == "error"
        and (
            item.code.startswith("E_OBJECT")
            or item.code.startswith("E_OVERLOAD")
            or item.code == "E_PARAM_UNKNOWN"
            or item.code in catalog_error_codes
        )
        for item in diagnostics
    )
    driven_inputs: Dict[str, str] = {}
    seen_edges: set[Tuple[str, str]] = set()
    for edge in ir["edges"]:
        line_number = edge.get("_line")
        source_endpoint = _endpoint(edge["from"], line_number, diagnostics)
        destination_endpoint = _endpoint(edge["to"], line_number, diagnostics)
        if source_endpoint is None or destination_endpoint is None:
            continue
        source_node, source_port = source_endpoint
        destination_node, destination_port = destination_endpoint
        if source_node not in metadata["node_map"]:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_EDGE_SOURCE_NODE",
                    f"unknown source node: {source_node}",
                    line_number,
                )
            )
            continue
        if destination_node not in metadata["node_map"]:
            diagnostics.append(
                Diagnostic("error", "E_EDGE_DEST_NODE", f"unknown destination node: {destination_node}", line_number)
            )
            continue
        source_object = resolved_nodes.get(source_node)
        destination_object = resolved_nodes.get(destination_node)
        if source_object is None or destination_object is None:
            continue
        source_atom = _find_atom(source_object.get("outlets", []), source_port)
        if source_atom is None:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_EDGE_SOURCE_PORT",
                    f"unknown outlet: {source_node}.{source_port}",
                    line_number,
                    {"available": [atom["name"] for atom in source_object.get("outlets", [])]},
                )
            )
            continue
        destination_atom = _find_atom(destination_object.get("inlets", []), destination_port)
        if destination_atom is None:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_EDGE_DEST_PORT",
                    f"unknown inlet: {destination_node}.{destination_port}",
                    line_number,
                    {"available": [atom["name"] for atom in destination_object.get("inlets", [])]},
                )
            )
            continue
        if not _convertible(source_atom["type"], destination_atom["type"]):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_EDGE_TYPE",
                    f"cannot connect {source_atom['type']} to {destination_atom['type']}",
                    line_number,
                    {"from": edge["from"], "to": edge["to"]},
                )
            )
        edge_key = (edge["from"], edge["to"])
        if edge_key in seen_edges:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_EDGE_DUP",
                    f"duplicate edge: {edge['from']} -> {edge['to']}",
                    line_number,
                )
            )
        seen_edges.add(edge_key)
        previous_source = driven_inputs.get(edge["to"])
        if previous_source is not None and previous_source != edge["from"]:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_MULTIPLE_DRIVERS",
                    f"inlet has multiple drivers: {edge['to']}",
                    line_number,
                    {"first": previous_source, "second": edge["from"]},
                )
            )
        else:
            driven_inputs[edge["to"]] = edge["from"]

    graph_has_errors = any(
        item.severity == "error"
        and (
            item.code.startswith("E_EDGE")
            or item.code.startswith("E_AXP_NET")
            or item.code in {"E_ENDPOINT", "E_MULTIPLE_DRIVERS", "E_OVERLOAD_GRAPH_CONFLICT"}
        )
        for item in diagnostics
    )
    parameter_has_errors = any(
        item.severity == "error"
        and (
            item.code.startswith("E_PARAM")
            or item.code.startswith("E_PRESET")
            or item.code.startswith("E_MODULATION")
            or item.code.startswith("E_AXP_PARAMETER")
        )
        for item in diagnostics
    )
    settings_have_errors = any(
        item.severity == "error"
        and (item.code.startswith("E_SETTING") or item.code.startswith("E_AXP_SETTING"))
        for item in diagnostics
    )
    attribute_has_errors = any(
        item.severity == "error"
        and (item.code.startswith("E_ATTR") or item.code.startswith("E_AXP_ATTRIBUTE"))
        for item in diagnostics
    )
    normalized_nodes = []
    for node in ir["nodes"]:
        normalized_nodes.append(
            {
                "id": node["id"],
                "name": node.get("name", node["id"]),
                "object": node["object"],
                "resolved_ref": node.get("resolved_ref", ""),
                "parameters": dict(sorted(node["parameters"].items())),
                "parameter_metadata": node.get("parameter_metadata", {}),
                "attributes": dict(sorted(node.get("attributes", {}).items())),
            }
        )
    normalized_edges = sorted(
        ({"from": edge["from"], "to": edge["to"]} for edge in ir["edges"]),
        key=lambda edge: (edge["from"], edge["to"]),
    )
    normalized_ir = {
        "schema_version": SCHEMA_VERSION,
        "patch": ir["patch"],
        "settings": dict(sorted(normalized_settings.items())),
        "nodes": normalized_nodes,
        "edges": normalized_edges,
        "assertions": dict(sorted(ir["assertions"].items())),
    }
    has_errors = any(item.severity == "error" for item in diagnostics)
    downstream_ran = not (parse_has_errors and not ir["nodes"] and not ir["edges"])
    return {
        "ok": not has_errors,
        "evidence": {
            "syntax": "fail" if parse_has_errors else "pass",
            "catalog_resolution": (
                "fail" if catalog_has_errors else "pass" if downstream_ran else "not_run"
            ),
            "parameter_values": (
                "fail" if parameter_has_errors else "pass" if downstream_ran else "not_run"
            ),
            "attribute_values": (
                "fail" if attribute_has_errors else "pass" if downstream_ran else "not_run"
            ),
            "patch_settings": (
                "fail" if settings_have_errors else "pass" if downstream_ran else "not_run"
            ),
            "graph_structure": (
                "fail" if graph_has_errors else "pass" if downstream_ran else "not_run"
            ),
            "declared_assertions": "not_run" if ir["assertions"] else "none",
            "legacy_generation": "not_run",
            "arm_compile_link": "not_run",
            "host_behavior": "not_run",
            "connected_board": "not_run",
            "audible": "not_run",
        },
        "diagnostics": [item.to_dict() for item in diagnostics],
        "patch_ir": normalized_ir,
    }


def validate_patch_text(text: str, catalog: Dict[str, Any]) -> Dict[str, Any]:
    ir, metadata, diagnostics = parse_patch_text(text)
    return _validate_ir(ir, metadata, diagnostics, catalog)


def validate_patch(path: Path, catalog: Dict[str, Any]) -> Dict[str, Any]:
    ir, metadata, diagnostics = parse_patch(path)
    return _validate_ir(ir, metadata, diagnostics, catalog)


def _safe_node_id(name: str, used: set[str]) -> str:
    if NODE_ID_RE.fullmatch(name):
        base = name
    else:
        base = re.sub(r"[^A-Za-z0-9_-]+", "_", name)
        base = re.sub(r"_+", "_", base)
        if not base:
            base = "node"
        if not re.match(r"^[A-Za-z_]", base):
            base = f"node_{base}"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _legacy_hashes(obj: Dict[str, Any]) -> set[str]:
    source = obj.get("source", {})
    values = set(source.get("legacy_hashes", []))
    legacy_sha = source.get("legacy_sha", "")
    if legacy_sha:
        values.add(legacy_sha)
    return values


def _legacy_object_candidates(
    type_name: str,
    legacy_uuid: str,
    legacy_sha: str,
    catalog: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Diagnostic], Optional[str]]:
    diagnostics: List[Diagnostic] = []
    objects = catalog["objects"]
    uuid_matches = sorted(
        (
            [obj for obj in objects if obj.get("legacy_uuid") == legacy_uuid]
            if legacy_uuid
            else []
        ),
        key=lambda obj: obj["ref"],
    )
    sha_matches = sorted(
        (
            [obj for obj in objects if legacy_sha in _legacy_hashes(obj)]
            if legacy_sha
            else []
        ),
        key=lambda obj: obj["ref"],
    )

    if len(uuid_matches) > 1:
        diagnostics.append(
            Diagnostic(
                "error",
                "E_AXP_UUID_AMBIGUOUS",
                f"legacy UUID resolves to {len(uuid_matches)} catalog variants: {legacy_uuid}",
                context={"choices": sorted(obj["ref"] for obj in uuid_matches)},
            )
        )
        return [], diagnostics, None

    uuid_object = uuid_matches[0] if uuid_matches else None
    sha_object = sha_matches[0] if len(sha_matches) == 1 else None
    if uuid_object is not None and sha_object is not None and uuid_object["ref"] != sha_object["ref"]:
        diagnostics.append(
            Diagnostic(
                "error",
                "E_AXP_IDENTITY_CONFLICT",
                "legacy UUID and SHA resolve to different object variants",
                context={"uuid_ref": uuid_object["ref"], "sha_ref": sha_object["ref"]},
            )
        )
        return [], diagnostics, None

    if uuid_object is not None and len(sha_matches) > 1:
        diagnostics.append(
            Diagnostic(
                "warning",
                "W_AXP_SHA_AMBIGUOUS_IGNORED",
                "legacy SHA is ambiguous; the exact UUID remains authoritative",
                context={"uuid_ref": uuid_object["ref"], "sha": legacy_sha},
            )
        )
        return [uuid_object], diagnostics, None

    if uuid_object is not None:
        if legacy_sha and not sha_matches:
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "W_AXP_SHA_UNRECOGNIZED",
                    f"legacy SHA was not recognized; exact UUID remains authoritative: {legacy_sha}",
                    context={"resolved_ref": uuid_object["ref"]},
                )
            )
        return [uuid_object], diagnostics, None

    if legacy_uuid:
        diagnostics.append(
            Diagnostic(
                "warning",
                "W_AXP_UUID_UNRECOGNIZED",
                f"legacy UUID was not recognized; constrained fallback is required: {legacy_uuid}",
            )
        )

    if sha_object is not None:
        return [sha_object], diagnostics, None
    if len(sha_matches) > 1:
        return sha_matches, diagnostics, "E_AXP_SHA_AMBIGUOUS"

    if legacy_sha:
        diagnostics.append(
            Diagnostic(
                "warning",
                "W_AXP_SHA_UNRECOGNIZED",
                f"legacy SHA was not recognized; constrained type fallback is required: {legacy_sha}",
            )
        )

    type_matches = sorted(
        [obj for obj in objects if obj.get("id") == type_name],
        key=lambda obj: obj["ref"],
    )
    if type_matches:
        ambiguity_code = "E_AXP_TYPE_AMBIGUOUS" if len(type_matches) > 1 else None
        return type_matches, diagnostics, ambiguity_code

    diagnostics.append(
        Diagnostic(
            "error",
            "E_AXP_OBJECT_NOT_FOUND",
            f"legacy object cannot be resolved: {type_name}",
            context={"uuid": legacy_uuid, "sha": legacy_sha},
        )
    )
    return [], diagnostics, None


def _axp_error_result(
    patch_id: str,
    target: str,
    diagnostics: List[Diagnostic],
) -> Dict[str, Any]:
    empty_ir = {
        "schema_version": SCHEMA_VERSION,
        "patch": {"id": patch_id, "target": target},
        "nodes": [],
        "edges": [],
        "assertions": {},
    }
    result = _validate_ir(empty_ir, {"node_map": {}}, diagnostics, {"objects": []})
    result["evidence"]["legacy_import"] = "fail"
    return result


def import_legacy_axp_bytes(
    data: bytes,
    catalog: Dict[str, Any],
    patch_id: str,
    target: str = AXP_TARGET,
) -> Dict[str, Any]:
    diagnostics: List[Diagnostic] = []
    if not patch_id:
        diagnostics.append(Diagnostic("error", "E_PATCH_MISSING", "patch ID cannot be empty"))
    if not target:
        diagnostics.append(Diagnostic("error", "E_TARGET_MISSING", "target cannot be empty"))
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        diagnostics.append(Diagnostic("error", "E_AXP_XML", f"cannot parse legacy patch XML: {exc}"))
        return _axp_error_result(patch_id, target, diagnostics)

    if _local_name(root.tag) != "patch-1.0":
        diagnostics.append(
            Diagnostic("error", "E_AXP_ROOT", f"expected patch-1.0 root, found {_local_name(root.tag)}")
        )
    unknown_root_attributes = sorted(set(root.attrib) - {"appVersion"})
    if unknown_root_attributes:
        diagnostics.append(
            Diagnostic(
                "error",
                "E_AXP_ROOT_ATTRIBUTES",
                "unsupported legacy patch root attributes",
                context={"attributes": unknown_root_attributes},
            )
        )
    app_version = root.attrib.get("appVersion", "").strip()
    if app_version:
        match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", app_version)
        if match is None:
            diagnostics.append(
                Diagnostic("error", "E_AXP_VERSION", f"unrecognized appVersion: {app_version}")
            )
        elif tuple(int(part) for part in match.groups()) > (1, 1, 0):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_AXP_VERSION_NEWER",
                    f"patch was written by a newer appVersion: {app_version}",
                )
            )

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    node_map: Dict[str, Dict[str, Any]] = {}
    legacy_name_to_id: Dict[str, str] = {}
    used_ids: set[str] = set()
    object_rows: List[Tuple[ET.Element, Dict[str, Any]]] = []
    nets_sections: List[ET.Element] = []
    settings_sections: List[ET.Element] = []
    settings_values: Dict[str, str] = {}
    ignored_ui: Dict[str, int] = {}

    for child in root:
        tag = _local_name(child.tag)
        if tag == "obj":
            unknown_attributes = sorted(set(child.attrib) - AXP_OBJECT_ATTRIBUTES)
            if unknown_attributes:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_AXP_OBJECT_ATTRIBUTES",
                        "unsupported legacy object attributes",
                        context={"attributes": unknown_attributes, "name": child.attrib.get("name", "")},
                    )
                )
            type_name = child.attrib.get("type", "").strip()
            instance_name = child.attrib.get("name", "").strip()
            if not type_name or not instance_name:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_AXP_OBJECT",
                        "legacy object requires non-empty type and name attributes",
                    )
                )
            for coordinate in ("x", "y"):
                value = child.attrib.get(coordinate, "")
                if not INTEGER_RE.fullmatch(value):
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "E_AXP_COORDINATE",
                            f"legacy object requires an integer {coordinate} coordinate",
                            context={"name": instance_name, "value": value},
                        )
                    )

            candidates, identity_diagnostics, ambiguity_code = _legacy_object_candidates(
                type_name,
                child.attrib.get("uuid", "").strip(),
                child.attrib.get("sha", "").strip(),
                catalog,
            )
            diagnostics.extend(identity_diagnostics)
            node_id = _safe_node_id(instance_name or f"node_{len(nodes) + 1}", used_ids)
            if instance_name in legacy_name_to_id:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_AXP_OBJECT_NAME_DUP",
                        f"duplicate legacy object name: {instance_name}",
                    )
                )
            elif instance_name:
                legacy_name_to_id[instance_name] = node_id
            node = {
                "id": node_id,
                "name": instance_name or node_id,
                "object": type_name,
                "parameters": {},
                "parameter_metadata": {},
                "attributes": {},
                "_candidate_objects": candidates,
                "_resolution_failed": not candidates,
                "_ambiguity_code": ambiguity_code or "E_AXP_TYPE_AMBIGUOUS",
                "_constraint_code": "E_AXP_OVERLOAD_CONSTRAINT",
                "_constrained_warning": "W_AXP_OVERLOAD_CONSTRAINED",
                "_constrain_legacy_type": ambiguity_code == "E_AXP_SHA_AMBIGUOUS",
                "_legacy_type": type_name,
                "_parameter_types": {},
                "_attribute_types": {},
                "_line": None,
            }
            nodes.append(node)
            node_map[node_id] = node
            object_rows.append((child, node))
        elif tag == "nets":
            nets_sections.append(child)
        elif tag == "settings":
            settings_sections.append(child)
        elif tag in {"comment", "hyperlink", "windowPos", "helpPatch"}:
            ignored_ui[tag] = ignored_ui.get(tag, 0) + 1
        elif tag == "notes":
            if (child.text or "").strip() or len(child):
                ignored_ui[tag] = ignored_ui.get(tag, 0) + 1
        elif tag in {"patcher", "patchobj", "zombie"}:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_AXP_OBJECT_KIND_UNSUPPORTED",
                    f"legacy object kind is not supported by kpatch v1: {tag}",
                )
            )
        else:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_AXP_ELEMENT_UNSUPPORTED",
                    f"unsupported legacy patch element: {tag}",
                )
            )

    if ignored_ui:
        diagnostics.append(
            Diagnostic(
                "warning",
                "W_AXP_UI_IGNORED",
                "legacy canvas-only metadata is not represented in kpatch",
                context={"elements": dict(sorted(ignored_ui.items()))},
            )
        )

    for element, node in object_rows:
        sections: Dict[str, List[ET.Element]] = {}
        for child in element:
            sections.setdefault(_local_name(child.tag), []).append(child)
        unknown_sections = sorted(set(sections) - {"params", "attribs"})
        if unknown_sections:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_AXP_OBJECT_ELEMENT_UNSUPPORTED",
                    f"unsupported elements on legacy object {node['name']}",
                    context={"elements": unknown_sections},
                )
            )
        for section_name in ("params", "attribs"):
            if len(sections.get(section_name, [])) > 1:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_AXP_OBJECT_SECTION_DUP",
                        f"duplicate {section_name} section on legacy object {node['name']}",
                    )
                )

        attribs = sections.get("attribs", [])
        if attribs:
            attribute_section = attribs[0]
            if attribute_section.attrib or (attribute_section.text or "").strip():
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_AXP_ATTRIBUTE_METADATA_UNSUPPORTED",
                        f"attribs section metadata is not supported: {node['name']}",
                        context={"attributes": dict(attribute_section.attrib)},
                    )
                )
            seen_attributes: set[str] = set()
            for attribute_element in attribute_section:
                attribute_type = _local_name(attribute_element.tag)
                attribute_name = attribute_element.attrib.get("attributeName", "").strip()
                value: Optional[str] = None
                malformed = False
                if attribute_type == "text":
                    if set(attribute_element.attrib) != {"attributeName"}:
                        malformed = True
                    text_elements = [
                        child
                        for child in attribute_element
                        if _local_name(child.tag) == "sText"
                    ]
                    if len(text_elements) > 1 or len(text_elements) != len(attribute_element):
                        malformed = True
                    if (attribute_element.text or "").strip():
                        malformed = True
                    if text_elements:
                        text_element = text_elements[0]
                        if text_element.attrib or len(text_element):
                            malformed = True
                        value = text_element.text or ""
                    else:
                        value = ""
                elif attribute_type in ATTRIBUTE_VALUE_FIELDS:
                    value_field = ATTRIBUTE_VALUE_FIELDS[attribute_type]
                    expected_attributes = {"attributeName", value_field}
                    if (
                        set(attribute_element.attrib) != expected_attributes
                        or len(attribute_element)
                        or (attribute_element.text or "").strip()
                    ):
                        malformed = True
                    if value_field in attribute_element.attrib:
                        value = attribute_element.attrib[value_field]
                else:
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "E_AXP_ATTRIBUTE_TYPE",
                            f"unsupported legacy attribute type: {attribute_type}",
                            context={"object": node["name"]},
                        )
                    )
                    continue
                if malformed:
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "E_AXP_ATTRIBUTE_METADATA_UNSUPPORTED",
                            f"malformed legacy attribute: {node['name']}.{attribute_name}",
                            context={
                                "type": attribute_type,
                                "attributes": dict(attribute_element.attrib),
                            },
                        )
                    )
                if not attribute_name or value is None:
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "E_AXP_ATTRIBUTE",
                            f"legacy attribute requires a name and typed value: {node['name']}",
                        )
                    )
                    continue
                if attribute_name in seen_attributes:
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "E_AXP_ATTRIBUTE_DUP",
                            f"duplicate legacy attribute: {node['name']}.{attribute_name}",
                        )
                    )
                    continue
                seen_attributes.add(attribute_name)
                if attribute_type == "objref":
                    value = legacy_name_to_id.get(value, value)
                node["attributes"][attribute_name] = value
                node["_attribute_types"][attribute_name] = attribute_type

        params = sections.get("params", [])
        if params:
            if params[0].attrib:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_AXP_PARAMETER_METADATA_UNSUPPORTED",
                        f"params section attributes are not supported: {node['name']}",
                        context={"attributes": dict(params[0].attrib)},
                    )
                )
            seen_parameters: set[str] = set()
            for parameter_element in params[0]:
                parameter_name = parameter_element.attrib.get("name", "").strip()
                value = parameter_element.attrib.get("value", "").strip()
                parameter_tag = _local_name(parameter_element.tag)
                unknown_parameter_attributes = sorted(
                    set(parameter_element.attrib) - {"name", "value", "MidiCC", "onParent"}
                )
                if unknown_parameter_attributes or (parameter_element.text or "").strip():
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "E_AXP_PARAMETER_METADATA_UNSUPPORTED",
                            f"unknown parameter metadata: {node['name']}.{parameter_name}",
                            context={"attributes": unknown_parameter_attributes},
                        )
                    )
                if not parameter_name or "value" not in parameter_element.attrib:
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "E_AXP_PARAMETER",
                            f"legacy parameter requires name and value: {node['name']}",
                        )
                    )
                    continue
                if parameter_name in seen_parameters:
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "E_AXP_PARAMETER_DUP",
                            f"duplicate legacy parameter: {node['name']}.{parameter_name}",
                        )
                    )
                    continue
                seen_parameters.add(parameter_name)
                node["parameters"][parameter_name] = value
                node["_parameter_types"][parameter_name] = parameter_tag
                parameter_metadata: Dict[str, Any] = {}
                if "MidiCC" in parameter_element.attrib:
                    parameter_metadata["midi_cc"] = parameter_element.attrib["MidiCC"]
                if "onParent" in parameter_element.attrib:
                    parameter_metadata["on_parent"] = parameter_element.attrib["onParent"]
                preset_sections = [
                    child
                    for child in parameter_element
                    if _local_name(child.tag) == "presets"
                ]
                modulation_sections = [
                    child
                    for child in parameter_element
                    if _local_name(child.tag) == "modulators"
                ]
                if (
                    len(preset_sections) + len(modulation_sections) != len(parameter_element)
                    or len(preset_sections) > 1
                    or len(modulation_sections) > 1
                ):
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "E_AXP_PARAMETER_METADATA_UNSUPPORTED",
                            f"parameter may contain at most one presets and modulators section: {node['name']}.{parameter_name}",
                        )
                    )
                if preset_sections:
                    preset_section = preset_sections[0]
                    presets: List[Dict[str, Any]] = []
                    if preset_section.attrib or (preset_section.text or "").strip():
                        diagnostics.append(
                            Diagnostic(
                                "error", "E_PRESET_ENCODING", "presets section cannot carry metadata"
                            )
                        )
                    for preset_element in preset_section:
                        if (
                            _local_name(preset_element.tag) != "preset"
                            or set(preset_element.attrib) != {"index"}
                            or (preset_element.text or "").strip()
                            or len(preset_element) != 1
                        ):
                            diagnostics.append(
                                Diagnostic("error", "E_PRESET_ENCODING", "malformed legacy preset")
                            )
                            continue
                        value_element = preset_element[0]
                        kind = _local_name(value_element.tag)
                        value_field = "i" if kind == "i" else "v" if kind == "f" else ""
                        if (
                            not value_field
                            or set(value_element.attrib) != {value_field}
                            or len(value_element)
                            or (value_element.text or "").strip()
                        ):
                            diagnostics.append(
                                Diagnostic("error", "E_PRESET_ENCODING", "malformed legacy preset value")
                            )
                            continue
                        presets.append(
                            {
                                "index": preset_element.attrib["index"],
                                "kind": kind,
                                "value": value_element.attrib[value_field],
                            }
                        )
                    parameter_metadata["presets"] = presets
                if modulation_sections:
                    modulation_section = modulation_sections[0]
                    modulations: List[Dict[str, Any]] = []
                    if modulation_section.attrib or (modulation_section.text or "").strip():
                        diagnostics.append(
                            Diagnostic(
                                "error", "E_MODULATION_ENCODING", "modulators section cannot carry metadata"
                            )
                        )
                    for modulation_element in modulation_section:
                        allowed_attributes = {"sourceName", "modName", "value"}
                        if (
                            _local_name(modulation_element.tag) != "modulation"
                            or not {"sourceName", "value"}.issubset(modulation_element.attrib)
                            or not set(modulation_element.attrib).issubset(allowed_attributes)
                            or len(modulation_element)
                            or (modulation_element.text or "").strip()
                        ):
                            diagnostics.append(
                                Diagnostic("error", "E_MODULATION_ENCODING", "malformed legacy modulation")
                            )
                            continue
                        legacy_source = modulation_element.attrib["sourceName"]
                        modulations.append(
                            {
                                "source": legacy_name_to_id.get(legacy_source, legacy_source),
                                "modulator": modulation_element.attrib.get("modName", ""),
                                "value": modulation_element.attrib["value"],
                            }
                        )
                    parameter_metadata["modulations"] = modulations
                if parameter_metadata:
                    node["parameter_metadata"][parameter_name] = parameter_metadata

    if len(nets_sections) != 1:
        diagnostics.append(
            Diagnostic(
                "error",
                "E_AXP_NETS",
                f"legacy patch requires exactly one nets section; found {len(nets_sections)}",
            )
        )
    elif nets_sections:
        nets = nets_sections[0]
        if nets.attrib:
            diagnostics.append(
                Diagnostic("error", "E_AXP_NETS_ATTRIBUTES", "nets section cannot have attributes")
            )
        for net in nets:
            if _local_name(net.tag) != "net" or net.attrib:
                diagnostics.append(
                    Diagnostic("error", "E_AXP_NET", "nets may contain only attribute-free net elements")
                )
                continue
            sources: List[Tuple[str, str]] = []
            destinations: List[Tuple[str, str]] = []
            for endpoint_element in net:
                endpoint_kind = _local_name(endpoint_element.tag)
                expected_attributes = AXP_ENDPOINT_ATTRIBUTES.get(endpoint_kind)
                if expected_attributes is None:
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "E_AXP_NET_ENDPOINT",
                            f"unsupported net endpoint element: {endpoint_kind}",
                        )
                    )
                    continue
                if (
                    set(endpoint_element.attrib) != expected_attributes
                    or len(endpoint_element)
                    or (endpoint_element.text or "").strip()
                ):
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "E_AXP_NET_ENDPOINT",
                            f"malformed {endpoint_kind} endpoint",
                            context={"attributes": dict(endpoint_element.attrib)},
                        )
                    )
                    continue
                legacy_name = endpoint_element.attrib["obj"]
                node_id = legacy_name_to_id.get(legacy_name)
                if node_id is None:
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "E_AXP_NET_OBJECT",
                            f"net references an unknown legacy object: {legacy_name}",
                        )
                    )
                    continue
                if endpoint_kind == "source":
                    sources.append((node_id, endpoint_element.attrib["outlet"]))
                else:
                    destinations.append((node_id, endpoint_element.attrib["inlet"]))
            if len(sources) != 1 or not destinations:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_AXP_NET_ARITY",
                        "each legacy net requires exactly one source and at least one destination",
                        context={"sources": len(sources), "destinations": len(destinations)},
                    )
                )
                continue
            source = f"{sources[0][0]}.{sources[0][1]}"
            for destination_node, destination_port in destinations:
                edges.append(
                    {
                        "from": source,
                        "to": f"{destination_node}.{destination_port}",
                        "_line": None,
                    }
                )

    if len(settings_sections) > 1:
        diagnostics.append(
            Diagnostic("error", "E_AXP_SETTINGS_DUP", "legacy patch has multiple settings sections")
        )
    elif settings_sections:
        settings = settings_sections[0]
        if settings.attrib or (settings.text or "").strip():
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_AXP_SETTINGS_UNSUPPORTED",
                    "settings section cannot carry attributes or text",
                )
            )
        for setting_element in settings:
            name = _local_name(setting_element.tag)
            if name not in AXP_SETTING_CONTRACTS:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_AXP_SETTINGS_UNSUPPORTED",
                        f"unsupported legacy patch setting: {name}",
                    )
                )
                continue
            if name in settings_values:
                diagnostics.append(
                    Diagnostic("error", "E_AXP_SETTINGS_DUP", f"duplicate setting: {name}")
                )
                continue
            if setting_element.attrib or len(setting_element):
                diagnostics.append(
                    Diagnostic("error", "E_AXP_SETTINGS_UNSUPPORTED", f"malformed setting: {name}")
                )
                continue
            settings_values[name] = (setting_element.text or "").strip()

    ir = {
        "schema_version": SCHEMA_VERSION,
        "patch": {"id": patch_id, "target": target},
        "settings": settings_values,
        "nodes": nodes,
        "edges": edges,
        "assertions": {},
    }
    result = _validate_ir(ir, {"node_map": node_map}, diagnostics, catalog)
    result["evidence"]["legacy_import"] = "pass" if result["ok"] else "fail"
    return result


def import_legacy_axp(
    path: Path,
    catalog: Dict[str, Any],
    target: str = AXP_TARGET,
) -> Dict[str, Any]:
    try:
        data = path.read_bytes()
    except FileNotFoundError as exc:
        raise KSAIError(f"legacy patch does not exist: {path}") from exc
    return import_legacy_axp_bytes(data, catalog, path.stem, target)


def _render_attribute_value(value: str) -> str:
    if value.startswith("json:") or "\n" in value or "\r" in value:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return "json:" + shlex.quote(encoded)
    return shlex.quote(value)


def render_kpatch(ir: Dict[str, Any]) -> str:
    lines = [
        f"kpatch {SCHEMA_VERSION}",
        f"patch {shlex.quote(ir['patch']['id'])}",
        f"target {shlex.quote(ir['patch']['target'])}",
    ]
    for name, value in sorted(ir.get("settings", {}).items()):
        lines.append(f"setting {name} {shlex.quote(value)}")
    for node in ir["nodes"]:
        line = f"node {node['id']} {shlex.quote(node['resolved_ref'])}"
        if node.get("name", node["id"]) != node["id"]:
            line += f" {shlex.quote(node['name'])}"
        lines.append(line)
        for parameter, value in sorted(node.get("parameters", {}).items()):
            lines.append(f"param {node['id']}.{parameter} {shlex.quote(value)}")
            parameter_metadata = node.get("parameter_metadata", {}).get(parameter, {})
            metadata_tokens = []
            if "midi_cc" in parameter_metadata:
                metadata_tokens.append(f"midi_cc={parameter_metadata['midi_cc']}")
            if "on_parent" in parameter_metadata:
                metadata_tokens.append(
                    f"on_parent={'true' if parameter_metadata['on_parent'] else 'false'}"
                )
            presets = parameter_metadata.get("presets")
            if presets == []:
                metadata_tokens.append("presets=true")
            if metadata_tokens:
                lines.append(
                    f"parammeta {node['id']}.{parameter} {' '.join(metadata_tokens)}"
                )
            for preset in presets or []:
                lines.append(
                    f"preset {node['id']}.{parameter} {preset['index']} "
                    f"{preset['kind']} {shlex.quote(preset['value'])}"
                )
            for modulation in parameter_metadata.get("modulations", []):
                modulator = modulation["modulator"] or "-"
                lines.append(
                    f"modulate {node['id']}.{parameter} {modulation['source']} "
                    f"{shlex.quote(modulator)} {shlex.quote(modulation['value'])}"
                )
        for attribute, value in sorted(node.get("attributes", {}).items()):
            lines.append(
                f"attr {node['id']}.{attribute} {_render_attribute_value(value)}"
            )

    grouped_edges: Dict[str, List[str]] = {}
    for edge in ir["edges"]:
        grouped_edges.setdefault(edge["from"], []).append(edge["to"])
    for source in sorted(grouped_edges):
        destinations = ",".join(sorted(grouped_edges[source]))
        lines.append(f"connect {source} -> {destinations}")
    for name, value in sorted(ir.get("assertions", {}).items()):
        lines.append(f"assert {shlex.quote(name + '=' + value)}")
    return "\n".join(lines) + "\n"


def emit_legacy_axp(
    ir: Dict[str, Any],
    catalog: Dict[str, Any],
) -> Tuple[Optional[bytes], List[Diagnostic]]:
    diagnostics: List[Diagnostic] = []
    if ir.get("patch", {}).get("target") != AXP_TARGET:
        diagnostics.append(
            Diagnostic(
                "error",
                "E_AXP_TARGET",
                f"legacy AXP generation supports only {AXP_TARGET}",
                context={"target": ir.get("patch", {}).get("target", "")},
            )
        )
    by_ref = {obj["ref"]: obj for obj in catalog["objects"]}
    node_names = {node["id"]: node.get("name", node["id"]) for node in ir["nodes"]}
    if len(set(node_names.values())) != len(node_names):
        diagnostics.append(
            Diagnostic("error", "E_AXP_EMIT_NAMES", "legacy instance names must be unique")
        )

    root = ET.Element("patch-1.0", {"appVersion": AXP_VERSION})
    for index, node in enumerate(ir["nodes"]):
        obj = by_ref.get(node.get("resolved_ref", ""))
        if obj is None:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_AXP_EMIT_OBJECT",
                    f"resolved object is absent from the catalog: {node.get('resolved_ref', '')}",
                    context={"node": node["id"]},
                )
            )
            continue
        attributes = {"type": obj["id"]}
        if obj.get("legacy_uuid"):
            attributes["uuid"] = obj["legacy_uuid"]
        elif obj.get("source", {}).get("legacy_sha"):
            attributes["sha"] = obj["source"]["legacy_sha"]
        else:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "E_AXP_EMIT_IDENTITY",
                    f"object has neither a legacy UUID nor SHA: {obj['ref']}",
                    context={"node": node["id"]},
                )
            )
            continue
        attributes["name"] = node_names[node["id"]]
        attributes["x"] = str(14 + (index % 6) * 224)
        attributes["y"] = str(14 + (index // 6) * 196)
        object_element = ET.SubElement(root, "obj", attributes)
        parameters_element = ET.SubElement(object_element, "params")
        definitions = {item["name"]: item for item in obj.get("parameters", [])}
        for parameter_name, value in sorted(node.get("parameters", {}).items()):
            definition = definitions.get(parameter_name)
            if definition is None:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_AXP_EMIT_PARAMETER",
                        f"parameter is absent from the resolved object: {node['id']}.{parameter_name}",
                    )
                )
                continue
            instance_type = definition.get("instance_type") or _parameter_instance_type(
                definition.get("type", "")
            )
            normalized_value, error = _normalize_parameter_value(definition, value)
            if not instance_type or error is not None:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_AXP_EMIT_PARAMETER_TYPE",
                        f"cannot serialize parameter {node['id']}.{parameter_name}: {error or definition.get('type', '')}",
                    )
                )
                continue
            parameter_attributes = {
                "name": parameter_name,
                "value": normalized_value or value,
            }
            parameter_metadata = node.get("parameter_metadata", {}).get(parameter_name, {})
            if "midi_cc" in parameter_metadata:
                parameter_attributes["MidiCC"] = str(parameter_metadata["midi_cc"])
            if "on_parent" in parameter_metadata:
                parameter_attributes["onParent"] = (
                    "true" if parameter_metadata["on_parent"] else "false"
                )
            parameter_element = ET.SubElement(
                parameters_element, instance_type, parameter_attributes
            )
            if "presets" in parameter_metadata:
                presets_element = ET.SubElement(parameter_element, "presets")
                for preset in parameter_metadata["presets"]:
                    preset_element = ET.SubElement(
                        presets_element, "preset", {"index": str(preset["index"])}
                    )
                    value_field = "i" if preset["kind"] == "i" else "v"
                    ET.SubElement(
                        preset_element,
                        preset["kind"],
                        {value_field: preset["value"]},
                    )
            if "modulations" in parameter_metadata:
                modulations_element = ET.SubElement(parameter_element, "modulators")
                for modulation in parameter_metadata["modulations"]:
                    modulation_attributes = {
                        "sourceName": node_names[modulation["source"]],
                        "value": modulation["value"],
                    }
                    if modulation["modulator"]:
                        modulation_attributes["modName"] = modulation["modulator"]
                    ET.SubElement(
                        modulations_element, "modulation", modulation_attributes
                    )
        attributes_element = ET.SubElement(object_element, "attribs")
        attribute_definitions = {
            item["name"]: item for item in obj.get("attributes", [])
        }
        for attribute_name, value in sorted(node.get("attributes", {}).items()):
            definition = attribute_definitions.get(attribute_name)
            if definition is None:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_AXP_EMIT_ATTRIBUTE",
                        f"attribute is absent from the resolved object: {node['id']}.{attribute_name}",
                    )
                )
                continue
            attribute_type = definition.get("instance_type") or definition.get("type", "")
            normalized_value, error = _normalize_attribute_value(
                definition, value, set(node_names)
            )
            if attribute_type not in ATTRIBUTE_TYPES or error is not None:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "E_AXP_EMIT_ATTRIBUTE_TYPE",
                        f"cannot serialize attribute {node['id']}.{attribute_name}: {error or attribute_type}",
                    )
                )
                continue
            assert normalized_value is not None
            if attribute_type == "text":
                attribute_element = ET.SubElement(
                    attributes_element,
                    "text",
                    {"attributeName": attribute_name},
                )
                ET.SubElement(attribute_element, "sText").text = normalized_value
            else:
                value_field = ATTRIBUTE_VALUE_FIELDS[attribute_type]
                serialized_value = normalized_value
                if attribute_type == "objref":
                    serialized_value = node_names[normalized_value]
                ET.SubElement(
                    attributes_element,
                    attribute_type,
                    {"attributeName": attribute_name, value_field: serialized_value},
                )

    nets_element = ET.SubElement(root, "nets")
    grouped_edges: Dict[str, List[str]] = {}
    for edge in ir["edges"]:
        grouped_edges.setdefault(edge["from"], []).append(edge["to"])
    for source in sorted(grouped_edges):
        source_parts = source.rsplit(".", 1)
        if len(source_parts) != 2 or source_parts[0] not in node_names:
            diagnostics.append(
                Diagnostic("error", "E_AXP_EMIT_EDGE", f"invalid source endpoint: {source}")
            )
            continue
        net = ET.SubElement(nets_element, "net")
        ET.SubElement(
            net,
            "source",
            {"obj": node_names[source_parts[0]], "outlet": source_parts[1]},
        )
        for destination in sorted(grouped_edges[source]):
            destination_parts = destination.rsplit(".", 1)
            if len(destination_parts) != 2 or destination_parts[0] not in node_names:
                diagnostics.append(
                    Diagnostic("error", "E_AXP_EMIT_EDGE", f"invalid destination endpoint: {destination}")
                )
                continue
            ET.SubElement(
                net,
                "dest",
                {"obj": node_names[destination_parts[0]], "inlet": destination_parts[1]},
            )

    settings = ET.SubElement(root, "settings")
    settings_values = dict(ir.get("settings", {}))
    settings_values.setdefault("subpatchmode", "no")
    setting_order = list(AXP_SETTING_CONTRACTS)
    for name in sorted(settings_values, key=lambda item: setting_order.index(item)):
        ET.SubElement(settings, name).text = settings_values[name]
    ET.SubElement(root, "notes")
    if any(item.severity == "error" for item in diagnostics):
        return None, diagnostics
    ET.indent(root, space="   ")
    return ET.tostring(root, encoding="utf-8", short_empty_elements=True) + b"\n", diagnostics


def semantic_patch_signature(ir: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "settings": dict(sorted(ir.get("settings", {}).items())),
        "nodes": [
            {
                "id": node["id"],
                "name": node.get("name", node["id"]),
                "resolved_ref": node["resolved_ref"],
                "parameters": dict(sorted(node.get("parameters", {}).items())),
                "parameter_metadata": node.get("parameter_metadata", {}),
                "attributes": dict(sorted(node.get("attributes", {}).items())),
            }
            for node in ir["nodes"]
        ],
        "edges": sorted(
            ({"from": edge["from"], "to": edge["to"]} for edge in ir["edges"]),
            key=lambda edge: (edge["from"], edge["to"]),
        ),
    }


def roundtrip_legacy_axp(path: Path, catalog: Dict[str, Any]) -> Dict[str, Any]:
    imported = import_legacy_axp(path, catalog)
    if not imported["ok"]:
        return {
            "ok": False,
            "input": str(path),
            "evidence": {"legacy_import": "fail", "semantic_roundtrip": "not_run"},
            "diagnostics": imported["diagnostics"],
        }

    kpatch_text = render_kpatch(imported["patch_ir"])
    reparsed = validate_patch_text(kpatch_text, catalog)
    if not reparsed["ok"]:
        return {
            "ok": False,
            "input": str(path),
            "evidence": {"legacy_import": "pass", "semantic_roundtrip": "fail"},
            "diagnostics": reparsed["diagnostics"],
        }
    axp_bytes, emit_diagnostics = emit_legacy_axp(reparsed["patch_ir"], catalog)
    if axp_bytes is None:
        return {
            "ok": False,
            "input": str(path),
            "evidence": {"legacy_import": "pass", "semantic_roundtrip": "fail"},
            "diagnostics": [item.to_dict() for item in emit_diagnostics],
        }
    reimported = import_legacy_axp_bytes(
        axp_bytes,
        catalog,
        imported["patch_ir"]["patch"]["id"],
        imported["patch_ir"]["patch"]["target"],
    )
    first_signature = semantic_patch_signature(imported["patch_ir"])
    second_signature = semantic_patch_signature(reimported["patch_ir"])
    equal = reimported["ok"] and first_signature == second_signature
    diagnostics = list(imported["diagnostics"])
    diagnostics.extend(item.to_dict() for item in emit_diagnostics)
    diagnostics.extend(reimported["diagnostics"] if not reimported["ok"] else [])
    if not equal:
        diagnostics.append(
            Diagnostic(
                "error",
                "E_SEMANTIC_ROUNDTRIP",
                "legacy import and deterministic re-import differ semantically",
                context={"before": first_signature, "after": second_signature},
            ).to_dict()
        )
    return {
        "ok": equal,
        "input": str(path),
        "node_count": len(imported["patch_ir"]["nodes"]),
        "edge_count": len(imported["patch_ir"]["edges"]),
        "kpatch_sha256": _sha256(kpatch_text.encode("utf-8")),
        "axp_sha256": _sha256(axp_bytes),
        "evidence": {
            "legacy_import": "pass",
            "kpatch_reparse": "pass",
            "legacy_generation": "pass",
            "semantic_roundtrip": "pass" if equal else "fail",
            "legacy_java_deserialize": "not_run",
            "arm_compile_link": "not_run",
            "connected_board": "not_run",
            "audible": "not_run",
        },
        "diagnostics": diagnostics,
    }


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _write_text_atomic(path: Path, text: str) -> None:
    _write_bytes_atomic(path, text.encode("utf-8"))


def _write_json(path: Path, value: Dict[str, Any]) -> None:
    serialized = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    _write_text_atomic(path, serialized)


def _emit(value: Dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def _command_catalog_build(args: argparse.Namespace) -> int:
    libraries = [parse_library_spec(spec) for spec in args.library]
    catalog, diagnostics = build_catalog(libraries)
    errors = [item for item in diagnostics if item.severity == "error"]
    if not errors:
        _write_json(args.output, catalog)
    response = {
        "ok": not errors,
        "output": str(args.output),
        "output_written": not errors,
        "library_count": len(catalog["libraries"]),
        "object_count": len(catalog["objects"]),
        "catalog_sha256": _sha256(
            (json.dumps(catalog, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
        ),
        "diagnostics": [item.to_dict() for item in diagnostics],
    }
    _emit(response)
    return 0 if not errors else 2


def _command_catalog_search(args: argparse.Namespace) -> int:
    catalog = _load_catalog(args.catalog)
    _emit(search_catalog(catalog, args.query, args.limit))
    return 0


def _command_catalog_inspect(args: argparse.Namespace) -> int:
    catalog = _load_catalog(args.catalog)
    result = inspect_catalog(catalog, args.object)
    _emit(result)
    return 0 if result["ok"] else 2


def _command_patch_validate(args: argparse.Namespace) -> int:
    catalog = _load_catalog(args.catalog)
    result = validate_patch(args.patch, catalog)
    _emit(result)
    return 0 if result["ok"] else 2


def _command_patch_explain(args: argparse.Namespace) -> int:
    catalog = _load_catalog(args.catalog)
    result = explain_validated_patch(validate_patch(args.patch, catalog), catalog)
    _emit(result)
    return 0 if result["ok"] else 2


def _command_patch_diff(args: argparse.Namespace) -> int:
    catalog = _load_catalog(args.catalog)
    result = diff_validated_patches(
        validate_patch(args.before, catalog), validate_patch(args.after, catalog)
    )
    _emit(result)
    return 0 if result["ok"] else 2


def _command_patch_repair(args: argparse.Namespace) -> int:
    catalog = _load_catalog(args.catalog)
    result = repair_plan(validate_patch(args.patch, catalog))
    _emit(result)
    return 0 if result["ok"] else 2


def _command_patch_import(args: argparse.Namespace) -> int:
    catalog = _load_catalog(args.catalog)
    result = import_legacy_axp(args.axp, catalog, args.target)
    response = {
        "ok": result["ok"],
        "input": str(args.axp),
        "output": str(args.output),
        "output_written": False,
        "evidence": dict(result["evidence"]),
        "diagnostics": result["diagnostics"],
    }
    if result["ok"]:
        rendered = render_kpatch(result["patch_ir"])
        _write_text_atomic(args.output, rendered)
        response["output_written"] = True
        response.update(
            {
                "node_count": len(result["patch_ir"]["nodes"]),
                "edge_count": len(result["patch_ir"]["edges"]),
                "output_sha256": _sha256(rendered.encode("utf-8")),
            }
        )
        response["evidence"]["kpatch_generation"] = "pass"
    else:
        response["evidence"]["kpatch_generation"] = "not_run"
    _emit(response)
    return 0 if result["ok"] else 2


def _command_patch_emit(args: argparse.Namespace) -> int:
    catalog = _load_catalog(args.catalog)
    result = validate_patch(args.patch, catalog)
    diagnostics = list(result["diagnostics"])
    output_bytes: Optional[bytes] = None
    if result["ok"]:
        output_bytes, emit_diagnostics = emit_legacy_axp(result["patch_ir"], catalog)
        diagnostics.extend(item.to_dict() for item in emit_diagnostics)
    ok = result["ok"] and output_bytes is not None
    evidence = dict(result["evidence"])
    evidence["legacy_generation"] = "pass" if ok else "fail" if result["ok"] else "not_run"
    evidence["legacy_java_deserialize"] = "not_run"
    response: Dict[str, Any] = {
        "ok": ok,
        "input": str(args.patch),
        "output": str(args.output),
        "output_written": False,
        "evidence": evidence,
        "diagnostics": diagnostics,
    }
    if output_bytes is not None:
        _write_bytes_atomic(args.output, output_bytes)
        response["output_written"] = True
        response.update(
            {
                "byte_count": len(output_bytes),
                "output_sha256": _sha256(output_bytes),
            }
        )
    _emit(response)
    return 0 if ok else 2


def _command_patch_roundtrip(args: argparse.Namespace) -> int:
    catalog = _load_catalog(args.catalog)
    result = roundtrip_legacy_axp(args.axp, catalog)
    _emit(result)
    return 0 if result["ok"] else 2


def _last_json_object(output: str) -> Optional[Dict[str, Any]]:
    for line in reversed(output.splitlines()):
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _command_patch_build(args: argparse.Namespace) -> int:
    catalog = _load_catalog(args.catalog)
    validated = validate_patch(args.patch, catalog)
    diagnostics = list(validated["diagnostics"])
    evidence = dict(validated["evidence"])
    response: Dict[str, Any] = {
        "ok": False,
        "input": str(args.patch),
        "output": str(args.output),
        "output_written": False,
        "evidence": evidence,
        "diagnostics": diagnostics,
    }
    if not validated["ok"]:
        evidence["legacy_generation"] = "not_run"
        evidence["arm_compile_link"] = "not_run"
        _emit(response)
        return 2

    axp_bytes, emit_diagnostics = emit_legacy_axp(validated["patch_ir"], catalog)
    diagnostics.extend(item.to_dict() for item in emit_diagnostics)
    if axp_bytes is None:
        evidence["legacy_generation"] = "fail"
        evidence["arm_compile_link"] = "not_run"
        _emit(response)
        return 2

    _write_bytes_atomic(args.output, axp_bytes)
    response["output_written"] = True
    response["output_sha256"] = _sha256(axp_bytes)
    evidence["legacy_generation"] = "pass"

    compiler = args.compiler.expanduser().resolve()
    try:
        completed = subprocess.run(
            [str(compiler), str(args.output.resolve())],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=args.timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        evidence["arm_compile_link"] = "not_run"
        diagnostics.append(
            Diagnostic("error", "E_COMPILER_START", str(exc), context={"compiler": str(compiler)}).to_dict()
        )
        _emit(response)
        return 2

    compile_result = _last_json_object(completed.stdout)
    if compile_result is None:
        evidence["arm_compile_link"] = "fail"
        diagnostics.append(
            Diagnostic(
                "error",
                "E_COMPILER_PROTOCOL",
                "compile-only backend did not emit a JSON result",
                context={
                    "exit_code": completed.returncode,
                    "stderr_tail": completed.stderr[-2000:],
                },
            ).to_dict()
        )
        _emit(response)
        return 2

    response["compile"] = compile_result
    evidence.update(compile_result.get("evidence", {}))
    diagnostics.extend(compile_result.get("diagnostics", []))
    ok = completed.returncode == 0 and bool(compile_result.get("ok"))
    response["ok"] = ok
    _emit(response)
    return 0 if ok else 2


def _command_object_validate(args: argparse.Namespace) -> int:
    from object_sdk import manifest_report

    report, _ = manifest_report(args.manifest)
    _emit(report)
    return 0 if report["ok"] else 2


def _command_object_emit(args: argparse.Namespace) -> int:
    from object_sdk import manifest_report, render_axo

    report, manifest = manifest_report(args.manifest)
    response = dict(report)
    response.update({"output": str(args.output), "output_written": False})
    if report["ok"] and manifest is not None:
        rendered = render_axo(manifest)
        _write_bytes_atomic(args.output, rendered)
        response["output_written"] = True
        response["output_sha256"] = _sha256(rendered)
    _emit(response)
    return 0 if report["ok"] else 2


def _command_serve(args: argparse.Namespace) -> int:
    from ksai_service import ReadOnlyAPI, is_loopback_host, serve

    if not is_loopback_host(args.host):
        raise KSAIError("the AI service only binds to 127.0.0.1, ::1, or localhost")
    if not 1 <= args.port <= 65535:
        raise KSAIError("service port must be between 1 and 65535")
    catalog = _load_catalog(args.catalog)
    api = ReadOnlyAPI(
        catalog,
        search=search_catalog,
        inspect=inspect_catalog,
        validate_text=validate_patch_text,
        explain=explain_validated_patch,
    )
    _emit(
        {
            "ok": True,
            "service": "ksai-read-only",
            "version": 1,
            "listen": f"http://{args.host}:{args.port}",
            "mutation": "disabled",
            "device_access": "disabled",
        }
    )
    serve(api, args.host, args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ksai", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    catalog = commands.add_parser("catalog", help="build or search a legacy object catalog")
    catalog_commands = catalog.add_subparsers(dest="catalog_command", required=True)

    catalog_build = catalog_commands.add_parser("build", help="build a deterministic catalog")
    catalog_build.add_argument("--library", action="append", default=[], metavar="NAME=PATH")
    catalog_build.add_argument("--output", type=Path, required=True)
    catalog_build.set_defaults(handler=_command_catalog_build)

    catalog_search = catalog_commands.add_parser("search", help="return compact object signatures")
    catalog_search.add_argument("--catalog", type=Path, required=True)
    catalog_search.add_argument("--limit", type=int, default=10)
    catalog_search.add_argument("query")
    catalog_search.set_defaults(handler=_command_catalog_search)

    catalog_inspect = catalog_commands.add_parser(
        "inspect", help="return the exact contract for one object or overload family"
    )
    catalog_inspect.add_argument("--catalog", type=Path, required=True)
    catalog_inspect.add_argument("object")
    catalog_inspect.set_defaults(handler=_command_catalog_inspect)

    patch = commands.add_parser("patch", help="validate and convert compact or legacy patches")
    patch_commands = patch.add_subparsers(dest="patch_command", required=True)
    patch_validate = patch_commands.add_parser("validate", help="run structural validation")
    patch_validate.add_argument("--catalog", type=Path, required=True)
    patch_validate.add_argument("patch", type=Path)
    patch_validate.set_defaults(handler=_command_patch_validate)

    patch_explain = patch_commands.add_parser(
        "explain", help="summarize a resolved graph without embedded DSP source"
    )
    patch_explain.add_argument("--catalog", type=Path, required=True)
    patch_explain.add_argument("patch", type=Path)
    patch_explain.set_defaults(handler=_command_patch_explain)

    patch_diff = patch_commands.add_parser("diff", help="return a semantic patch difference")
    patch_diff.add_argument("--catalog", type=Path, required=True)
    patch_diff.add_argument("before", type=Path)
    patch_diff.add_argument("after", type=Path)
    patch_diff.set_defaults(handler=_command_patch_diff)

    patch_repair = patch_commands.add_parser(
        "repair", help="return a conservative repair plan without changing the patch"
    )
    patch_repair.add_argument("--catalog", type=Path, required=True)
    patch_repair.add_argument("patch", type=Path)
    patch_repair.set_defaults(handler=_command_patch_repair)

    patch_import = patch_commands.add_parser(
        "import", help="import a supported legacy .axp as deterministic kpatch"
    )
    patch_import.add_argument("--catalog", type=Path, required=True)
    patch_import.add_argument("--target", default=AXP_TARGET)
    patch_import.add_argument("--output", type=Path, required=True)
    patch_import.add_argument("axp", type=Path)
    patch_import.set_defaults(handler=_command_patch_import)

    patch_emit = patch_commands.add_parser(
        "emit", help="emit deterministic Ksoloti 1.1.0 .axp XML"
    )
    patch_emit.add_argument("--catalog", type=Path, required=True)
    patch_emit.add_argument("--output", type=Path, required=True)
    patch_emit.add_argument("patch", type=Path)
    patch_emit.set_defaults(handler=_command_patch_emit)

    patch_roundtrip = patch_commands.add_parser(
        "roundtrip", help="prove import, generation, re-import, and semantic equality"
    )
    patch_roundtrip.add_argument("--catalog", type=Path, required=True)
    patch_roundtrip.add_argument("axp", type=Path)
    patch_roundtrip.set_defaults(handler=_command_patch_roundtrip)

    patch_build = patch_commands.add_parser(
        "build", help="emit AXP and compile/link it without connecting to USB"
    )
    patch_build.add_argument("--catalog", type=Path, required=True)
    patch_build.add_argument("--output", type=Path, required=True)
    patch_build.add_argument(
        "--compiler",
        type=Path,
        default=Path(__file__).resolve().with_name("compile-axp.sh"),
    )
    patch_build.add_argument("--timeout", type=int, default=180)
    patch_build.add_argument("patch", type=Path)
    patch_build.set_defaults(handler=_command_patch_build)

    object_command = commands.add_parser(
        "object", help="validate or generate an Object SDK manifest"
    )
    object_commands = object_command.add_subparsers(dest="object_command", required=True)
    object_validate = object_commands.add_parser("validate", help="validate an Object SDK manifest")
    object_validate.add_argument("manifest", type=Path)
    object_validate.set_defaults(handler=_command_object_validate)
    object_emit = object_commands.add_parser("emit", help="emit deterministic thin .axo glue")
    object_emit.add_argument("--output", type=Path, required=True)
    object_emit.add_argument("manifest", type=Path)
    object_emit.set_defaults(handler=_command_object_emit)

    service = commands.add_parser(
        "serve", help="serve read-only catalog and patch operations on loopback"
    )
    service.add_argument("--catalog", type=Path, required=True)
    service.add_argument("--host", default="127.0.0.1")
    service.add_argument("--port", type=int, default=8765)
    service.set_defaults(handler=_command_serve)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "limit", 1) < 1:
        _emit(
            {
                "ok": False,
                "diagnostics": [
                    {
                        "severity": "error",
                        "code": "E_LIMIT",
                        "message": "limit must be positive",
                    }
                ],
            }
        )
        return 2
    try:
        return args.handler(args)
    except (KSAIError, OSError) as exc:
        _emit(
            {
                "ok": False,
                "diagnostics": [
                    {"severity": "error", "code": "E_INPUT", "message": str(exc)}
                ],
            }
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
