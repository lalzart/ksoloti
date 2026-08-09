// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiExtendedLoopMutateDSP {
public:
    void Init() {
        state_ = UINT32_C(0x6d2b79f5);
        seed_tag_ = INT32_MIN;
        position_ = 0;
        previous_clock_ = false;
        previous_reset_ = false;
        for (int i = 0; i < kMaximumLength; ++i) memory_[i] = 0;
    }

    void Process(
        int32_t clock,
        int32_t reset,
        int32_t memory,
        int32_t spread,
        int32_t bias,
        int32_t length,
        int32_t seed,
        int32_t& out_value,
        bool& out_fresh,
        int32_t& out_step) {
        if (seed != seed_tag_) Seed(seed);

        const bool reset_high = reset > 0;
        if (reset_high && !previous_reset_) position_ = 0;
        previous_reset_ = reset_high;

        out_fresh = false;
        const bool clock_high = clock > 0;
        const int active_length = ClampLength(length);
        if (clock_high && !previous_clock_) {
            position_ = (position_ + 1) % active_length;
            const uint32_t recycle = ClampUnit(memory);
            const bool reuse = (Next() >> 5) < recycle;
            if (!reuse) {
                memory_[position_] = NextBipolar();
                out_fresh = true;
            }
        }
        previous_clock_ = clock_high;

        out_value = Shape(memory_[position_], spread, bias);
        out_step = position_;
    }

private:
    static const int kMaximumLength = 16;

    static int ClampLength(int value) {
        if (value < 1) return 1;
        if (value > kMaximumLength) return kMaximumLength;
        return value;
    }

    static uint32_t ClampUnit(int32_t value) {
        if (value <= 0) return 0;
        if (value >= (INT32_C(1) << 27)) return UINT32_C(1) << 27;
        return static_cast<uint32_t>(value);
    }

    static int32_t Shape(int32_t raw, int32_t spread, int32_t bias) {
        const int32_t spread_clamped = static_cast<int32_t>(ClampUnit(spread));
        int64_t value = (static_cast<int64_t>(raw) * spread_clamped) >> 27;
        value += bias;
        if (value > 0x07ffffff) value = 0x07ffffff;
        if (value < -0x08000000) value = -0x08000000;
        return static_cast<int32_t>(value);
    }

    void Seed(int32_t seed) {
        seed_tag_ = seed;
        state_ = static_cast<uint32_t>(seed) ^ UINT32_C(0x9e3779b9);
        if (state_ == 0) state_ = UINT32_C(0x6d2b79f5);
        for (int i = 0; i < kMaximumLength; ++i) memory_[i] = NextBipolar();
        position_ = 0;
    }

    uint32_t Next() {
        uint32_t value = state_;
        value ^= value << 13;
        value ^= value >> 17;
        value ^= value << 5;
        state_ = value;
        return value;
    }

    int32_t NextBipolar() {
        return static_cast<int32_t>(Next()) >> 4;
    }

    int32_t memory_[kMaximumLength];
    uint32_t state_;
    int32_t seed_tag_;
    int position_;
    bool previous_clock_;
    bool previous_reset_;
};
