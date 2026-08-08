// SPDX-License-Identifier: GPL-3.0-or-later
#include "gain_dsp.h"

#include <cassert>
#include <cstdint>

static const int kBlockSize = 16;
static const int32_t kUnityQ27 = INT32_C(1) << 27;

static void test_silence() {
    KsolotiAiGainDSP engine;
    int32_t input[kBlockSize] = {0};
    int32_t output[kBlockSize];
    engine.Init();
    engine.Process(input, output, kUnityQ27, kBlockSize);
    for (int index = 0; index < kBlockSize; ++index) assert(output[index] == 0);
}

static void test_unity_and_bounds() {
    KsolotiAiGainDSP engine;
    int32_t input[kBlockSize] = {
        0, 1, -1, 0x07FFFFFF, -0x08000000, 0x01000000, -0x01000000, 42,
        -42, 0x00100000, -0x00100000, 7, -7, 3, -3, 0
    };
    int32_t output[kBlockSize];
    engine.Init();
    engine.Process(input, output, kUnityQ27, kBlockSize);
    for (int index = 0; index < kBlockSize; ++index) assert(output[index] == input[index]);
}

static void test_negative_input() {
    KsolotiAiGainDSP engine;
    int32_t input[kBlockSize] = {0};
    int32_t output[kBlockSize];
    input[0] = -0x04000000;
    engine.Init();
    engine.Process(input, output, kUnityQ27 / 2, kBlockSize);
    assert(output[0] == -0x02000000);
}

int main() {
    test_silence();
    test_unity_and_bounds();
    test_negative_input();
    return 0;
}
