// SPDX-License-Identifier: GPL-3.0-or-later
#include "probability_router_dsp.h"

#include <cassert>
#include <cstdint>

static void pulse(KsolotiExtendedProbabilityRouterDSP& engine, int32_t probability,
                  int32_t seed, bool& a, bool& b, bool& choice) {
    engine.Process(1, probability, seed, a, b, choice);
    engine.Process(0, probability, seed, a, b, choice);
}

static void test_extremes_and_edges() {
    KsolotiExtendedProbabilityRouterDSP engine;
    bool a = false, b = false, choice = false;
    engine.Init();
    engine.Process(1, 0, 7, a, b, choice);
    assert(a == 0 && b == 1 && choice == 0);
    engine.Process(1, 0, 7, a, b, choice);
    assert(a == 0 && b == 0 && choice == 0);
    engine.Process(0, 0, 7, a, b, choice);
    engine.Process(1, INT32_C(1) << 27, 7, a, b, choice);
    assert(a == 1 && b == 0 && choice == 1);
}

static void test_seed_repeatability() {
    KsolotiExtendedProbabilityRouterDSP first;
    KsolotiExtendedProbabilityRouterDSP second;
    first.Init();
    second.Init();
    for (int i = 0; i < 64; ++i) {
        bool a1, b1, c1, a2, b2, c2;
        pulse(first, INT32_C(1) << 26, 1234, a1, b1, c1);
        pulse(second, INT32_C(1) << 26, 1234, a2, b2, c2);
        assert(c1 == c2);
    }
}

int main() {
    test_extremes_and_edges();
    test_seed_repeatability();
    return 0;
}
