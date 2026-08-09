// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiExtendedClockedDelayDSP {
public:
    void Init() {
        for (int i = 0; i < kCapacity; ++i) buffer_[i] = 0.0f;
        for (int i = 0; i < kGrains; ++i) grains_[i].remaining = 0;
        write_ = next_grain_ = 0; previous_clock_ = false; feedback_sample_ = 0.0f;
    }
    void Process(const int32_t* input, int32_t clock, int32_t delay, int32_t grain_size,
                 int32_t pitch, int32_t feedback, int32_t freeze,
                 int32_t* left, int32_t* right, int size) {
        const bool high = clock > 0;
        if (high && !previous_clock_) Spawn(delay, grain_size, pitch);
        previous_clock_ = high;
        const float fb = Unit(feedback) * 0.88f;
        for (int sample = 0; sample < size; ++sample) {
            if (!freeze) {
                buffer_[write_] = Bipolar(input[sample]) + feedback_sample_ * fb;
                write_ = (write_ + 1) & (kCapacity - 1);
            }
            float l = 0.0f, r = 0.0f;
            for (int i = 0; i < kGrains; ++i) {
                Grain& grain = grains_[i];
                if (grain.remaining <= 0) continue;
                const int index = static_cast<int>(grain.position) & (kCapacity - 1);
                const int next = (index + 1) & (kCapacity - 1);
                const float fraction = grain.position - static_cast<int>(grain.position);
                const float value = buffer_[index] + (buffer_[next] - buffer_[index]) * fraction;
                const float progress = 1.0f - static_cast<float>(grain.remaining) / grain.total;
                const float window = progress < 0.5f ? progress * 2.0f : (1.0f - progress) * 2.0f;
                l += value * window * (grain.pan ? 0.25f : 0.75f);
                r += value * window * (grain.pan ? 0.75f : 0.25f);
                grain.position += grain.increment;
                while (grain.position >= kCapacity) grain.position -= kCapacity;
                --grain.remaining;
            }
            feedback_sample_ = (l + r) * 0.4f;
            left[sample] = ToQ27(l);
            right[sample] = ToQ27(r);
        }
    }
private:
    static const int kCapacity = 8192, kGrains = 4;
    struct Grain { float position, increment; int remaining, total; bool pan; };
    void Spawn(int32_t delay, int32_t size, int32_t pitch) {
        Grain& grain = grains_[next_grain_ & (kGrains - 1)];
        grain.total = 96 + static_cast<int>(Unit(size) * 4000.0f);
        grain.remaining = grain.total;
        const int delay_samples = 64 + static_cast<int>(Unit(delay) * (kCapacity - 128));
        grain.position = static_cast<float>((write_ - delay_samples) & (kCapacity - 1));
        grain.increment = 0.5f + Unit(pitch) * 1.5f;
        grain.pan = (next_grain_ & 1) != 0;
        ++next_grain_;
    }
    static float Unit(int32_t x) { if (x <= 0) return 0.0f; if (x >= 0x08000000) return 1.0f; return x * (1.0f / 134217728.0f); }
    static float Bipolar(int32_t x) { return x * (1.0f / 134217728.0f); }
    static int32_t ToQ27(float x) { if (x >= 1.0f) return 0x07ffffff; if (x <= -1.0f) return -0x08000000; return static_cast<int32_t>(x * 134217728.0f); }
    float buffer_[kCapacity];
    Grain grains_[kGrains];
    int write_, next_grain_;
    bool previous_clock_;
    float feedback_sample_;
};
