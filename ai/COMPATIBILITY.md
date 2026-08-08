# Ksoloti 1.1.0 compatibility envelope

This snapshot records the bounded compatibility evidence for the first legacy
backend. It is not a claim that every historical Ksoloti patch is representable
by kpatch v1.

## Authenticated inputs

- Patcher repository baseline: official `1.1.0` tag at
  `6dd3e7df756bcafe6958ae50b811cb605b4ccd27`.
- Installed libraries: `axoloti-factory`, `ksoloti-objects`,
  `axoloti-contrib`, and `ksoloti-contrib`, each on its `1.1.0` branch with a
  clean worktree.
- Deterministic catalog: 3,414 exact variants, SHA-256
  `c0d5a9cf8312e027da0c9b65bf1c3842551ffc9e63b06feff9b4876d1c5f81f6`.
- Parameter definition-to-instance mapping: zero unmapped parameter types in
  that catalog.
- Typed attribute catalog: 2,273 definitions and zero unsupported attribute
  tags; combo choices and spinner/integer bounds are retained rather than
  reduced to untyped names.

## Positive fixtures

The read-only stock harness passed semantic round-trip for:

- `axoloti-factory/patches/tutorials/01_sine_oscillator.axp`: 6 nodes,
  5 edges, generated AXP SHA-256
  `91ab5d6d6124d323dc61e5bb96d530e6a009abf1cbf1fd8359226580b58d5e38`;
- `axoloti-factory/patches/tutorials/02_keyboard_controlled_sine_oscillator.axp`:
  3 nodes, 3 edges, generated AXP SHA-256
  `01288e0f4efb0f35222a05f324f5c015977d3c17ad679afa93e5178bd0ea7bec`;
- `axoloti-factory/patches/tutorials/12_subtractive_lfo_env.axp`: 12 nodes,
  15 normalized edges, graph-constrained scalar `math/*c` overload, generated
  AXP SHA-256
  `16396f8efd6528675d30dacdfc899fc1c5661199910a5030dab1444e4c146c1e`;
- `axoloti-factory/patches/demos/sensors/physical.axp`: 2 nodes, 1 edge, typed
  GPIO combo attribute, generated AXP SHA-256
  `9119afa184d5ac505651bbe3f34756c792256f1fa8d97f8a62c561d076a843f2`;
- `ai/examples/minimal-sine.kpatch`: byte-identical to the committed golden
  fixture, SHA-256
  `76d9b3fcec52d650da2a7047b06bebbba0c160823e0f45073d02a51c71ffaebf`;
  and
- the contrib `int32.mini` probe, emitted with the Java-compatible
  `<int32.small>` instance tag.

The real 1.1.0 SimpleXML model deserialized the generated minimal patch as two
objects and one net, the generated tutorial 02 patch as three objects and two
nets, the typed seven-kind attribute fixture as two objects and zero nets, the
generated physical patch as two objects and one net, the generated tutorial 12
patch as 12 objects and 12 nets, and the integer mapping probe as one object and
zero nets. The check does not call patch `PostConstructor`, load object libraries,
connect to USB, compile, or run the graph.

The offline compiler then ran the real 1.1.0 object loader, Java patch model,
C++ generator, Cortex-M4 compiler, and linker without constructing Swing or
attempting USB. Two builds of the deterministic minimal fixture produced the
same C++ SHA-256
`7e06fb8bc695ba412bd5b8aafada9a887253c3062b376a3e9488c1b1df708a89`
and binary SHA-256
`6b96b1826f03e759c267a9dad06babed10885e08e6269eb08967cef28ef1d1b1`.
The firmware ID was `5021D42A`; reported use was 308 B of CCMSRAM and 1,216 B
of SRAM1.

The Object SDK gain example also compiled and linked through that path. Its
binary SHA-256 was
`b5057a23204e95ea73171f809a0c6bf9fb1fc587944ee6c02d4d329b261bdbc6`;
reported use was 316 B of CCMSRAM and 1,976 B of SRAM1. These are fixture-level
target results, not general performance or board claims.

## Corpus boundary

A read-only import audit covered all 73 `.axp` files under the installed
`axoloti-factory/patches` tree. Forty-six fit the current semantic subset and
27 were rejected. Every accepted file also passed semantic round-trip. The
compact audit fingerprint was
`74667932f9d964f8b41bba52cc63ee9e06d99df37dbe2a6c55b9d78cff3dceee`.
Rejections were explicit and clustered into the remaining object-family
boundaries:

| Diagnostic | Occurrences |
| --- | ---: |
| `E_AXP_OBJECT_NOT_FOUND` | 34 |
| `E_AXP_NET_ARITY` | 29 |
| `E_AXP_NET_OBJECT` | 29 |
| `E_AXP_OBJECT_KIND_UNSUPPORTED` | 14 |

These are error occurrences, not numbers of distinct files; one file can
exercise several boundaries. The net errors are cascades from rejected nested
or missing object instances. Patch settings, MIDI mappings, parent parameter
exposure, presets, and modulation assignments are now modeled and round-trip
semantically. There were no parser crashes and no accepted file silently
discarded one of those constructs.

As a concrete constrained-resolution control,
`tutorials/12_subtractive_lfo_env.axp` carries an old `math/*c` SHA that is no
longer present in the 1.1.0 identity chain. Its explicit output edge accepts the
scalar overload and rejects the buffer overload, so the importer records that
selection as a warning and round-trips successfully. Unit negative controls
with no discriminating graph still return both exact choices and fail; a graph
that admits zero assignments also fails rather than selecting by library order.

## Unproven layers

This snapshot does not establish full GUI open/save behavior, ARM compilation
of the entire accepted corpus, portable DSP behavior for arbitrary native
objects, real-time scheduling, connected-board behavior, or audible behavior.
The firmware ABI v1 header is dormant: its host layout compiles, but firmware
negotiation, event-ring correctness, and timing are not implemented or tested.
