// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiExtendedKeyframes4DSP {
public:
    void Init() {
        previous_record_ = false;
        for (int frame = 0; frame < kFrames; ++frame) {
            for (int channel = 0; channel < kChannels; ++channel) {
                values_[frame][channel] = frame == 0 ? 0 : 0x04000000;
            }
        }
    }

    void Process(
        int32_t record, int32_t position_in,
        int32_t input1, int32_t input2, int32_t input3, int32_t input4,
        int32_t position, int32_t slot, int32_t frames, int32_t curve,
        int32_t& output1, int32_t& output2, int32_t& output3, int32_t& output4,
        int32_t& segment) {
        const bool high = record > 0;
        const int frame_count = ClampInt(frames, 2, kFrames);
        const int selected_slot = ClampInt(slot, 0, frame_count - 1);
        if (high && !previous_record_) {
            values_[selected_slot][0] = ClampUnit(input1);
            values_[selected_slot][1] = ClampUnit(input2);
            values_[selected_slot][2] = ClampUnit(input3);
            values_[selected_slot][3] = ClampUnit(input4);
        }
        previous_record_ = high;

        const int32_t normalized = ClampUnit(SaturatingAdd(position, position_in));
        const uint64_t scaled = static_cast<uint64_t>(normalized) * (frame_count - 1);
        const int left = static_cast<int>(scaled >> 27);
        const int right = left + 1 < frame_count ? left + 1 : left;
        int32_t fraction = static_cast<int32_t>(scaled & 0x07ffffff);
        if (curve == 1) {
            const int64_t x = fraction;
            const int64_t x2 = (x * x) >> 27;
            fraction = static_cast<int32_t>((x2 * ((INT64_C(3) << 27) - (x << 1))) >> 27);
        } else if (curve >= 2) {
            fraction = 0;
        }
        int32_t* outputs[kChannels] = {&output1, &output2, &output3, &output4};
        for (int channel = 0; channel < kChannels; ++channel) {
            const int64_t delta = static_cast<int64_t>(values_[right][channel]) - values_[left][channel];
            *outputs[channel] = values_[left][channel] + static_cast<int32_t>((delta * fraction) >> 27);
        }
        segment = left;
    }

private:
    static const int kFrames = 8;
    static const int kChannels = 4;

    static int ClampInt(int value, int minimum, int maximum) {
        if (value < minimum) return minimum;
        if (value > maximum) return maximum;
        return value;
    }

    static int32_t ClampUnit(int32_t value) {
        if (value <= 0) return 0;
        if (value >= 0x08000000) return 0x07ffffff;
        return value;
    }

    static int32_t SaturatingAdd(int32_t a, int32_t b) {
        const int64_t value = static_cast<int64_t>(a) + b;
        if (value <= 0) return 0;
        if (value >= 0x08000000) return 0x07ffffff;
        return static_cast<int32_t>(value);
    }

    int32_t values_[kFrames][kChannels];
    bool previous_record_;
};
