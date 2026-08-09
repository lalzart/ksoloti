# License and attribution

Except where noted below, the Ksoloti Extended Library source is:

Copyright (c) 2026 Lance Ship

SPDX-License-Identifier: GPL-3.0-or-later

You may redistribute and modify it under the terms of the GNU General Public
License, version 3 or (at your option) any later version. The complete GPL-3.0
text is available in the Ksoloti repository `license.txt`.

## Physical resonator

`extended/physical/physical_resonator_dsp.h` is a GPL-3.0-or-later Ksoloti
wrapper around the Rings DSP carried in `firmware/mutable_instruments/rings`.
That DSP was written by Emilie Gillet and is distributed under the MIT License.
Its copyright and license notices remain in the included firmware source.

## Topographic sequencer

`extended/sequencing/topographic_patterns.h` contains pattern-map data derived
from Mutable Instruments Grids by Emilie Gillet. The source data and the
topographic sequencer wrapper are distributed under GPL-3.0-or-later.

## Complete macro voice

`extended/synthesis/vendor/` contains the DSP and generated resources from
Mutable Instruments Plaits by Emilie Gillet, distributed under the MIT License.
The exact eurorack and stmlib commit IDs, mechanical namespace isolation, and
48 kHz adaptation are recorded in that directory's `README.md`. The
`macro_voice_dsp.h` Ksoloti wrapper is GPL-3.0-or-later.

Mutable Instruments is a registered trademark. It is used here only for
attribution and source identification, not as the name of this library or its
objects.
