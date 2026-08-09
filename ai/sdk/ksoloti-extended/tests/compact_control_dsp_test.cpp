// SPDX-License-Identifier: GPL-3.0-or-later
#include <assert.h>
#include <stdint.h>

#include "../objects/extended/control/keyframes_4_dsp.h"
#include "../objects/extended/modulation/segment_6_dsp.h"
#include "../objects/extended/modulation/bounce_dsp.h"
#include "../objects/extended/random/pulse_randomizer_dsp.h"
#include "../objects/extended/random/smooth_random_dsp.h"
#include "../objects/extended/timing/adaptive_clock_dsp.h"

int main() {
    const int32_t half = INT32_C(1) << 26;
    int32_t a = 0, b = 0, c = 0, d = 0, index = 0;
    KsolotiExtendedKeyframes4DSP keyframes;
    keyframes.Init();
    keyframes.Process(1, 0, 0, half, half, 0, 0, 0, 2, 0, a, b, c, d, index);
    keyframes.Process(0, 0, 0, 0, 0, 0, 0, 0, 2, 0, a, b, c, d, index);
    keyframes.Process(1, 0, half, 0, 0, half, 0, 1, 2, 0, a, b, c, d, index);
    keyframes.Process(0, 0, 0, 0, 0, 0, half, 0, 2, 0, a, b, c, d, index);
    assert(a > 0 && a < half && b > 0 && b < half);

    KsolotiExtendedSegment6DSP segments;
    segments.Init();
    bool event = false;
    segments.Process(1, 0, 0, half, half, half, half, half, 0,
        0, 0, 0, 0, 0, 0, 0, 5, 0, a, event, index, 16);
    assert(a >= 0 && index >= 0 && index < 6);

    KsolotiExtendedBounceDSP bounce;
    bounce.Init();
    bool active = false;
    bounce.Process(1, half, half, half, a, event, active, 16);
    assert(active && a > 0);

    KsolotiExtendedPulseRandomizerDSP pulses;
    pulses.Init();
    bool pulse = false;
    pulses.Process(1, 0, 0x07ffffff, 0, 0, 7, pulse, a);
    assert(pulse);

    KsolotiExtendedSmoothRandomDSP smooth1, smooth2;
    smooth1.Init(); smooth2.Init();
    for (int i = 0; i < 64; ++i) {
        smooth1.Process(i == 0, 0, half, half, 99, 1, a, b, 16);
        smooth2.Process(i == 0, 0, half, half, 99, 1, c, d, 16);
        assert(a == c && b == d);
    }

    KsolotiExtendedAdaptiveClockDSP clock;
    clock.Init();
    bool locked = false;
    for (int i = 0; i < 100; ++i) clock.Process(i == 0, 0, 0, half, event, a, locked, 16);
    clock.Process(1, 0, 0, half, event, a, locked, 16);
    assert(locked);
    return 0;
}
