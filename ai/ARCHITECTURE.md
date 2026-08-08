# AI authoring architecture

## Baseline and invariants

- Base development on the official Ksoloti `1.1.0` tag.
- Preserve `.axo`, `.axs`, and `.axp` compatibility while the new path matures.
- Keep semantic graph data independent from Swing components and canvas layout.
- Resolve objects by library, canonical ID, and stable legacy UUID.
- Make generated intermediate artifacts deterministic and content-addressed.
- Keep device upload, SD writes, and flashing outside the AI authoring path.
- Treat AI-authored native C++ as trusted code, not sandboxed code.
- Report structural, host, ARM, board, and audible evidence separately.

## Staged data flow

```text
compact .kpatch
    -> parser
    -> immutable Patch IR
    -> catalog candidate resolver
    -> deterministic graph-constraint solver
    -> graph/type validator
    -> deterministic legacy-order/layout adapter
    -> legacy .axp backend
    -> headless 1.1.0 Java code generator
    -> ARM compile/link
    -> optional connected-board profiling
```

The current implementation reaches deterministic `.axp` generation, semantic
re-import, headless C++ generation, and Cortex-M4 compile/link. It reuses the
authenticated 1.1.0 Java generator as a backend; it does not claim a second
independent C++ generator. The Python Patch IR is UI-independent and is shared
by the CLI and read-only service. Later stages must extend the same report
instead of silently promoting earlier evidence.

## Patch source v1

The line-oriented source is deliberately small. Quoting follows shell quoting,
and `#` begins a comment.

```kpatch
kpatch 1
patch minimal-sine
target ksoloti-core@1.1.0
node osc axoloti-factory:osc/sine
node out "axoloti-factory:audio/out stereo"
param osc.pitch 0
connect osc.wave -> out.left,out.right
assert startup=silent
```

The parser normalizes this into the JSON representation described by
`schemas/patch-v1.schema.json`. Node declaration order is the explicit legacy
execution order. Layout is otherwise absent; the backend projects that order
onto deterministic coordinates whose position sort is identical. The Patcher's
global "sort by execution" preference can still replace position order, just as
it can for hand-authored patches. A future `.klayout` file can replace the
generated canvas arrangement without changing the graph or declared order.

An optional fourth node token preserves a legacy instance label that is unsafe
as a compact graph identifier:

```text
node dac_1 "axoloti-factory:audio/out stereo@UUID" "dac~_1"
```

An object reference has this form:

```text
library:canonical/object/id@legacy-uuid
```

The UUID suffix may be omitted when the catalog contains one matching variant,
or when explicit parameter/attribute names and values plus graph port/type
constraints produce exactly one complete assignment. Zero or multiple valid
assignments fail closed; library order and GUI selection are never tie-breakers.
Multiline attribute text is encoded as a JSON string behind the `json:` prefix
so the line-oriented source remains unambiguous.

Patch settings use `setting`; parameter MIDI/parent/preset metadata uses
`parammeta`; preset entries use `preset`; and modulation assignments use
`modulate`. All are normalized into schema-validated IR and included in the
semantic signature rather than carried as opaque XML.

Typed attributes always refer to a declared node. For example:

```text
node adc axoloti-factory:gpio/in/analog
attr adc.channel 'PC0 (ADC1_IN10)'
```

## Catalog v1

The catalog importer reads existing `.axo` files without evaluating their C or
C++ code. It records:

- canonical object ID and exact legacy variant UUID;
- current SHA and every declared historical `upgradeSha` identity;
- source path and SHA-256 digests;
- descriptions, authors, and declared licenses;
- inlet, outlet, parameter, and typed attribute signatures, including combo
  choices and integer bounds;
- declared include/dependency names; and
- which legacy code sections are present.

Search responses return compact signatures, never entire CDATA implementations.
The catalog does not yet claim parameter units, CPU cost, memory use, safety, or
behavior because legacy `.axo` files do not carry reliable contracts for those
properties.

## Legacy compatibility contract

The `.axp` importer and backend preserve the represented semantic surface:

- ordered direct object instances and exact resolved variants;
- numeric parameter values, mapped from definition tags to the instance tags
  accepted by the 1.1.0 SimpleXML unions;
- patch settings, MIDI CC mappings, parent exposure, presets, and modulation
  assignments;
- typed combo, integer, object-reference, table, file, and text attribute
  values, with object references normalized to compact node IDs; and
- one-source nets with ordered nodes and normalized edges.

Legacy object resolution is UUID first, then current/historical SHA, then
canonical type candidates. Ambiguous candidates are filtered only by explicit
serialized parameter and attribute contracts, named endpoints, and declared
type conversions; one remaining complete assignment is required. Conflicting
identities and residual ambiguity are errors. Canvas annotations are reported
as omitted UI metadata. Anything that can alter runtime meaning but is not
modeled—principally nested/embedded patcher object families and zombies—is
rejected.

## Validation ladder

1. **Structural:** source parses, objects resolve without an ambiguous overload,
   typed values validate, endpoints exist, conversions are supported, and every
   inlet has at most one driver.
2. **Legacy generation:** normalized IR emits deterministic `.axp`, the real
   Java model deserializes it, and re-import has the same semantic signature.
3. **Target:** the complete Cortex-M4 patch compiles and links against 1.1.0.
4. **Host behavior:** explicit harnesses check finite output, bounds, state,
   transitions, and reproducibility where portable code permits it.
5. **Board:** connected hardware measures load, overruns, stack, controls, and
   electrical behavior.
6. **Audible:** a human evaluates level, balance, artifacts, and musical value.

No earlier stage substitutes for a later one.

## Seven workstreams and current status

1. **Reproducible fork:** personal `origin`, official read-only `upstream`, exact
   1.1.0 commit, deterministic fixtures, contract checks, and CI are recorded.
2. **Semantic authoring core:** compact source, immutable normalized IR,
   deterministic catalog, exact overload solver, schemas, and evidence records
   are implemented independently of Swing.
3. **Offline compiler:** `-compileOnly` enters before Swing, singleton startup,
   queues, or USB; it waits for actual library loading and emits C++/binary
   hashes plus linker memory evidence.
4. **Legacy coverage:** `.axo` cataloging and `.axp` import/emission preserve the
   modeled runtime semantics and fail closed at unmodeled object families.
5. **Object SDK:** validated manifests, stable IDs, thin generated glue,
   resource declarations, required test names, and a target-built reference
   object are implemented.
6. **Agent surfaces:** compact inspect/explain/diff/read-only-repair operations
   and a loopback-only read-only service share the semantic core. No device
   operation is exposed.
7. **Firmware ABI v1:** an offset-based, fixed-layout header for stable IDs,
   timestamped events, descriptors, and telemetry is compile-checked but
   intentionally dormant and not included by firmware.

The largest remaining architectural extraction is a Java compiler module that
has no dependency on `MainFrame` statics at all. The present headless route
avoids constructing the UI but still adapts to legacy static object-library
ownership for compatibility.
