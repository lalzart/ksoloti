// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiExtendedSegment6DSP {
public:
    void Init() {
        current_ = 0;
        phase_ = 0.0f;
        start_ = 0.0f;
        value_ = 0.0f;
        running_ = false;
        previous_trigger_ = false;
    }

    void Process(
        int32_t trigger, int32_t gate, int32_t rate_in,
        int32_t level1, int32_t level2, int32_t level3, int32_t level4, int32_t level5, int32_t level6,
        int32_t time1, int32_t time2, int32_t time3, int32_t time4, int32_t time5, int32_t time6,
        int32_t shape, int32_t sustain, int32_t loop,
        int32_t& output, bool& eoc, int32_t& segment, int size) {
        const bool high = trigger > 0;
        if (high && !previous_trigger_) {
            current_ = 0;
            phase_ = 0.0f;
            start_ = value_;
            running_ = true;
        }
        previous_trigger_ = high;
        eoc = false;
        const int32_t levels[6] = {level1, level2, level3, level4, level5, level6};
        const int32_t times[6] = {time1, time2, time3, time4, time5, time6};
        if (running_) {
            const int sustain_index = ClampInt(sustain, 0, 5);
            const bool held = current_ == sustain_index && gate > 0 && phase_ >= 1.0f;
            if (!held) {
                const float rate_scale = 0.25f + Unit(rate_in) * 3.75f;
                const float seconds = 0.005f + Unit(times[current_]) * Unit(times[current_]) * 7.995f;
                phase_ += static_cast<float>(size) * rate_scale / (48000.0f * seconds);
            }
            float interpolation = phase_ > 1.0f ? 1.0f : phase_;
            interpolation = Shape(interpolation, Unit(shape));
            const float target = Unit(levels[current_]);
            value_ = start_ + (target - start_) * interpolation;
            if (phase_ >= 1.0f && !held) {
                value_ = target;
                start_ = value_;
                phase_ = 0.0f;
                ++current_;
                if (current_ >= 6) {
                    eoc = true;
                    if (loop) current_ = 0;
                    else { current_ = 5; running_ = false; }
                }
            }
        }
        output = ToQ27(value_);
        segment = current_;
    }

private:
    static int ClampInt(int value, int minimum, int maximum) {
        if (value < minimum) return minimum;
        if (value > maximum) return maximum;
        return value;
    }
    static float Unit(int32_t value) {
        if (value <= 0) return 0.0f;
        if (value >= 0x08000000) return 1.0f;
        return value * (1.0f / 134217728.0f);
    }
    static float Shape(float x, float shape) {
        const float smooth = x * x * (3.0f - 2.0f * x);
        if (shape < 0.5f) return x + (smooth - x) * (shape * 2.0f);
        const float step = x >= 1.0f ? 1.0f : 0.0f;
        return smooth + (step - smooth) * ((shape - 0.5f) * 2.0f);
    }
    static int32_t ToQ27(float value) {
        if (value <= 0.0f) return 0;
        if (value >= 1.0f) return 0x07ffffff;
        return static_cast<int32_t>(value * 134217728.0f);
    }
    int current_;
    float phase_;
    float start_;
    float value_;
    bool running_;
    bool previous_trigger_;
};
