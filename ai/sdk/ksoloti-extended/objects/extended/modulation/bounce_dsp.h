// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiExtendedBounceDSP {
public:
    void Init() { height_ = velocity_ = 0.0f; previous_trigger_ = false; active_ = false; }
    void Process(int32_t trigger, int32_t gravity, int32_t rebound, int32_t loss,
                 int32_t& height, bool& impact, bool& active, int size) {
        const bool high = trigger > 0;
        if (high && !previous_trigger_) {
            height_ = 1.0f;
            velocity_ = 0.15f + Unit(rebound) * 1.35f;
            active_ = true;
        }
        previous_trigger_ = high;
        impact = false;
        if (active_) {
            const float dt = static_cast<float>(size) / 3000.0f;
            velocity_ -= (0.25f + Unit(gravity) * 3.75f) * dt;
            height_ += velocity_ * dt;
            if (height_ <= 0.0f) {
                height_ = 0.0f;
                impact = true;
                velocity_ = -velocity_ * (0.98f - Unit(loss) * 0.88f);
                if (velocity_ < 0.012f) { velocity_ = 0.0f; active_ = false; }
            }
            if (height_ > 1.0f) height_ = 1.0f;
        }
        height = ToQ27(height_);
        active = active_;
    }
private:
    static float Unit(int32_t x) { if (x <= 0) return 0.0f; if (x >= 0x08000000) return 1.0f; return x * (1.0f / 134217728.0f); }
    static int32_t ToQ27(float x) { if (x <= 0.0f) return 0; if (x >= 1.0f) return 0x07ffffff; return static_cast<int32_t>(x * 134217728.0f); }
    float height_;
    float velocity_;
    bool previous_trigger_;
    bool active_;
};
