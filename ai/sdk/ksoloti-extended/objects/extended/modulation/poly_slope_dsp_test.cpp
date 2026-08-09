// SPDX-License-Identifier: GPL-3.0-or-later
#include "poly_slope_dsp.h"

#include <cassert>
#include <cstdint>

static void process(KsolotiExtendedPolySlopeDSP& engine, int32_t clock,
                    int32_t reset, int32_t clocked, int32_t& a, int32_t& b,
                    int32_t& c, int32_t& d, bool& eoc) {
    engine.Process(clock, reset, 0, 0, 0, 0,
                   INT32_C(1) << 25, INT32_C(1) << 26,
                   INT32_C(1) << 26, INT32_C(1) << 26, clocked,
                   a, b, c, d, eoc, 16);
}

static void test_bounds_and_reset() {
    KsolotiExtendedPolySlopeDSP engine;
    engine.Init();
    int32_t a, b, c, d;
    bool eoc;
    for (int i = 0; i < 10000; ++i) {
        process(engine, 0, i == 5000, 0, a, b, c, d, eoc);
        assert(a >= -0x08000000 && a <= 0x07ffffff);
        assert(b >= -0x08000000 && b <= 0x07ffffff);
        assert(c >= -0x08000000 && c <= 0x07ffffff);
        assert(d >= -0x08000000 && d <= 0x07ffffff);
    }
    process(engine, 0, 0, 0, a, b, c, d, eoc);
    process(engine, 0, 1, 0, a, b, c, d, eoc);
    assert(a == -0x08000000);
    assert(c == 0x07ffffff);
}

static void test_clock_lock_repeatability() {
    KsolotiExtendedPolySlopeDSP first;
    KsolotiExtendedPolySlopeDSP second;
    first.Init();
    second.Init();
    int32_t a1, b1, c1, d1, a2, b2, c2, d2;
    bool e1, e2;
    for (int block = 0; block < 128; ++block) {
        const int32_t clock = (block % 16) == 0;
        process(first, clock, 0, 1, a1, b1, c1, d1, e1);
        process(second, clock, 0, 1, a2, b2, c2, d2, e2);
        assert(a1 == a2 && b1 == b2 && c1 == c2 && d1 == d2 && e1 == e2);
    }
}

int main() {
    test_bounds_and_reset();
    test_clock_lock_repeatability();
    return 0;
}
