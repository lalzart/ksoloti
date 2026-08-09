// SPDX-License-Identifier: GPL-3.0-or-later
#include <assert.h>
#include <cmath>
#include <stdint.h>

#include "pitch_amdf_dsp.h"

static void Feed(KsolotiExtendedPitchAMDFAudioDSP& tracker, double frequency, double amplitude,
                 int samples, int32_t& pitch, int32_t& level, int32_t& confidence, bool& valid) {
    int32_t block[16];
    static double phase = 0.0;
    for (int offset = 0; offset < samples; offset += 16) {
        for (int i = 0; i < 16; ++i) {
            block[i] = static_cast<int32_t>(std::sin(phase) * amplitude * 134217728.0);
            phase += 6.28318530717958647692 * frequency / 48000.0;
            if (phase >= 6.28318530717958647692) phase -= 6.28318530717958647692;
        }
        tracker.Process(block, 50, 1200, INT32_C(1) << 20, INT32_C(1) << 23, 0,
                        pitch, level, confidence, valid, 16);
    }
}

int main() {
    KsolotiExtendedPitchAMDFAudioDSP tracker;
    tracker.Init();
    int32_t pitch = 0, level = 0, confidence = 0;
    bool valid = false;
    Feed(tracker, 0.0, 0.0, 24000, pitch, level, confidence, valid);
    assert(!valid && level == 0 && confidence == 0);

    Feed(tracker, 440.0, 0.5, 48000, pitch, level, confidence, valid);
    assert(valid);
    assert(std::abs(pitch - (INT32_C(5) << 21)) < (INT32_C(2) << 21));
    Feed(tracker, 220.0, 0.5, 48000, pitch, level, confidence, valid);
    assert(valid);
    assert(std::abs(pitch + (INT32_C(7) << 21)) < (INT32_C(2) << 21));
    int32_t quiet[16] = {};
    for (int i = 0; i < 1000; ++i) {
        tracker.Process(quiet, 50, 1200, INT32_C(1) << 24, INT32_C(1) << 23, 0,
                        pitch, level, confidence, valid, 16);
    }
    assert(!valid);
    const int32_t retained = pitch;
    for (int i = 0; i < 100; ++i) {
        tracker.Process(quiet, 50, 1200, INT32_C(1) << 24, INT32_C(1) << 23, 0,
                        pitch, level, confidence, valid, 16);
    }
    assert(pitch == retained);
    assert(confidence >= 0 && confidence <= 0x07ffffff);
    return 0;
}
