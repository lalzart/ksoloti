// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiExtendedSmoothRandomDSP {
public:
    void Init() { state_ = 1; seed_tag_ = INT32_MIN; from_ = to_ = phase_ = 0.0f; previous_clock_ = false; }
    void Process(int32_t clock, int32_t reset, int32_t rate, int32_t smooth, int32_t seed, int32_t clocked,
                 int32_t& output, int32_t& raw, int size) {
        if (seed != seed_tag_ || reset > 0) Seed(seed);
        const bool high = clock > 0;
        const bool edge = high && !previous_clock_;
        previous_clock_ = high;
        if (clocked) {
            if (edge) NewTarget();
            phase_ += (1.0f - phase_) * (0.02f + Unit(smooth) * 0.48f);
        } else {
            const float hz = 0.01f + Unit(rate) * Unit(rate) * 19.99f;
            phase_ += hz * static_cast<float>(size) / 48000.0f;
            if (phase_ >= 1.0f) { phase_ -= 1.0f; NewTarget(); }
        }
        float x = phase_;
        const float s = x * x * (3.0f - 2.0f * x);
        x += (s - x) * Unit(smooth);
        output = ToQ27(from_ + (to_ - from_) * x);
        raw = ToQ27(to_);
    }
private:
    static float Unit(int32_t x) { if (x <= 0) return 0.0f; if (x >= 0x08000000) return 1.0f; return x * (1.0f / 134217728.0f); }
    static int32_t ToQ27(float x) { if (x >= 1.0f) return 0x07ffffff; if (x <= -1.0f) return -0x08000000; return static_cast<int32_t>(x * 134217728.0f); }
    void Seed(int32_t seed) { seed_tag_ = seed; state_ = static_cast<uint32_t>(seed) ^ UINT32_C(0x3c6ef372); if (!state_) state_ = 1; from_ = 0.0f; to_ = RandomBipolar(); phase_ = 0.0f; }
    uint32_t Next() { uint32_t x = state_; x ^= x << 13; x ^= x >> 17; x ^= x << 5; return state_ = x; }
    float RandomBipolar() { return static_cast<int32_t>(Next() >> 1) * (1.0f / 1073741824.0f) - 1.0f; }
    void NewTarget() { from_ = from_ + (to_ - from_) * phase_; to_ = RandomBipolar(); phase_ = 0.0f; }
    uint32_t state_;
    int32_t seed_tag_;
    float from_;
    float to_;
    float phase_;
    bool previous_clock_;
};
