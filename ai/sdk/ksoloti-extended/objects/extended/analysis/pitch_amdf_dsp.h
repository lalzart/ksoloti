// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiExtendedPitchAMDFAudioDSP {
public:
    void Init() {
        for (int i = 0; i < kHistorySize; ++i) history_[i] = 0;
        write_index_ = 0;
        decimation_sum_ = 0;
        decimation_count_ = 0;
        samples_seen_ = 0;
        samples_until_analysis_ = kAnalysisHop;
        pitch_ = 0;
        level_ = 0;
        confidence_ = 0;
        candidate_valid_ = false;
    }

    void Process(
        const int32_t* input,
        int32_t minimum_frequency,
        int32_t maximum_frequency,
        int32_t threshold,
        int32_t quality,
        int32_t smooth,
        int32_t& pitch,
        int32_t& level,
        int32_t& confidence,
        bool& valid,
        int size) {
        uint64_t level_sum = 0;
        for (int i = 0; i < size; ++i) {
            const int64_t sample = input[i];
            level_sum += static_cast<uint64_t>(sample < 0 ? -sample : sample);
            decimation_sum_ += sample;
            if (++decimation_count_ == kDecimation) {
                history_[write_index_] = static_cast<int32_t>(decimation_sum_ / kDecimation);
                write_index_ = (write_index_ + 1) & kHistoryMask;
                if (samples_seen_ < kHistorySize) ++samples_seen_;
                decimation_sum_ = 0;
                decimation_count_ = 0;
                if (--samples_until_analysis_ <= 0) {
                    Analyze(minimum_frequency, maximum_frequency);
                    samples_until_analysis_ = kAnalysisHop;
                }
            }
        }
        const int32_t block_level = size > 0
            ? ClampUnit64(level_sum / static_cast<uint32_t>(size)) : 0;
        const int shift = block_level > level_ ? 2 : 5;
        level_ += (block_level - level_) >> shift;
        const bool accepted = candidate_valid_
            && level_ >= ClampUnit(threshold)
            && confidence_ >= ClampUnit(quality);
        if (accepted) {
            int smoothing_shift = static_cast<int>(static_cast<uint32_t>(ClampUnit(smooth)) >> 24);
            if (smoothing_shift > 7) smoothing_shift = 7;
            if (smoothing_shift == 0) pitch_ = candidate_pitch_;
            else pitch_ += (candidate_pitch_ - pitch_) >> smoothing_shift;
        }
        pitch = pitch_;
        level = level_;
        confidence = confidence_;
        valid = accepted;
    }

private:
    static const int kDecimation = 4;
    static const int kDecimatedRate = 12000;
    static const int kHistorySize = 512;
    static const int kHistoryMask = kHistorySize - 1;
    static const int kWindow = 64;
    static const int kAnalysisHop = 16;

    int32_t SampleAgo(int age) const {
        return history_[(write_index_ - 1 - age) & kHistoryMask];
    }

    uint64_t Difference(int lag) const {
        uint64_t sum = 0;
        for (int i = 0; i < kWindow; ++i) {
            const int64_t difference = static_cast<int64_t>(SampleAgo(i)) - SampleAgo(i + lag);
            sum += static_cast<uint64_t>(difference < 0 ? -difference : difference);
        }
        return sum;
    }

    void Analyze(int minimum_frequency, int maximum_frequency) {
        int min_frequency = ClampInt(minimum_frequency, 40, 200);
        int max_frequency = ClampInt(maximum_frequency, 400, 2000);
        if (max_frequency <= min_frequency) max_frequency = min_frequency + 1;
        int minimum_lag = kDecimatedRate / max_frequency;
        int maximum_lag = kDecimatedRate / min_frequency;
        minimum_lag = ClampInt(minimum_lag, 6, 30);
        maximum_lag = ClampInt(maximum_lag, minimum_lag + 2, 300);
        if (samples_seen_ < maximum_lag + kWindow + 1) {
            confidence_ = 0;
            candidate_valid_ = false;
            return;
        }

        uint64_t best_error = UINT64_MAX;
        uint64_t coarse_sum = 0;
        int coarse_count = 0;
        int best_lag = minimum_lag;
        for (int lag = minimum_lag; lag <= maximum_lag; lag += 4) {
            const uint64_t error = Difference(lag);
            coarse_sum += error;
            ++coarse_count;
            if (error < best_error) { best_error = error; best_lag = lag; }
        }
        const int refine_start = ClampInt(best_lag - 3, minimum_lag, maximum_lag);
        const int refine_end = ClampInt(best_lag + 3, minimum_lag, maximum_lag);
        for (int lag = refine_start; lag <= refine_end; ++lag) {
            const uint64_t error = Difference(lag);
            if (error < best_error) { best_error = error; best_lag = lag; }
        }

        const uint64_t mean_error = coarse_count ? coarse_sum / coarse_count : 0;
        for (int divisor = 4; divisor >= 2; --divisor) {
            const int candidate = (best_lag + divisor / 2) / divisor;
            if (candidate < minimum_lag) continue;
            for (int offset = -1; offset <= 1; ++offset) {
                const int lag = candidate + offset;
                if (lag < minimum_lag || lag >= best_lag) continue;
                const uint64_t error = Difference(lag);
                if (error <= best_error + mean_error / 16) {
                    best_error = error;
                    best_lag = lag;
                }
            }
        }

        int32_t period_q16 = best_lag << 16;
        if (best_lag > minimum_lag && best_lag < maximum_lag) {
            const double left = static_cast<double>(Difference(best_lag - 1));
            const double middle = static_cast<double>(Difference(best_lag));
            const double right = static_cast<double>(Difference(best_lag + 1));
            const double denominator = left - 2.0 * middle + right;
            if (denominator > 0.0) {
                double delta = 0.5 * (left - right) / denominator;
                if (delta < -0.5) delta = -0.5;
                if (delta > 0.5) delta = 0.5;
                period_q16 += static_cast<int32_t>(delta * 65536.0);
            }
        }

        const int32_t log_period = static_cast<int32_t>(FastLog2Q23(period_q16));
        const int32_t log_e4_period = static_cast<int32_t>(FastLog2Q23(2385820));
        candidate_pitch_ = ClampBipolar(-3 * (log_period - log_e4_period));
        confidence_ = mean_error > best_error && mean_error
            ? ClampUnit64(((mean_error - best_error) << 27) / mean_error)
            : 0;
        candidate_valid_ = true;
    }

    static uint32_t FastLog2Q23(uint32_t value) {
        union { float f; uint32_t u; } bits;
        bits.f = static_cast<float>(value);
        return (((bits.u >> 23) & 0xff) << 23) | (bits.u & 0x7fffff);
    }
    static int ClampInt(int value, int minimum, int maximum) { if (value < minimum) return minimum; if (value > maximum) return maximum; return value; }
    static int32_t ClampUnit(int32_t value) { if (value <= 0) return 0; if (value >= 0x08000000) return 0x07ffffff; return value; }
    static int32_t ClampUnit64(uint64_t value) { return value >= UINT64_C(0x08000000) ? 0x07ffffff : static_cast<int32_t>(value); }
    static int32_t ClampBipolar(int64_t value) { if (value > 0x07ffffff) return 0x07ffffff; if (value < -0x08000000) return -0x08000000; return static_cast<int32_t>(value); }

    int32_t history_[kHistorySize];
    int write_index_;
    int64_t decimation_sum_;
    int decimation_count_;
    int samples_seen_;
    int samples_until_analysis_;
    int32_t candidate_pitch_;
    int32_t pitch_;
    int32_t level_;
    int32_t confidence_;
    bool candidate_valid_;
};
