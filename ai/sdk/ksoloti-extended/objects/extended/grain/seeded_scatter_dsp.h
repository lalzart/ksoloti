// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiExtendedSeededScatterDSP {
public:
    void Init() {
        for (int i = 0; i < kCapacity; ++i) buffer_[i] = 0.0f;
        for (int i = 0; i < kGrains; ++i) grains_[i].remaining = 0;
        state_ = 1; seed_tag_ = INT32_MIN; write_ = next_grain_ = 0;
        previous_trigger_ = false; feedback_sample_ = 0.0f;
    }
    void Process(const int32_t* input, int32_t trigger, int32_t density, int32_t grain_size,
                 int32_t pitch, int32_t spread, int32_t feedback, int32_t seed,
                 int32_t* left, int32_t* right, int size) {
        if (seed != seed_tag_) Seed(seed);
        const bool high = trigger > 0;
        const bool edge = high && !previous_trigger_;
        previous_trigger_ = high;
        if (edge) Spawn(grain_size, pitch, spread);
        const uint32_t chance = static_cast<uint32_t>(Unit(density) * Unit(density) * 1000000.0f);
        const float fb = Unit(feedback) * 0.85f;
        for (int sample = 0; sample < size; ++sample) {
            if ((Next() & 0x00ffffff) < chance) Spawn(grain_size, pitch, spread);
            buffer_[write_] = Bipolar(input[sample]) + feedback_sample_ * fb;
            write_ = (write_ + 1) & (kCapacity - 1);
            float l = 0.0f, r = 0.0f;
            for (int i = 0; i < kGrains; ++i) {
                Grain& grain = grains_[i];
                if (grain.remaining <= 0) continue;
                const int index = static_cast<int>(grain.position) & (kCapacity - 1);
                const int next = (index + 1) & (kCapacity - 1);
                const float fraction = grain.position - static_cast<int>(grain.position);
                const float value = buffer_[index] + (buffer_[next] - buffer_[index]) * fraction;
                const float progress = 1.0f - static_cast<float>(grain.remaining) / grain.total;
                const float window = 1.0f - (progress < 0.5f ? 1.0f - progress * 2.0f : progress * 2.0f - 1.0f);
                l += value * window * (1.0f - grain.pan);
                r += value * window * grain.pan;
                grain.position += grain.increment;
                while (grain.position >= kCapacity) grain.position -= kCapacity;
                --grain.remaining;
            }
            feedback_sample_ = (l + r) * 0.35f;
            left[sample] = ToQ27(l * 0.65f);
            right[sample] = ToQ27(r * 0.65f);
        }
    }
private:
    static const int kCapacity = 4096, kGrains = 4;
    struct Grain { float position, increment, pan; int remaining, total; };
    void Spawn(int32_t size, int32_t pitch, int32_t spread) {
        Grain& grain = grains_[next_grain_++ & (kGrains - 1)];
        grain.total = 64 + static_cast<int>(Unit(size) * 1984.0f);
        grain.remaining = grain.total;
        const int delay = 64 + static_cast<int>(Next() % (kCapacity - 128));
        grain.position = static_cast<float>((write_ - delay) & (kCapacity - 1));
        grain.increment = 0.5f + Unit(pitch) * 1.5f;
        const float random_pan = static_cast<float>(Next() & 0xffff) * (1.0f / 65535.0f);
        grain.pan = 0.5f + (random_pan - 0.5f) * Unit(spread);
    }
    void Seed(int32_t seed) { seed_tag_ = seed; state_ = static_cast<uint32_t>(seed) ^ UINT32_C(0xbb67ae85); if (!state_) state_ = 1; }
    uint32_t Next() { uint32_t x = state_; x ^= x << 13; x ^= x >> 17; x ^= x << 5; return state_ = x; }
    static float Unit(int32_t x) { if (x <= 0) return 0.0f; if (x >= 0x08000000) return 1.0f; return x * (1.0f / 134217728.0f); }
    static float Bipolar(int32_t x) { return x * (1.0f / 134217728.0f); }
    static int32_t ToQ27(float x) { if (x >= 1.0f) return 0x07ffffff; if (x <= -1.0f) return -0x08000000; return static_cast<int32_t>(x * 134217728.0f); }
    float buffer_[kCapacity];
    Grain grains_[kGrains];
    uint32_t state_;
    int32_t seed_tag_;
    int write_, next_grain_;
    bool previous_trigger_;
    float feedback_sample_;
};
