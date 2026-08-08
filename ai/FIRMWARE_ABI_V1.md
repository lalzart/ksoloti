# Dormant patch ABI v1

`firmware/patch_abi_v1.h` is a compile-checked design contract. It is not
included by the 1.1.0 firmware, does not extend `patchMeta_t`, does not alter the
linker map or USB protocol, and cannot affect a currently generated patch.

The contract gives a future shell or panel controller four stable primitives:

- 128-bit patch and parameter identities generated from Object SDK identities,
  rather than fragile parameter-array indexes;
- fixed-size parameter descriptors with exact numeric bounds and flags;
- a fixed-size, timestamped event ring whose `frame_offset` is relative to the
  next DSP block; and
- bounded telemetry counters for dropped/late events, queue depth, ABI errors,
  and processing cycles.

The root structure contains 32-bit offsets rather than native pointers. That
makes the binary layout independent of host pointer width, relocatable as one
blob, and easy to validate with `byte_size` before dereferencing anything. All
structures have compile-time size assertions.

## Compatibility and negotiation

A future implementation should preserve the existing 1.1.0 patch initializer
and `patchMeta_t`. Firmware may look for an optional, separately located ABI
advertisement only after the legacy initializer succeeds. It must require the
magic value, major version 1, a supported minor version, aligned in-bounds
offsets, unique 128-bit IDs, a power-of-two event capacity, and non-overlapping
regions. If any check fails, the firmware must ignore the advertisement and
continue through the legacy path.

The ring is intended for one producer and one consumer. The contract specifies
monotonic sequence locations but deliberately leaves memory barriers and
interrupt policy to the firmware integration. Events with invalid IDs or frame
offsets must be rejected and counted, never redirected by parameter order.

## Evidence boundary

The present evidence is host compilation of the C layout and static size
assertions only. Queue correctness, cycle cost, firmware compatibility,
controller behavior, board stability, timing, and audible results are all
`not_run`. Activating this ABI requires a separately reviewed firmware change
and explicit permission before flashing any board.
