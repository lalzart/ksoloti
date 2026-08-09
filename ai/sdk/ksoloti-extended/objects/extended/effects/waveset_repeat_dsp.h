// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiExtendedWavesetRepeatDSP {
public:
    void Init() {
        for (int i = 0; i < kCapacity; ++i) buffer_[i] = 0;
        length_ = write_ = read_ = crossings_ = repeats_left_ = 0;
        previous_sample_ = 0;
        previous_trigger_ = false;
        capturing_ = repeating_ = false;
    }
    void Process(const int32_t* input, int32_t trigger, int32_t cycles, int32_t repeats, int32_t threshold,
                 int32_t mix, int32_t* output, bool& capturing, bool& repeating, int size) {
        const bool high = trigger > 0;
        if (high && !previous_trigger_) {
            capturing_ = true; repeating_ = false; write_ = 0; crossings_ = 0; length_ = 0;
        }
        previous_trigger_ = high;
        const int target_crossings = ClampInt(cycles, 1, 16) * 2;
        const int repeat_count = ClampInt(repeats, 1, 32);
        const int32_t threshold_value = ClampUnit(threshold) >> 5;
        const int32_t wet = ClampUnit(mix);
        for (int i = 0; i < size; ++i) {
            int32_t effected = input[i];
            if (capturing_) {
                if (write_ < kCapacity) buffer_[write_++] = input[i];
                const bool crossing = previous_sample_ <= -threshold_value && input[i] > threshold_value;
                const bool reverse_crossing = previous_sample_ >= threshold_value && input[i] < -threshold_value;
                if (crossing || reverse_crossing) ++crossings_;
                if (crossings_ >= target_crossings || write_ >= kCapacity) {
                    length_ = write_;
                    capturing_ = false;
                    repeating_ = length_ > 1;
                    read_ = 0;
                    repeats_left_ = repeat_count;
                }
            } else if (repeating_ && length_ > 1) {
                effected = buffer_[read_++];
                if (read_ >= length_) {
                    read_ = 0;
                    if (--repeats_left_ <= 0) repeating_ = false;
                }
            }
            previous_sample_ = input[i];
            output[i] = SaturatingMix(input[i], effected, wet);
        }
        capturing = capturing_;
        repeating = repeating_;
    }
private:
    static const int kCapacity = 4096;
    static int ClampInt(int x, int lo, int hi) { if (x < lo) return lo; if (x > hi) return hi; return x; }
    static int32_t ClampUnit(int32_t x) { if (x <= 0) return 0; if (x >= 0x08000000) return 0x07ffffff; return x; }
    static int32_t SaturatingMix(int32_t dry, int32_t effected, int32_t wet) { const int64_t x = static_cast<int64_t>(dry) + ((static_cast<int64_t>(effected - dry) * wet) >> 27); if (x > 0x07ffffff) return 0x07ffffff; if (x < -0x08000000) return -0x08000000; return static_cast<int32_t>(x); }
    int32_t buffer_[kCapacity];
    int length_, write_, read_, crossings_, repeats_left_;
    int32_t previous_sample_;
    bool previous_trigger_, capturing_, repeating_;
};
