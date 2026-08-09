// SPDX-License-Identifier: GPL-3.0-or-later
#include <assert.h>
#include <stdint.h>

#include "../objects/extended/physical/drip_water_dsp.h"
#include "../objects/extended/effects/waveset_repeat_dsp.h"
#include "../objects/extended/effects/talkbox_lpc_dsp.h"
#include "../objects/extended/effects/comb_network_dsp.h"
#include "../objects/extended/grain/seeded_scatter_dsp.h"
#include "../objects/extended/grain/clocked_delay_dsp.h"

static bool AnyNonzero(const int32_t* values, int size) { for (int i = 0; i < size; ++i) if (values[i]) return true; return false; }

int main() {
    int32_t input[16] = {};
    int32_t other[16] = {};
    int32_t left[16] = {};
    int32_t right[16] = {};
    input[0] = INT32_C(1) << 25;
    const int32_t half = INT32_C(1) << 26;

    KsolotiExtendedDripWaterDSP drip;
    drip.Init();
    drip.Process(1, 0, 0, half, half, half, 7, left, right, 16);
    assert(AnyNonzero(left, 16) || AnyNonzero(right, 16));

    KsolotiExtendedWavesetRepeatDSP waveset;
    waveset.Init();
    bool capturing = false, repeating = false;
    for (int block = 0; block < 32; ++block) {
        for (int i = 0; i < 16; ++i) input[i] = ((block * 16 + i) & 8) ? half : -half;
        waveset.Process(input, block == 0, 1, 2, 0, 0x07ffffff, left, capturing, repeating, 16);
    }
    assert(!capturing);

    KsolotiExtendedTalkboxLPCDSP talkbox;
    talkbox.Init();
    for (int block = 0; block < 32; ++block) {
        for (int i = 0; i < 16; ++i) { input[i] = ((block * 16 + i) & 4) ? half : -half; other[i] = ((block * 16 + i) & 16) ? half / 2 : -half / 2; }
        talkbox.Process(input, other, 10, half, half, left, 16);
    }
    for (int i = 0; i < 16; ++i) assert(left[i] <= 0x07ffffff && left[i] >= -0x08000000);

    KsolotiExtendedCombNetworkDSP comb;
    comb.Init();
    for (int block = 0; block < 80; ++block) { for (int i = 0; i < 16; ++i) input[i] = block == 0 && i == 0 ? half : 0; comb.Process(input, half, half, half, half, 0x07ffffff, left, right, 16); }
    assert(AnyNonzero(left, 16) || AnyNonzero(right, 16));

    KsolotiExtendedSeededScatterDSP scatter;
    scatter.Init();
    bool scatter_energy = false;
    for (int block = 0; block < 300; ++block) { for (int i = 0; i < 16; ++i) input[i] = ((block * 16 + i) & 16) ? half : -half; scatter.Process(input, block == 200, 0, half, half, half, 0, 3, left, right, 16); scatter_energy = scatter_energy || AnyNonzero(left, 16) || AnyNonzero(right, 16); }
    assert(scatter_energy);

    KsolotiExtendedClockedDelayDSP clocked;
    clocked.Init();
    bool delay_energy = false;
    for (int block = 0; block < 600; ++block) { for (int i = 0; i < 16; ++i) input[i] = ((block * 16 + i) & 16) ? half : -half; clocked.Process(input, block == 500, half, half, half, 0, 0, left, right, 16); delay_energy = delay_energy || AnyNonzero(left, 16) || AnyNonzero(right, 16); }
    assert(delay_energy);
    return 0;
}
