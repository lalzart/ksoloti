// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiExtendedTalkboxLPCDSP {
public:
    void Init() {
        for (int i = 0; i < kWindow; ++i) history_[i] = 0.0f;
        for (int i = 0; i <= kMaxOrder; ++i) coefficients_[i] = synthesis_[i] = 0.0f;
        history_index_ = 0;
        blocks_ = 0;
        previous_modulator_ = 0.0f;
        envelope_ = 0.0f;
    }
    void Process(const int32_t* carrier, const int32_t* modulator, int32_t order, int32_t wet,
                 int32_t preemphasis, int32_t* output, int size) {
        const int active_order = ClampInt(order, 4, kMaxOrder);
        const float pre = Unit(preemphasis) * 0.98f;
        const float mix = Unit(wet);
        for (int i = 0; i < size; ++i) {
            const float mod = Bipolar(modulator[i]);
            history_[history_index_] = mod - pre * previous_modulator_;
            previous_modulator_ = mod;
            history_index_ = (history_index_ + 1) & (kWindow - 1);
            envelope_ += (mod * mod - envelope_) * (mod * mod > envelope_ ? 0.02f : 0.002f);
        }
        if (++blocks_ >= 8) { Analyze(active_order); blocks_ = 0; }
        for (int i = 0; i < size; ++i) {
            const float excitation = Bipolar(carrier[i]);
            float y = excitation * (0.15f + envelope_ * 3.0f);
            for (int k = 1; k <= active_order; ++k) y -= coefficients_[k] * synthesis_[k - 1];
            if (y > 1.5f) y = 1.5f;
            if (y < -1.5f) y = -1.5f;
            for (int k = active_order - 1; k > 0; --k) synthesis_[k] = synthesis_[k - 1];
            synthesis_[0] = y;
            output[i] = ToQ27(excitation + (y - excitation) * mix);
        }
    }
private:
    static const int kWindow = 256;
    static const int kMaxOrder = 12;
    void Analyze(int order) {
        double autocorrelation[kMaxOrder + 1] = {};
        for (int lag = 0; lag <= order; ++lag) {
            for (int n = lag; n < kWindow; ++n) {
                const float a = history_[(history_index_ + n) & (kWindow - 1)];
                const float b = history_[(history_index_ + n - lag) & (kWindow - 1)];
                autocorrelation[lag] += static_cast<double>(a) * b;
            }
        }
        float next[kMaxOrder + 1] = {};
        coefficients_[0] = 1.0f;
        double error = autocorrelation[0] + 1.0e-9;
        for (int i = 1; i <= order; ++i) {
            double sum = autocorrelation[i];
            for (int j = 1; j < i; ++j) sum += coefficients_[j] * autocorrelation[i - j];
            double reflection = -sum / error;
            if (reflection > 0.98) reflection = 0.98;
            if (reflection < -0.98) reflection = -0.98;
            for (int j = 0; j <= order; ++j) next[j] = coefficients_[j];
            next[i] = static_cast<float>(reflection);
            for (int j = 1; j < i; ++j) next[j] = coefficients_[j] + static_cast<float>(reflection) * coefficients_[i - j];
            for (int j = 0; j <= i; ++j) coefficients_[j] = next[j];
            error *= 1.0 - reflection * reflection;
            if (error < 1.0e-12) break;
        }
    }
    static int ClampInt(int x, int lo, int hi) { if (x < lo) return lo; if (x > hi) return hi; return x; }
    static float Unit(int32_t x) { if (x <= 0) return 0.0f; if (x >= 0x08000000) return 1.0f; return x * (1.0f / 134217728.0f); }
    static float Bipolar(int32_t x) { return x * (1.0f / 134217728.0f); }
    static int32_t ToQ27(float x) { if (x >= 1.0f) return 0x07ffffff; if (x <= -1.0f) return -0x08000000; return static_cast<int32_t>(x * 134217728.0f); }
    float history_[kWindow];
    float coefficients_[kMaxOrder + 1];
    float synthesis_[kMaxOrder + 1];
    int history_index_;
    int blocks_;
    float previous_modulator_;
    float envelope_;
};
