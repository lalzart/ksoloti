// SPDX-License-Identifier: GPL-3.0-or-later
#include "loop_mutate_dsp.h"

#include <cassert>
#include <cstdint>

static int32_t tick(KsolotiExtendedLoopMutateDSP& engine, int32_t memory,
                    int length, int seed, bool* fresh = 0) {
    int32_t value = 0, step = 0;
    bool did_refresh = false;
    engine.Process(1, 0, memory, INT32_C(1) << 27, 0, length, seed,
                   value, did_refresh, step);
    if (fresh) *fresh = did_refresh;
    engine.Process(0, 0, memory, INT32_C(1) << 27, 0, length, seed,
                   value, did_refresh, step);
    return value;
}

static void test_locked_loop_and_bounds() {
    KsolotiExtendedLoopMutateDSP engine;
    engine.Init();
    int32_t first[5];
    for (int i = 0; i < 5; ++i) first[i] = tick(engine, INT32_C(1) << 27, 5, 99);
    for (int i = 0; i < 20; ++i) {
        const int32_t value = tick(engine, INT32_C(1) << 27, 5, 99);
        assert(value == first[i % 5]);
        assert(value >= -0x08000000 && value <= 0x07ffffff);
    }
}

static void test_fresh_stream_and_repeatability() {
    KsolotiExtendedLoopMutateDSP first;
    KsolotiExtendedLoopMutateDSP second;
    first.Init();
    second.Init();
    for (int i = 0; i < 32; ++i) {
        bool fresh_a = false, fresh_b = false;
        const int32_t a = tick(first, 0, 16, 77, &fresh_a);
        const int32_t b = tick(second, 0, 16, 77, &fresh_b);
        assert(a == b);
        assert(fresh_a && fresh_b);
    }
}

static void test_length_clamps() {
    KsolotiExtendedLoopMutateDSP one;
    KsolotiExtendedLoopMutateDSP sixteen;
    one.Init();
    sixteen.Init();
    const int32_t fixed = tick(one, INT32_C(1) << 27, -5, 19);
    for (int i = 0; i < 8; ++i) {
        assert(tick(one, INT32_C(1) << 27, -5, 19) == fixed);
    }
    for (int i = 0; i < 64; ++i) {
        const int32_t value = tick(sixteen, 0, 100, 21);
        assert(value >= -0x08000000 && value <= 0x07ffffff);
    }
}

int main() {
    test_locked_loop_and_bounds();
    test_fresh_stream_and_repeatability();
    test_length_clamps();
    return 0;
}
