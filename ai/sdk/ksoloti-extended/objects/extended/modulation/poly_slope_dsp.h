// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiExtendedPolySlopeDSP {
public:
    void Init() {
        phase_ = 0.0f;
        synchronized_increment_ = 0.0f;
        samples_since_clock_ = 0;
        previous_clock_ = false;
        previous_reset_ = false;
    }

    void Process(
        int32_t clock,
        int32_t reset,
        int32_t rate_in,
        int32_t shape_in,
        int32_t slope_in,
        int32_t smooth_in,
        int32_t rate,
        int32_t shape,
        int32_t slope,
        int32_t smooth,
        int32_t clocked,
        int32_t& phase_0,
        int32_t& phase_90,
        int32_t& phase_180,
        int32_t& phase_270,
        bool& eoc,
        int size) {
        const bool reset_high = reset > 0;
        if (reset_high && !previous_reset_) phase_ = 0.0f;
        previous_reset_ = reset_high;

        const bool clock_high = clock > 0;
        if (clock_high && !previous_clock_) {
            if (samples_since_clock_ >= size && samples_since_clock_ <= 480000) {
                synchronized_increment_ = 1.0f / static_cast<float>(samples_since_clock_);
            }
            samples_since_clock_ = 0;
            if (clocked) phase_ = 0.0f;
        }
        previous_clock_ = clock_high;

        const float rate_value = Unit(SaturatingAdd(rate, rate_in));
        const float rate_squared = rate_value * rate_value;
        const float free_hz = 0.02f + rate_squared * rate_value * 39.98f;
        const float free_increment = free_hz / 48000.0f;
        const float increment = clocked && synchronized_increment_ > 0.0f
            ? synchronized_increment_ : free_increment;

        const float shape_value = Unit(SaturatingAdd(shape, shape_in));
        const float slope_value = Unit(SaturatingAdd(slope, slope_in));
        const float smooth_value = Unit(SaturatingAdd(smooth, smooth_in));
        phase_0 = ToQ27(Wave(phase_, shape_value, slope_value, smooth_value));
        phase_90 = ToQ27(Wave(Wrap(phase_ + 0.25f), shape_value, slope_value, smooth_value));
        phase_180 = ToQ27(Wave(Wrap(phase_ + 0.5f), shape_value, slope_value, smooth_value));
        phase_270 = ToQ27(Wave(Wrap(phase_ + 0.75f), shape_value, slope_value, smooth_value));

        eoc = false;
        phase_ += increment * static_cast<float>(size);
        if (phase_ >= 1.0f) {
            phase_ -= static_cast<int>(phase_);
            eoc = true;
        }
        samples_since_clock_ += size;
        if (samples_since_clock_ > 480000) samples_since_clock_ = 480000;
    }

private:
    static int32_t SaturatingAdd(int32_t a, int32_t b) {
        int64_t value = static_cast<int64_t>(a) + b;
        if (value > 0x07ffffff) value = 0x07ffffff;
        if (value < 0) value = 0;
        return static_cast<int32_t>(value);
    }

    static float Unit(int32_t value) {
        if (value <= 0) return 0.0f;
        if (value >= 0x08000000) return 1.0f;
        return static_cast<float>(value) * (1.0f / 134217728.0f);
    }

    static float Wrap(float value) {
        return value >= 1.0f ? value - 1.0f : value;
    }

    static float Wave(float phase, float shape, float slope, float smooth) {
        const float skew = 0.05f + slope * 0.90f;
        float rising;
        if (phase < skew) {
            rising = phase / skew;
        } else {
            rising = (1.0f - phase) / (1.0f - skew);
        }
        if (rising < 0.0f) rising = 0.0f;
        if (rising > 1.0f) rising = 1.0f;

        const float smoothstep = rising * rising * (3.0f - 2.0f * rising);
        float value = rising + smooth * (smoothstep - rising);
        if (shape < 0.5f) {
            const float amount = 1.0f - shape * 2.0f;
            value += amount * (value * value - value);
        } else {
            const float amount = shape * 2.0f - 1.0f;
            const float inverse = 1.0f - value;
            const float ease_out = 1.0f - inverse * inverse;
            value += amount * (ease_out - value);
        }
        return value * 2.0f - 1.0f;
    }

    static int32_t ToQ27(float value) {
        if (value >= 1.0f) return 0x07ffffff;
        if (value <= -1.0f) return -0x08000000;
        return static_cast<int32_t>(value * 134217728.0f);
    }

    float phase_;
    float synchronized_increment_;
    int32_t samples_since_clock_;
    bool previous_clock_;
    bool previous_reset_;
};
