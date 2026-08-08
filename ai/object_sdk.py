#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic manifest validation and thin legacy .axo glue generation."""

from __future__ import annotations

import hashlib
import html
import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
STABLE_ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)+$")
ARGUMENT_RE = re.compile(r"^(?:(?:inlet|outlet|param|attr)_[A-Za-z0-9_]+|BUFSIZE)$")
NUMBER_RE = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$")
RESERVED_INSTANCE_NAMES = {"Init", "MidiInHandler", "dispose", "dsp"}
PORT_TYPES = {
    "frac32",
    "frac32.bipolar",
    "frac32buffer",
    "frac32buffer.bipolar",
    "int32",
    "bool32",
    "charptr32",
}
PARAMETER_TYPES = {
    "frac32.u.map",
    "frac32.s.map",
    "frac32.u.mapvsl",
    "frac32.s.mapvsl",
    "int32",
    "int32.small",
    "int32.hradio",
    "int32.vradio",
    "int2x16",
    "bin8",
    "bin12",
    "bin16",
    "bin32",
    "bool32.tgl",
    "bool32.mom",
}


def _diagnostic(code: str, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {"severity": "error", "code": code, "message": message}
    if context:
        result["context"] = context
    return result


def load_manifest(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("object manifest root must be an object")
    return value


def validate_manifest(manifest: Dict[str, Any], base_dir: Path) -> List[Dict[str, Any]]:
    diagnostics: List[Dict[str, Any]] = []
    required = {
        "schema_version",
        "stable_id",
        "id",
        "uuid",
        "description",
        "author",
        "license",
        "ports",
        "parameters",
        "implementation",
        "resources",
        "tests",
    }
    missing = sorted(required - set(manifest))
    if missing:
        diagnostics.append(_diagnostic("E_SDK_REQUIRED", "missing manifest fields", {"fields": missing}))
        return diagnostics
    if manifest.get("schema_version") != 1:
        diagnostics.append(_diagnostic("E_SDK_VERSION", "schema_version must be 1"))
    if not STABLE_ID_RE.fullmatch(str(manifest.get("stable_id", ""))):
        diagnostics.append(_diagnostic("E_SDK_STABLE_ID", "stable_id must be a lowercase namespaced identifier"))
    if not str(manifest.get("id", "")).strip():
        diagnostics.append(_diagnostic("E_SDK_ID", "legacy object id cannot be empty"))
    try:
        uuid.UUID(str(manifest.get("uuid", "")))
    except ValueError:
        diagnostics.append(_diagnostic("E_SDK_UUID", "uuid must be a canonical UUID"))
    if not str(manifest.get("license", "")).strip():
        diagnostics.append(_diagnostic("E_SDK_LICENSE", "license cannot be empty"))

    ports = manifest.get("ports")
    if not isinstance(ports, dict) or set(ports) != {"inlets", "outlets"}:
        diagnostics.append(_diagnostic("E_SDK_PORTS", "ports must contain only inlets and outlets"))
        ports = {"inlets": [], "outlets": []}
    port_names = set()
    for direction in ("inlets", "outlets"):
        values = ports.get(direction, [])
        if not isinstance(values, list):
            diagnostics.append(_diagnostic("E_SDK_PORTS", f"{direction} must be a list"))
            continue
        for port in values:
            if not isinstance(port, dict) or not {"name", "type"}.issubset(port):
                diagnostics.append(_diagnostic("E_SDK_PORT", "each port needs name and type"))
                continue
            name = str(port["name"])
            if not IDENTIFIER_RE.fullmatch(name) or name in port_names:
                diagnostics.append(_diagnostic("E_SDK_PORT_NAME", f"invalid or duplicate port name: {name}"))
            port_names.add(name)
            if port["type"] not in PORT_TYPES:
                diagnostics.append(_diagnostic("E_SDK_PORT_TYPE", f"unsupported port type: {port['type']}"))

    parameter_names = set()
    parameter_ids = set()
    parameters = manifest.get("parameters", [])
    if not isinstance(parameters, list):
        diagnostics.append(_diagnostic("E_SDK_PARAMETERS", "parameters must be a list"))
        parameters = []
    for parameter in parameters:
        if not isinstance(parameter, dict) or not {"id", "name", "type", "default"}.issubset(parameter):
            diagnostics.append(_diagnostic("E_SDK_PARAMETER", "each parameter needs id, name, type, and default"))
            continue
        name = str(parameter["name"])
        stable_id = str(parameter["id"])
        if not IDENTIFIER_RE.fullmatch(name) or name in parameter_names:
            diagnostics.append(_diagnostic("E_SDK_PARAMETER_NAME", f"invalid or duplicate parameter name: {name}"))
        parameter_names.add(name)
        if not STABLE_ID_RE.fullmatch(stable_id):
            diagnostics.append(_diagnostic("E_SDK_PARAMETER_ID", f"invalid stable parameter id: {stable_id}"))
        elif not stable_id.startswith(str(manifest.get("stable_id", "")) + "."):
            diagnostics.append(
                _diagnostic(
                    "E_SDK_PARAMETER_NAMESPACE",
                    f"parameter id must be below the object stable id: {stable_id}",
                )
            )
        if stable_id in parameter_ids:
            diagnostics.append(_diagnostic("E_SDK_PARAMETER_ID", f"duplicate stable parameter id: {stable_id}"))
        parameter_ids.add(stable_id)
        if parameter["type"] not in PARAMETER_TYPES:
            diagnostics.append(_diagnostic("E_SDK_PARAMETER_TYPE", f"unsupported parameter type: {parameter['type']}"))
        if not NUMBER_RE.fullmatch(str(parameter["default"])):
            diagnostics.append(
                _diagnostic("E_SDK_PARAMETER_DEFAULT", f"parameter default must be numeric: {name}")
            )

    implementation = manifest.get("implementation")
    implementation_fields = {
        "header", "class_name", "instance_name", "init_method", "process_method", "rate", "arguments"
    }
    if not isinstance(implementation, dict) or set(implementation) != implementation_fields:
        diagnostics.append(_diagnostic("E_SDK_IMPLEMENTATION", "implementation fields do not match SDK v1"))
        implementation = {}
    header = str(implementation.get("header", ""))
    if not header or Path(header).name != header or "]]>" in header:
        diagnostics.append(_diagnostic("E_SDK_HEADER", "header must be one local filename"))
    elif not (base_dir / header).is_file():
        diagnostics.append(_diagnostic("E_SDK_HEADER_MISSING", f"implementation header does not exist: {header}"))
    for field in ("class_name", "instance_name", "init_method", "process_method"):
        if not IDENTIFIER_RE.fullmatch(str(implementation.get(field, ""))):
            diagnostics.append(_diagnostic("E_SDK_IMPLEMENTATION_NAME", f"invalid C++ identifier: {field}"))
    if implementation.get("instance_name") in RESERVED_INSTANCE_NAMES:
        diagnostics.append(
            _diagnostic(
                "E_SDK_INSTANCE_RESERVED",
                f"instance_name collides with generated patch methods: {implementation.get('instance_name')}",
            )
        )
    if implementation.get("rate") not in {"krate", "srate"}:
        diagnostics.append(_diagnostic("E_SDK_RATE", "rate must be krate or srate"))
    arguments = implementation.get("arguments", [])
    if not isinstance(arguments, list) or any(not ARGUMENT_RE.fullmatch(str(item)) for item in arguments):
        diagnostics.append(_diagnostic("E_SDK_ARGUMENT", "arguments must use generated inlet/outlet/param/attr names or BUFSIZE"))
    elif isinstance(ports, dict):
        allowed_arguments = {"BUFSIZE"}
        allowed_arguments.update(
            f"inlet_{item['name']}"
            for item in ports.get("inlets", [])
            if isinstance(item, dict) and "name" in item
        )
        allowed_arguments.update(
            f"outlet_{item['name']}"
            for item in ports.get("outlets", [])
            if isinstance(item, dict) and "name" in item
        )
        allowed_arguments.update(f"param_{name}" for name in parameter_names)
        unknown_arguments = sorted(set(arguments) - allowed_arguments)
        if unknown_arguments:
            diagnostics.append(
                _diagnostic(
                    "E_SDK_ARGUMENT_REFERENCE",
                    "arguments must reference declared ports or parameters",
                    {"arguments": unknown_arguments},
                )
            )

    resources = manifest.get("resources")
    resource_fields = {"max_voices", "state_bytes", "scratch_bytes", "bounded_work_per_block"}
    if not isinstance(resources, dict) or set(resources) != resource_fields:
        diagnostics.append(_diagnostic("E_SDK_RESOURCES", "resources fields do not match SDK v1"))
    else:
        for name, value in resources.items():
            if not isinstance(value, int) or value < 0:
                diagnostics.append(_diagnostic("E_SDK_RESOURCE_VALUE", f"{name} must be a non-negative integer"))
        if isinstance(resources.get("max_voices"), int) and resources["max_voices"] < 1:
            diagnostics.append(_diagnostic("E_SDK_RESOURCE_VALUE", "max_voices must be at least one"))
    tests = manifest.get("tests")
    if not isinstance(tests, list) or not tests or any(not isinstance(item, str) or not item for item in tests):
        diagnostics.append(_diagnostic("E_SDK_TESTS", "tests must name at least one non-empty test vector"))
    return diagnostics


def _element(tag: str, attributes: Optional[Dict[str, str]] = None, text: Optional[str] = None, indent: int = 0) -> str:
    prefix = "   " * indent
    attrs = "".join(f' {key}="{html.escape(value, quote=True)}"' for key, value in (attributes or {}).items())
    if text is None:
        return f"{prefix}<{tag}{attrs}/>"
    return f"{prefix}<{tag}{attrs}>{html.escape(text)}</{tag}>"


def render_axo(manifest: Dict[str, Any]) -> bytes:
    implementation = manifest["implementation"]
    instance = implementation["instance_name"]
    declaration = f'{implementation["class_name"]} {instance};'
    init = f"{instance}.{implementation['init_method']}();"
    arguments = ", ".join(implementation["arguments"])
    process = f"{instance}.{implementation['process_method']}({arguments});"
    lines = [
        '<objdefs appVersion="1.1.0">',
        _element("obj.normal", {"id": manifest["id"], "uuid": manifest["uuid"]}, "", 1)[:-13],
        _element("sDescription", text=manifest["description"], indent=2),
        _element("author", text=manifest["author"], indent=2),
        _element("license", text=manifest["license"], indent=2),
    ]
    for section in ("inlets", "outlets"):
        values = manifest["ports"][section]
        if values:
            lines.append("   " * 2 + f"<{section}>")
            for value in values:
                attributes = {"name": value["name"]}
                if value.get("description"):
                    attributes["description"] = value["description"]
                lines.append(_element(value["type"], attributes, indent=3))
            lines.append("   " * 2 + f"</{section}>")
        else:
            lines.append(_element(section, indent=2))
    parameters = manifest["parameters"]
    if parameters:
        lines.append("   " * 2 + "<params>")
        for parameter in parameters:
            attributes = {"name": parameter["name"]}
            if parameter.get("description"):
                attributes["description"] = parameter["description"]
            lines.append(_element(parameter["type"], attributes, indent=3))
        lines.append("   " * 2 + "</params>")
    else:
        lines.append(_element("params", indent=2))
    lines.extend(
        [
            _element("attribs", indent=2),
            "      <includes>",
            _element("include", text=f'./{implementation["header"]}', indent=3),
            "      </includes>",
            "      <code.declaration><![CDATA[" + declaration + "]]></code.declaration>",
            "      <code.init><![CDATA[" + init + "]]></code.init>",
            f"      <code.{implementation['rate']}><![CDATA[" + process + f"]]></code.{implementation['rate']}>",
            "   </obj.normal>",
            "</objdefs>",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def manifest_report(path: Path) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    try:
        manifest = load_manifest(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "manifest": str(path),
            "diagnostics": [_diagnostic("E_SDK_INPUT", str(exc))],
        }, None
    diagnostics = validate_manifest(manifest, path.parent)
    rendered = render_axo(manifest) if not diagnostics else b""
    return {
        "ok": not diagnostics,
        "manifest": str(path),
        "stable_id": manifest.get("stable_id", ""),
        "axo_sha256": hashlib.sha256(rendered).hexdigest() if rendered else "",
        "resources": manifest.get("resources", {}),
        "tests": manifest.get("tests", []),
        "diagnostics": diagnostics,
    }, manifest
