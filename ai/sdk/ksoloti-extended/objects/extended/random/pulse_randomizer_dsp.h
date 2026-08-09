// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiExtendedPulseRandomizerDSP {
public:
    void Init() { state_ = 1; seed_tag_ = INT32_MIN; previous_clock_ = false; remaining_ = 0; value_ = 0; }
    void Process(int32_t clock, int32_t reset, int32_t probability, int32_t width, int32_t variation, int32_t seed,
                 bool& pulse, int32_t& value) {
        if (seed != seed_tag_ || reset > 0) Seed(seed);
        const bool high = clock > 0;
        if (high && !previous_clock_) {
            const uint32_t random = Next();
            value_ = static_cast<int32_t>((random >> 5) & 0x07ffffff);
            if ((Next() >> 5) < ClampUnit(probability)) {
                const int base = 1 + static_cast<int>((static_cast<uint64_t>(ClampUnit(width)) * 31) >> 27);
                const int spread = static_cast<int>((static_cast<uint64_t>(ClampUnit(variation)) * base) >> 28);
                const int offset = spread ? static_cast<int>(Next() % (spread * 2 + 1)) - spread : 0;
                remaining_ = base + offset;
                if (remaining_ < 1) remaining_ = 1;
            }
        }
        previous_clock_ = high;
        pulse = remaining_ > 0;
        if (remaining_ > 0) --remaining_;
        value = value_;
    }
private:
    static uint32_t ClampUnit(int32_t x) { if (x <= 0) return 0; if (x >= 0x08000000) return UINT32_C(1) << 27; return static_cast<uint32_t>(x); }
    void Seed(int32_t seed) { seed_tag_ = seed; state_ = static_cast<uint32_t>(seed) ^ UINT32_C(0xa511e9b3); if (!state_) state_ = 1; remaining_ = 0; }
    uint32_t Next() { uint32_t x = state_; x ^= x << 13; x ^= x >> 17; x ^= x << 5; return state_ = x; }
    uint32_t state_;
    int32_t seed_tag_;
    bool previous_clock_;
    int remaining_;
    int32_t value_;
};
