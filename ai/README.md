# Ksoloti AI authoring

This directory is the compatibility-first AI authoring layer for the personal
Ksoloti fork. It is based on the authenticated upstream `1.1.0` tag and keeps
compact graph semantics, legacy XML, target compilation, device access, and
audible evidence as separate gates.

The implemented path is:

```text
installed 1.1.0 object libraries -> deterministic catalog
compact .kpatch -> resolved Patch IR -> deterministic .axp
                 -> legacy Java model -> generated C++ -> ARM compile/link
```

No command here uploads a patch, connects to USB, writes an SD card, or flashes
firmware. `patch build` ends when the Cortex-M4 binary has linked.

The exact fork and upstream contract are recorded in [BASELINE.md](BASELINE.md).

## Catalog

Build a deterministic catalog from installed libraries:

```sh
python3 ai/ksai.py catalog build \
  --library axoloti-factory=/path/to/1.1.0/axoloti-factory \
  --library ksoloti-objects=/path/to/1.1.0/ksoloti-objects \
  --output /tmp/ksoloti-catalog-v1.json
```

Search returns compact contracts without embedded DSP source. Inspect returns
the exact variants in one object family:

```sh
python3 ai/ksai.py catalog search --catalog /tmp/ksoloti-catalog-v1.json \
  --limit 8 "sine oscillator"
python3 ai/ksai.py catalog inspect --catalog /tmp/ksoloti-catalog-v1.json \
  axoloti-factory:osc/sine
```

## Patches

Validate or emit deterministic 1.1.0 XML:

```sh
python3 ai/ksai.py patch validate --catalog /tmp/ksoloti-catalog-v1.json \
  ai/examples/minimal-sine.kpatch
python3 ai/ksai.py patch emit --catalog /tmp/ksoloti-catalog-v1.json \
  --output /tmp/minimal-sine.axp ai/examples/minimal-sine.kpatch
```

Import a supported legacy patch or prove import, compact-source reparse,
generation, re-import, and semantic equality:

```sh
python3 ai/ksai.py patch import --catalog /tmp/ksoloti-catalog-v1.json \
  --output /tmp/imported.kpatch path/to/input.axp
python3 ai/ksai.py patch roundtrip --catalog /tmp/ksoloti-catalog-v1.json \
  path/to/input.axp
```

Agent-facing operations are deliberately small and structured:

```sh
python3 ai/ksai.py patch explain --catalog /tmp/ksoloti-catalog-v1.json patch.kpatch
python3 ai/ksai.py patch diff --catalog /tmp/ksoloti-catalog-v1.json before.kpatch after.kpatch
python3 ai/ksai.py patch repair --catalog /tmp/ksoloti-catalog-v1.json broken.kpatch
```

`repair` is read-only: it returns conservative candidates and `changed:false`.

Patch settings, MIDI CC mappings, parent exposure, presets, and modulation
assignments have compact directives and round-trip through the normalized IR.
Use `python3 ai/ksai.py patch --help` and the schema in
[`schemas/patch-v1.schema.json`](schemas/patch-v1.schema.json) for the complete
contract.

## Offline target build

Build the Java classes once, then emit and compile/link a patch without USB:

```sh
ant test
python3 ai/ksai.py patch build --catalog /tmp/ksoloti-catalog-v1.json \
  --output /tmp/minimal-sine.axp ai/examples/minimal-sine.kpatch
```

`ai/compile-axp.sh` accepts these environment overrides:

- `KSAI_PATCHER_HOME`: installed 1.1.0 application resources;
- `KSAI_LIBRARIES`: installed library/build root;
- `KSAI_FIRMWARE`: this fork's firmware source;
- `KSAI_LINK_FIRMWARE`: authenticated prebuilt firmware image used for linker
  symbols;
- `KSAI_PLATFORM`: ARM toolchain directory; and
- `KSAI_OBJECT_PATHS`: path-separated additional object libraries.

The machine-readable result includes content hashes, firmware ID, compiler
evidence, artifacts, linker memory regions, and memory usage. The headless Java
entry point runs before Swing, the desktop singleton, command queues, or USB.

## Object SDK

An AI-authored object is split into a validated manifest, a small DSP header,
and generated `.axo` glue:

```sh
python3 ai/ksai.py object validate \
  ai/sdk/example-library/objects/ai/gain.manifest.json
python3 ai/ksai.py object emit \
  --output /tmp/gain.axo \
  ai/sdk/example-library/objects/ai/gain.manifest.json
```

The manifest carries stable identities, typed ports and parameters, declared
resource bounds, and required behavior tests. Glue arguments are identifiers
from a closed grammar, not arbitrary generated C++. The reference gain object
compiles and links through the same target path. See [OBJECT_SDK.md](OBJECT_SDK.md).

## Read-only localhost service

The CLI and service share the catalog, resolver, validator, and explainer:

```sh
python3 ai/ksai.py serve --catalog /tmp/ksoloti-catalog-v1.json \
  --host 127.0.0.1 --port 8765
```

Only health, catalog search/inspect, and patch validate/explain routes exist.
Binding to a non-loopback address is rejected; mutation, compilation, and
device access are absent. See [SERVICE.md](SERVICE.md).

## Validation

Dependency-free checks:

```sh
python3 -m unittest discover -s ai/tests -v
python3 ai/tests/check_docs_examples.py
cc -std=c11 -Wall -Wextra -Werror -I. \
  ai/tests/firmware_abi_v1_compile.c -o /tmp/firmware-abi-v1
c++ -std=c++11 -Wall -Wextra -Werror \
  ai/sdk/example-library/objects/ai/gain_dsp_test.cpp \
  -o /tmp/ksai-gain-dsp-test && /tmp/ksai-gain-dsp-test
```

CI additionally installs `jsonschema`, validates all schemas, builds Java, and
deserializes the golden AXP with the real SimpleXML model. It does not download
object libraries, invoke the proprietary installation's ARM toolchain, or
access USB.

The installed-library corpus audit is reproducible but intentionally local:

```sh
python3 ai/tests/audit_factory_corpus.py \
  --library-root /path/to/ksoloti/1.1.0 \
  --expect-accepted 46 --expect-rejected 27
```

See [ARCHITECTURE.md](ARCHITECTURE.md), [COMPATIBILITY.md](COMPATIBILITY.md),
and [FIRMWARE_ABI_V1.md](FIRMWARE_ABI_V1.md) for the boundaries and evidence.
