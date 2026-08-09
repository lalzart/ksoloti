// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiExtendedCombNetworkDSP {
public:
    void Init() {
        for (int line = 0; line < kLines; ++line) {
            write_[line] = 0; lowpass_[line] = 0.0f;
            for (int i = 0; i < kCapacity; ++i) delay_[line][i] = 0.0f;
        }
    }
    void Process(const int32_t* input, int32_t size_control, int32_t feedback,
                 int32_t damping, int32_t spread, int32_t mix,
                 int32_t* left, int32_t* right, int size) {
        const float room = 0.45f + Unit(size_control) * 0.54f;
        const float fb = Unit(feedback) * 0.93f;
        const float damp = 0.02f + Unit(damping) * 0.48f;
        const float stereo = Unit(spread);
        const float wet = Unit(mix);
        const int base[kLines] = {601, 733, 877, 997};
        for (int i = 0; i < size; ++i) {
            const float dry = Bipolar(input[i]);
            float taps[kLines];
            for (int line = 0; line < kLines; ++line) {
                int delay = static_cast<int>(base[line] * room);
                if (delay < 32) delay = 32;
                const int read = (write_[line] - delay) & (kCapacity - 1);
                taps[line] = delay_[line][read];
                lowpass_[line] += (taps[line] - lowpass_[line]) * damp;
            }
            for (int line = 0; line < kLines; ++line) {
                const float nested = taps[(line + 1) & 3] - taps[(line + 3) & 3];
                delay_[line][write_[line]] = dry * 0.3f + (lowpass_[line] + nested * 0.16f) * fb;
                write_[line] = (write_[line] + 1) & (kCapacity - 1);
            }
            const float l = (taps[0] + taps[2]) * 0.45f + (taps[1] - taps[3]) * 0.3f * stereo;
            const float r = (taps[1] + taps[3]) * 0.45f + (taps[0] - taps[2]) * 0.3f * stereo;
            left[i] = ToQ27(dry + (l - dry) * wet);
            right[i] = ToQ27(dry + (r - dry) * wet);
        }
    }
private:
    static const int kLines = 4, kCapacity = 1024;
    static float Unit(int32_t x) { if (x <= 0) return 0.0f; if (x >= 0x08000000) return 1.0f; return x * (1.0f / 134217728.0f); }
    static float Bipolar(int32_t x) { return x * (1.0f / 134217728.0f); }
    static int32_t ToQ27(float x) { if (x >= 1.0f) return 0x07ffffff; if (x <= -1.0f) return -0x08000000; return static_cast<int32_t>(x * 134217728.0f); }
    float delay_[kLines][kCapacity];
    int write_[kLines];
    float lowpass_[kLines];
};
