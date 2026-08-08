# Object SDK v1

The Object SDK separates what an agent may describe from the C++ that runs in a
DSP block.

```text
object manifest -> contract validator -> deterministic thin .axo glue
DSP header --------------------------------------------^ -> ARM compile/link
```

The manifest schema requires:

- a globally stable object ID, legacy object ID, and UUID;
- typed inlet, outlet, and parameter contracts;
- a DSP header, class, instance, initialization method, processing method,
  rate, and ordered generated arguments;
- declared maximum voices, state bytes, scratch bytes, and bounded operations
  per block; and
- named behavior tests.

The glue generator accepts only C/C++ identifiers and a closed set of generated
argument names such as `inlet_in`, `outlet_out`, `param_level`, and `BUFSIZE`.
It rejects arbitrary expressions in those fields. This is an injection barrier
for glue generation, not a sandbox for the included DSP header; native DSP code
remains trusted and must be reviewed.

The example under `sdk/example-library/objects/ai/` demonstrates the intended
shape. Its DSP loop has a fixed block bound, uses fixed-point arithmetic, makes
no allocation, and saturates its output. The committed `.axo` must be byte-for-
byte equal to regenerated glue, and its example patch must pass the target
compiler before the object is considered target-compatible.

## Stable parameter identity

Each parameter has a textual stable ID independent of object order or the
legacy `ParameterExchange_t` index. A future packaging step should derive the
128-bit firmware ABI identity from that UTF-8 string with one specified digest
and namespace rule, retain the source string in build evidence, and reject any
duplicate binary identity. That derivation is intentionally not activated in
firmware yet.

## Required promotion gates

1. Manifest and schema validation.
2. Deterministic glue equality.
3. Catalog resolution and patch structural validation.
4. Cortex-M4 compile/link and budget report.
5. Portable behavior tests where the DSP can be isolated.
6. Connected-board profiling and control tests.
7. Audible evaluation.

Passing an earlier gate never promotes a later evidence class.
