# Plaits DSP snapshot

This directory contains the MIT-licensed DSP portion of Mutable Instruments
Plaits at eurorack commit `08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4`
with stmlib commit `e3bd7c9cc00e4364166f9905c0509b6ffd0535ec`.

Only DSP, resources, and the null test user-data provider are included. The
stmlib namespace and include guards are mechanically isolated as
`plaits_stmlib` / `PLAITSLIB_` so this snapshot can coexist with the older
stmlib already prelinked by Ksoloti. Internal include paths are relative to the
snapshot. `kCorrectedSampleRate` is set to Ksoloti's 48 kHz callback rate.

The original MIT notices remain in every source file. Mutable Instruments and
Plaits are used here only to identify upstream source and are not library or
object product names.
