// SPDX-License-Identifier: GPL-3.0-or-later
#include "topographic_3_dsp.h"

#include <cassert>
#include <cstdint>

struct Result {
    bool part[3];
    bool accent[3];
    int32_t step;
};

static Result tick(KsolotiExtendedTopographic3DSP& engine, int32_t density,
                   int32_t x, int32_t y, int32_t chaos, int seed) {
    Result result = {{0, 0, 0}, {0, 0, 0}, 0};
    engine.Process(1, 0, 0, 0, x, y, density, density, density, chaos, seed,
                   result.part[0], result.part[1], result.part[2],
                   result.accent[0], result.accent[1], result.accent[2], result.step);
    bool ignored_part[3], ignored_accent[3];
    int32_t ignored_step;
    engine.Process(0, 0, 0, 0, x, y, density, density, density, chaos, seed,
                   ignored_part[0], ignored_part[1], ignored_part[2],
                   ignored_accent[0], ignored_accent[1], ignored_accent[2], ignored_step);
    return result;
}

static void test_step_wrap_and_accent_subset() {
    KsolotiExtendedTopographic3DSP engine;
    engine.Init();
    for (int i = 0; i < 96; ++i) {
        const Result result = tick(engine, 0x07ffffff, INT32_C(1) << 26,
                                   INT32_C(1) << 26, 0, 11);
        assert(result.step == (i & 31));
        for (int channel = 0; channel < 3; ++channel) {
            assert(!result.accent[channel] || result.part[channel]);
        }
    }
}

static void test_density_and_seed_repeatability() {
    KsolotiExtendedTopographic3DSP low;
    KsolotiExtendedTopographic3DSP high;
    KsolotiExtendedTopographic3DSP first;
    KsolotiExtendedTopographic3DSP second;
    low.Init(); high.Init(); first.Init(); second.Init();
    int low_count = 0, high_count = 0;
    for (int i = 0; i < 64; ++i) {
        const Result lo = tick(low, 0, INT32_C(1) << 25, INT32_C(1) << 26, 0, 5);
        const Result hi = tick(high, 0x07ffffff, INT32_C(1) << 25,
                               INT32_C(1) << 26, 0, 5);
        const Result a = tick(first, INT32_C(1) << 26, INT32_C(1) << 25,
                              INT32_C(1) << 26, INT32_C(1) << 25, 123);
        const Result b = tick(second, INT32_C(1) << 26, INT32_C(1) << 25,
                              INT32_C(1) << 26, INT32_C(1) << 25, 123);
        for (int channel = 0; channel < 3; ++channel) {
            low_count += lo.part[channel];
            high_count += hi.part[channel];
            assert(a.part[channel] == b.part[channel]);
            assert(a.accent[channel] == b.accent[channel]);
        }
    }
    assert(low_count == 0);
    assert(high_count > low_count);
}

static void test_coordinate_variation() {
    KsolotiExtendedTopographic3DSP corner_a;
    KsolotiExtendedTopographic3DSP corner_b;
    corner_a.Init();
    corner_b.Init();
    int differences = 0;
    for (int i = 0; i < 32; ++i) {
        const Result a = tick(corner_a, INT32_C(1) << 26, 0, 0, 0, 41);
        const Result b = tick(corner_b, INT32_C(1) << 26, 0x07ffffff,
                              0x07ffffff, 0, 41);
        for (int channel = 0; channel < 3; ++channel) {
            differences += a.part[channel] != b.part[channel];
        }
    }
    assert(differences > 0);
}

int main() {
    test_step_wrap_and_accent_subset();
    test_density_and_seed_repeatability();
    test_coordinate_variation();
    return 0;
}
