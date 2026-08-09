// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

// Official Plaits DSP snapshot. TEST selects the safe null user-data provider;
// a patch object must never read or write the original module's flash address.
#ifndef TEST
#define KSOLOTI_EXTENDED_DEFINED_PLAITS_TEST
#define TEST 1
#endif

#include "vendor/stmlib/dsp/atan.cc"
#include "vendor/stmlib/dsp/units.cc"
#include "vendor/stmlib/utils/random.cc"
#include "vendor/plaits/resources.cc"
#include "vendor/plaits/dsp/chords/chord_bank.cc"
#include "vendor/plaits/dsp/engine/additive_engine.cc"
#include "vendor/plaits/dsp/engine/bass_drum_engine.cc"
#include "vendor/plaits/dsp/engine/chord_engine.cc"
#include "vendor/plaits/dsp/engine/fm_engine.cc"
#include "vendor/plaits/dsp/engine/grain_engine.cc"
#include "vendor/plaits/dsp/engine/hi_hat_engine.cc"
#include "vendor/plaits/dsp/engine/modal_engine.cc"
#include "vendor/plaits/dsp/engine/noise_engine.cc"
#include "vendor/plaits/dsp/engine/particle_engine.cc"
#include "vendor/plaits/dsp/engine/snare_drum_engine.cc"
#include "vendor/plaits/dsp/engine/speech_engine.cc"
#include "vendor/plaits/dsp/engine/string_engine.cc"
#include "vendor/plaits/dsp/engine/swarm_engine.cc"
#include "vendor/plaits/dsp/engine/virtual_analog_engine.cc"
#include "vendor/plaits/dsp/engine/waveshaping_engine.cc"
#include "vendor/plaits/dsp/engine/wavetable_engine.cc"
#include "vendor/plaits/dsp/engine2/chiptune_engine.cc"
#include "vendor/plaits/dsp/engine2/phase_distortion_engine.cc"
#include "vendor/plaits/dsp/engine2/six_op_engine.cc"
#include "vendor/plaits/dsp/engine2/string_machine_engine.cc"
#include "vendor/plaits/dsp/engine2/virtual_analog_vcf_engine.cc"
#include "vendor/plaits/dsp/engine2/wave_terrain_engine.cc"
#include "vendor/plaits/dsp/fm/algorithms.cc"
#include "vendor/plaits/dsp/fm/dx_units.cc"
#include "vendor/plaits/dsp/physical_modelling/modal_voice.cc"
#include "vendor/plaits/dsp/physical_modelling/resonator.cc"
#include "vendor/plaits/dsp/physical_modelling/string.cc"
#include "vendor/plaits/dsp/physical_modelling/string_voice.cc"
#include "vendor/plaits/dsp/speech/lpc_speech_synth.cc"
#include "vendor/plaits/dsp/speech/lpc_speech_synth_controller.cc"
#include "vendor/plaits/dsp/speech/lpc_speech_synth_phonemes.cc"
#include "vendor/plaits/dsp/speech/lpc_speech_synth_words.cc"
#include "vendor/plaits/dsp/speech/naive_speech_synth.cc"
#include "vendor/plaits/dsp/speech/sam_speech_synth.cc"
#include "vendor/plaits/dsp/voice.cc"

#ifdef KSOLOTI_EXTENDED_DEFINED_PLAITS_TEST
#undef TEST
#undef KSOLOTI_EXTENDED_DEFINED_PLAITS_TEST
#endif

class KsolotiExtendedMacroVoiceDSP {
public:
    void Init() {
        plaits_stmlib::BufferAllocator allocator(shared_buffer_, sizeof(shared_buffer_));
        voice_.Init(&allocator);
    }

    void Process(
        int32_t trigger,
        int32_t engine_in,
        int32_t pitch_in,
        int32_t harmonics_in,
        int32_t timbre_in,
        int32_t morph_in,
        int32_t frequency_in,
        int32_t level_in,
        int32_t engine,
        int32_t pitch,
        int32_t harmonics,
        int32_t timbre,
        int32_t morph,
        int32_t frequency_modulation,
        int32_t timbre_modulation,
        int32_t morph_modulation,
        int32_t decay,
        int32_t lpg_colour,
        int32_t drone,
        int32_t external_level,
        int32_t* output,
        int32_t* aux,
        int size) {
        if (size <= 0 || size > static_cast<int>(plaits::kMaxBlockSize)) {
            for (int i = 0; i < size; ++i) output[i] = aux[i] = 0;
            return;
        }
        plaits::Patch patch;
        patch.note = 64.0f + Semitones(pitch);
        patch.harmonics = Unit(harmonics);
        patch.timbre = Unit(timbre);
        patch.morph = Unit(morph);
        patch.frequency_modulation_amount = Bipolar(frequency_modulation);
        patch.timbre_modulation_amount = Bipolar(timbre_modulation);
        patch.morph_modulation_amount = Bipolar(morph_modulation);
        patch.engine = ClampInt(engine + engine_in, 0, plaits::kMaxEngines - 1);
        patch.decay = Unit(decay);
        patch.lpg_colour = Unit(lpg_colour);

        plaits::Modulations modulation;
        modulation.engine = 0.0f;
        modulation.note = Semitones(pitch_in);
        modulation.frequency = Bipolar(frequency_in);
        modulation.harmonics = Bipolar(harmonics_in);
        modulation.timbre = Bipolar(timbre_in);
        modulation.morph = Bipolar(morph_in);
        modulation.trigger = trigger > 0 ? 1.0f : 0.0f;
        modulation.level = Unit(level_in);
        modulation.frequency_patched = frequency_modulation != 0;
        modulation.timbre_patched = timbre_modulation != 0;
        modulation.morph_patched = morph_modulation != 0;
        modulation.trigger_patched = drone == 0;
        modulation.level_patched = external_level != 0;
        voice_.Render(patch, modulation, frames_, size);
        for (int i = 0; i < size; ++i) {
            output[i] = static_cast<int32_t>(frames_[i].out) << 12;
            aux[i] = static_cast<int32_t>(frames_[i].aux) << 12;
        }
    }

private:
    static int ClampInt(int value, int minimum, int maximum) {
        if (value < minimum) return minimum;
        if (value > maximum) return maximum;
        return value;
    }
    static float Unit(int32_t value) {
        if (value <= 0) return 0.0f;
        if (value >= 0x08000000) return 1.0f;
        return value * (1.0f / 134217728.0f);
    }
    static float Bipolar(int32_t value) {
        if (value >= 0x08000000) return 1.0f;
        if (value <= -0x08000000) return -1.0f;
        return value * (1.0f / 134217728.0f);
    }
    static float Semitones(int32_t value) {
        return value * (1.0f / 2097152.0f);
    }

    plaits::Voice voice_;
    uint8_t shared_buffer_[16384];
    plaits::Voice::Frame frames_[plaits::kMaxBlockSize];
};
