// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

class KsolotiAiGainDSP {
public:
    void Init() {}

    void Process(const int32_t* input, int32_t* output, int32_t level, int size) {
        for (int i = 0; i < size; ++i) {
            int64_t scaled = (static_cast<int64_t>(input[i]) * level) >> 27;
            if (scaled > 0x07FFFFFF) scaled = 0x07FFFFFF;
            if (scaled < -0x08000000) scaled = -0x08000000;
            output[i] = static_cast<int32_t>(scaled);
        }
    }
};
