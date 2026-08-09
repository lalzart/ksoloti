// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiExtendedAdaptiveClockDSP {
public:
    void Init() { measured_ = 0; elapsed_ = 0; phase_ = 0; previous_tap_ = false; locked_ = false; }
    void Process(int32_t tap, int32_t reset, int32_t ratio, int32_t smoothing,
                 bool& clock, int32_t& phase, bool& locked, int size) {
        if (reset > 0) Init();
        const bool high = tap > 0;
        if (high && !previous_tap_) {
            if (elapsed_ >= size && elapsed_ <= 480000) {
                if (!locked_) measured_ = elapsed_;
                else {
                    const int shift = 1 + static_cast<int>((static_cast<uint32_t>(ClampUnit(smoothing)) * 5) >> 27);
                    measured_ += (elapsed_ - measured_) >> shift;
                }
                locked_ = true;
                phase_ = 0;
            }
            elapsed_ = 0;
        }
        previous_tap_ = high;
        elapsed_ += size;
        if (elapsed_ > 480000) { elapsed_ = 480000; locked_ = false; }
        clock = false;
        if (locked_ && measured_ > 0) {
            int period = measured_;
            if (ratio > 0) period /= ratio + 1;
            else if (ratio < 0) period *= 1 - ratio;
            if (period < size) period = size;
            phase_ += size;
            if (phase_ >= period) { phase_ %= period; clock = true; }
            phase = static_cast<int32_t>((static_cast<int64_t>(phase_) << 27) / period);
        } else phase = 0;
        locked = locked_;
    }
private:
    static int32_t ClampUnit(int32_t x) { if (x <= 0) return 0; if (x >= 0x08000000) return 0x07ffffff; return x; }
    int32_t measured_;
    int32_t elapsed_;
    int32_t phase_;
    bool previous_tap_;
    bool locked_;
};
