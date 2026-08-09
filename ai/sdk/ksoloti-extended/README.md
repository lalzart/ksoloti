# Ksoloti Extended Library

This is a separate object library for Ksoloti 1.1.0. It does not replace or
modify the installed factory, Ksoloti, or community libraries.

The library currently contains 19 objects:

| Object | Function | Tier | Offline build status |
|---|---|---|---|
| `analysis/pitch-amdf` | monophonic AMDF pitch, level, confidence, and validity | Core-heavy | verified |
| `control/keyframes-4` | record and morph up to eight four-channel scenes | Core | verified |
| `effects/comb-network` | four nested cross-coupled feedback comb lines | Core-heavy | verified |
| `effects/talkbox-lpc` | 4th-to-12th-order LPC cross-synthesis | Core-heavy | verified |
| `effects/waveset-repeat` | bounded zero-crossing waveset capture and repeat | Core-heavy | verified |
| `grain/clocked-delay` | clocked four-voice granular delay and freeze | H7 recommended | verified; 97.73% CCMSRAM in the full recipe |
| `grain/seeded-scatter` | seeded four-voice recent-audio grain scattering | Core-heavy | verified |
| `modulation/bounce` | bouncing-ball generator with impact pulses | Core | verified |
| `modulation/poly-slope` | four phase-related shaped modulation outputs | Core | verified |
| `modulation/segment-6` | chained ramp, hold, step, sustain, and loop segments | Core | verified |
| `physical/drip-water` | seeded three-resonator water-droplet model | Core | verified |
| `physical/resonator` | modal, sympathetic, and dispersive string processing | Core-heavy | verified |
| `random/loop-mutate` | seeded random memory from fresh stream to locked loop | Core | verified |
| `random/probability-router` | complementary seeded probability routing | Core | verified |
| `random/pulse-randomizer` | probability, width, and variation for clock pulses | Core | verified |
| `random/smooth` | free or clocked interpolated seeded random control | Core | verified |
| `sequencing/topographic-3` | three-channel interpolation through a drum-pattern map | Core | verified |
| `synthesis/macro-voice` | complete official 24-engine Plaits DSP | H7 recommended | host verified; Core build failed by code size |
| `timing/adaptive-clock` | smoothed tap-period prediction and clock ratios | Core | verified |

Every object has a validated Object SDK manifest, deterministic generated
`.axo` glue, bounded state/work declarations, compatibility metadata, and a
portable behavior test where its DSP can be isolated. The `compatibility`
record is the authoritative machine-readable tag:

- `core`: small enough for routine Core use;
- `core-heavy`: Core compile/link passed, but CPU or combination profiling is
  important;
- `h7-recommended`: retained in full, with a documented reason to prefer the
  larger target; and
- `reference`: source contract only, without a runnable target claim.

`build_status` records actual evidence separately. An offline-verified tag does
not claim real-time headroom or sound quality.

## Use with the AI authoring tools

Add the library when building a catalog:

```sh
python3 ai/ksai.py catalog build \
  --library axoloti-factory=/path/to/1.1.0/axoloti-factory \
  --library ksoloti-extended=ai/sdk/ksoloti-extended \
  --output /tmp/ksoloti-extended-catalog.json
```

The `examples/` directory contains six higher-level recipes:

- `extended-resonator-system.kpatch`: structured rhythm, memory, modulation,
  probability, and physical resonation;
- `control-scenes.kpatch`: adaptive timing, pulse variation, segment motion,
  bouncing control, scene recording, and a resonator;
- `pitch-follower.kpatch`: external-audio AMDF tracking driving a sine monitor;
- `audio-reactive-macro-voice.kpatch`: tracker-driven complete macro voice,
  retained as the H7/custom-firmware recipe;
- `audio-effects-chain.kpatch`: wavesets into LPC cross-synthesis and a nested
  comb network; and
- `granular-water-system.kpatch`: seeded droplets feeding scatter and clocked
  grain processors.

For an offline target build, expose this separate library to the legacy Java
loader as well as to the catalog builder:

```sh
KSAI_OBJECT_PATHS="$PWD/ai/sdk/ksoloti-extended/objects" \
python3 ai/ksai.py patch build \
  --catalog /tmp/ksoloti-extended-catalog.json \
  --output /tmp/extended-control-scenes.axp \
  ai/sdk/ksoloti-extended/examples/control-scenes.kpatch
```

The target build does not copy the library into the installed 1.1.0 object
directories and does not upload anything to a board.

## Current offline target evidence

| Recipe | CCMSRAM | SRAM1 code | Result |
|---|---:|---:|---|
| Original five-object resonator system | 17.22% | 37.09% | pass |
| Control scenes | 17.89% | 33.51% | pass |
| Pitch follower | 4.94% | 8.91% | pass |
| Audio effects chain | 67.47% | 11.74% | pass |
| Granular water system | 97.73% | 20.09% | pass |
| Pitch follower plus complete macro voice | 54.86% | 417.37% | fail: needs 188048 of 45056 bytes |

The complete macro voice is not reduced to fit the F4. Its 24 official engines
and resources remain available for an H7 port, a custom firmware prelink, or a
future set of explicitly smaller banks.

RNBO Minimal Export remains correctly tagged `reference / source-required` in
`integrations/rnbo-minimal/README.md`: it is an importer contract requiring a
user-supplied licensed export, not a patchable DSP object. The original comb,
granular, and higher-level recipe work is already present in the runnable
library.

## Evidence boundary

Manifest validation, portable tests, catalog resolution, and a Cortex-M4
compile/link are offline evidence. They do not establish connected-board CPU
margin, underrun safety, tracking latency, control feel, output level, or sound
quality. Those remain hardware and listening checks.

## Licensing and names

The library is GPL-3.0-or-later. The physical resonator wrapper uses the
MIT-licensed Rings DSP already carried by Ksoloti. The complete macro voice
vendors an attributed MIT Plaits DSP snapshot. The topographic pattern data is
derived from the GPL-3.0-or-later Grids source. See `LICENSE.md` for details.
Object and library names remain functional; upstream names are used only for
source identification and attribution.
