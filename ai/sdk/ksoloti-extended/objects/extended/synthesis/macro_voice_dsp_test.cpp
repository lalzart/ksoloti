// SPDX-License-Identifier: GPL-3.0-or-later
#include <assert.h>
#include <stdint.h>

#include "macro_voice_dsp.h"

int main() {
    KsolotiExtendedMacroVoiceDSP voice;
    voice.Init();
    int32_t output[16] = {};
    int32_t aux[16] = {};
    const int32_t half = INT32_C(1) << 26;
    for (int engine = 0; engine < 24; ++engine) {
        for (int block = 0; block < 48; ++block) {
            voice.Process(block == 0, 0, 0, 0, 0, 0, 0, 0,
                engine, 0, half, half, half, 0, 0, 0, half, half, 0, 0,
                output, aux, 16);
            for (int i = 0; i < 16; ++i) {
                assert(output[i] <= 0x07ffffff && output[i] >= -0x08000000);
                assert(aux[i] <= 0x07ffffff && aux[i] >= -0x08000000);
            }
        }
    }
    return 0;
}
