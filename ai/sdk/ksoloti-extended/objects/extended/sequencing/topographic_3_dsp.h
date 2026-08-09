// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

#include "topographic_patterns.h"

class KsolotiExtendedTopographic3DSP {
public:
    void Init() {
        state_ = UINT32_C(0x6d2b79f5);
        seed_tag_ = INT32_MIN;
        step_ = 0;
        previous_clock_ = false;
        previous_reset_ = false;
        perturbation_[0] = perturbation_[1] = perturbation_[2] = 0;
    }

    void Process(
        int32_t clock,
        int32_t reset,
        int32_t x_in,
        int32_t y_in,
        int32_t x,
        int32_t y,
        int32_t density_1,
        int32_t density_2,
        int32_t density_3,
        int32_t chaos,
        int32_t seed,
        bool& part_1,
        bool& part_2,
        bool& part_3,
        bool& accent_1,
        bool& accent_2,
        bool& accent_3,
        int32_t& out_step) {
        if (seed != seed_tag_) Seed(seed);

        const bool reset_high = reset > 0;
        if (reset_high && !previous_reset_) step_ = 0;
        previous_reset_ = reset_high;

        part_1 = part_2 = part_3 = false;
        accent_1 = accent_2 = accent_3 = false;
        out_step = step_;

        const bool clock_high = clock > 0;
        if (clock_high && !previous_clock_) {
            const uint8_t map_x = ToByte(SaturatingAdd(x, x_in));
            const uint8_t map_y = ToByte(SaturatingAdd(y, y_in));
            const uint8_t density[3] = {
                ToByte(density_1), ToByte(density_2), ToByte(density_3)
            };
            const uint8_t randomness = ToByte(chaos);
            if (step_ == 0) {
                for (int channel = 0; channel < 3; ++channel) {
                    perturbation_[channel] = static_cast<uint8_t>(
                        ((Next() >> 24) * randomness) >> 8);
                }
            }

            bool* parts[3] = {&part_1, &part_2, &part_3};
            bool* accents[3] = {&accent_1, &accent_2, &accent_3};
            for (int channel = 0; channel < 3; ++channel) {
                int level = ReadMap(step_, channel, map_x, map_y);
                level += perturbation_[channel];
                if (level > 255) level = 255;
                if (level > 255 - density[channel]) {
                    *parts[channel] = true;
                    *accents[channel] = level > 192;
                }
            }
            out_step = step_;
            step_ = (step_ + 1) & 31;
        }
        previous_clock_ = clock_high;
    }

private:
    static int32_t SaturatingAdd(int32_t a, int32_t b) {
        int64_t value = static_cast<int64_t>(a) + b;
        if (value > 0x07ffffff) value = 0x07ffffff;
        if (value < 0) value = 0;
        return static_cast<int32_t>(value);
    }

    static uint8_t ToByte(int32_t value) {
        if (value <= 0) return 0;
        if (value >= 0x07ffffff) return 255;
        return static_cast<uint8_t>(value >> 19);
    }

    static uint8_t Mix(uint8_t a, uint8_t b, uint8_t amount) {
        return static_cast<uint8_t>(
            static_cast<int>(a) + ((static_cast<int>(b) - a) * amount >> 8));
    }

    static uint8_t ReadMap(uint8_t step, uint8_t channel, uint8_t x, uint8_t y) {
        using namespace ksoloti_extended_topographic;
        const uint8_t cell_x = x >> 6;
        const uint8_t cell_y = y >> 6;
        const uint8_t fraction_x = static_cast<uint8_t>((x & 63) << 2);
        const uint8_t fraction_y = static_cast<uint8_t>((y & 63) << 2);
        const int offset = channel * 32 + step;
        const uint8_t a = kMap[cell_x][cell_y][offset];
        const uint8_t b = kMap[cell_x + 1][cell_y][offset];
        const uint8_t c = kMap[cell_x][cell_y + 1][offset];
        const uint8_t d = kMap[cell_x + 1][cell_y + 1][offset];
        return Mix(Mix(a, b, fraction_x), Mix(c, d, fraction_x), fraction_y);
    }

    void Seed(int32_t seed) {
        seed_tag_ = seed;
        state_ = static_cast<uint32_t>(seed) ^ UINT32_C(0x9e3779b9);
        if (state_ == 0) state_ = UINT32_C(0x6d2b79f5);
        step_ = 0;
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
    uint8_t step_;
    uint8_t perturbation_[3];
    bool previous_clock_;
    bool previous_reset_;
};
