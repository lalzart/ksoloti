// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiExtendedProbabilityRouterDSP {
public:
    void Init() {
        state_ = UINT32_C(0x6d2b79f5);
        seed_tag_ = INT32_MIN;
        previous_trigger_ = false;
        choice_ = false;
    }

    void Process(
        int32_t trigger,
        int32_t probability,
        int32_t seed,
        bool& out_a,
        bool& out_b,
        bool& out_choice) {
        if (seed != seed_tag_) {
            Seed(seed);
        }

        out_a = false;
        out_b = false;
        const bool high = trigger > 0;
        if (high && !previous_trigger_) {
            const uint32_t threshold = ClampUnit(probability);
            choice_ = (Next() >> 5) < threshold;
            out_a = choice_;
            out_b = !choice_;
        }
        previous_trigger_ = high;
        out_choice = choice_;
    }

private:
    static uint32_t ClampUnit(int32_t value) {
        if (value <= 0) return 0;
        if (value >= (INT32_C(1) << 27)) return UINT32_C(1) << 27;
        return static_cast<uint32_t>(value);
    }

    void Seed(int32_t seed) {
        seed_tag_ = seed;
        state_ = static_cast<uint32_t>(seed) ^ UINT32_C(0x9e3779b9);
        if (state_ == 0) state_ = UINT32_C(0x6d2b79f5);
    }

    uint32_t Next() {
        uint32_t value = state_;
        value ^= value << 13;
        value ^= value >> 17;
        value ^= value << 5;
        state_ = value;
        return value;
    }

    uint32_t state_;
    int32_t seed_tag_;
    bool previous_trigger_;
    bool choice_;
};
