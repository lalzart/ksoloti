// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <math.h>
#include <stdint.h>

class KsolotiExtendedDripWaterDSP {
public:
    void Init() {
        state_ = 1;
        seed_tag_ = INT32_MIN;
        previous_trigger_ = false;
        burst_ = 0;
        for (int i = 0; i < 3; ++i) y1_[i] = y2_[i] = 0.0f;
    }
    void Process(int32_t trigger, int32_t activity_in, int32_t activity, int32_t damping,
                 int32_t brightness, int32_t spread, int32_t seed,
                 int32_t* output, int32_t* aux, int size) {
        if (seed != seed_tag_) Seed(seed);
        const bool high = trigger > 0;
        if (high && !previous_trigger_) burst_ = 192;
        previous_trigger_ = high;
        const float density = Unit(SaturatingAdd(activity, activity_in));
        const float colour = Unit(brightness);
        const float stereo = Unit(spread);
        const float radius = 0.985f + Unit(damping) * 0.0145f;
        const float base[3] = {430.0f, 730.0f, 1190.0f};
        float coefficient[3];
        for (int mode = 0; mode < 3; ++mode) {
            const float frequency = base[mode] * (0.65f + colour * (0.8f + mode * 0.35f));
            coefficient[mode] = 2.0f * radius * cosf(6.28318530717958647692f * frequency / 48000.0f);
        }
        for (int sample = 0; sample < size; ++sample) {
            float impulse = 0.0f;
            const uint32_t chance = static_cast<uint32_t>(density * density * 1500000.0f);
            if (burst_ > 0 || (Next() & 0x00ffffff) < chance) {
                const float random = static_cast<float>(Next() & 0xffff) * (1.0f / 65535.0f);
                impulse = (0.04f + random * 0.22f) * (burst_ > 0 ? 1.0f : density);
                if (burst_ > 0) --burst_;
            }
            float left = 0.0f;
            float right = 0.0f;
            for (int mode = 0; mode < 3; ++mode) {
                const float mode_impulse = impulse * (1.0f - mode * 0.22f);
                const float y = mode_impulse + coefficient[mode] * y1_[mode] - radius * radius * y2_[mode];
                y2_[mode] = y1_[mode];
                y1_[mode] = y;
                const float pan = (mode - 1) * 0.35f * stereo;
                left += y * (0.5f - pan);
                right += y * (0.5f + pan);
            }
            output[sample] = ToQ27(left * 0.6f);
            aux[sample] = ToQ27(right * 0.6f);
        }
    }
private:
    static float Unit(int32_t x) { if (x <= 0) return 0.0f; if (x >= 0x08000000) return 1.0f; return x * (1.0f / 134217728.0f); }
    static int32_t SaturatingAdd(int32_t a, int32_t b) { const int64_t x = static_cast<int64_t>(a) + b; if (x <= 0) return 0; if (x >= 0x08000000) return 0x07ffffff; return static_cast<int32_t>(x); }
    static int32_t ToQ27(float x) { if (x >= 1.0f) return 0x07ffffff; if (x <= -1.0f) return -0x08000000; return static_cast<int32_t>(x * 134217728.0f); }
    void Seed(int32_t seed) { seed_tag_ = seed; state_ = static_cast<uint32_t>(seed) ^ UINT32_C(0x6a09e667); if (!state_) state_ = 1; }
    uint32_t Next() { uint32_t x = state_; x ^= x << 13; x ^= x >> 17; x ^= x << 5; return state_ = x; }
    uint32_t state_;
    int32_t seed_tag_;
    bool previous_trigger_;
    int burst_;
    float y1_[3];
    float y2_[3];
};
