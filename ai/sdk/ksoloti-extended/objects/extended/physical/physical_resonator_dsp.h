// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdint.h>

// The Ksoloti firmware carries the MIT-licensed Mutable Instruments Rings DSP
// and prelinks its resource table. Include the two complete core implementation
// units once in the generated patch translation unit. Ksoloti deliberately
// removed Rings' fx/reverb support, so this wrapper builds voice management
// directly from Resonator and String instead of depending on rings::Part.
#include "rings/dsp/resonator.cpp"
#include "rings/dsp/string.cpp"
#include "rings/dsp/limiter.h"
#include "rings/dsp/plucker.h"
#include "stmlib/dsp/units.h"

class KsolotiExtendedPhysicalResonatorDSP {
public:
    void Init() {
        previous_strum_ = false;
        current_voice_ = 0;
        next_voice_ = 0;
        polyphony_ = 1;
        for (int voice = 0; voice < kMaxVoices; ++voice) {
            note_[voice] = 0.0f;
            resonator_[voice].Init();
            plucker_[voice].Init();
            dispersive_[voice].Init(true);
            for (int string = 0; string < 2; ++string) {
                sympathetic_[voice * 2 + string].Init(false);
            }
        }
        limiter_.Init();
    }

    void Process(
        const int32_t* input,
        int32_t strum,
        int32_t pitch_in,
        int32_t structure_in,
        int32_t brightness_in,
        int32_t damping_in,
        int32_t position_in,
        int32_t pitch,
        int32_t structure,
        int32_t brightness,
        int32_t damping,
        int32_t position,
        int32_t model,
        int32_t voices,
        int32_t external,
        int32_t* output,
        int32_t* aux,
        int size) {
        if (size <= 0 || size > static_cast<int>(rings::kMaxBlockSize)) {
            for (int i = 0; i < size; ++i) output[i] = aux[i] = 0;
            return;
        }

        const int next_polyphony = ClampInt(voices + 1, 1, 4);
        if (next_polyphony != polyphony_) {
            polyphony_ = next_polyphony;
            if (current_voice_ >= polyphony_) current_voice_ = 0;
            if (next_voice_ >= polyphony_) next_voice_ = 0;
        }

        const int selected_model = ClampInt(model, 0, 2);
        const float structure_value = Unit(SaturatingAdd(structure, structure_in));
        const float brightness_value = Unit(SaturatingAdd(brightness, brightness_in));
        const float damping_value = Unit(SaturatingAdd(damping, damping_in));
        const float position_value = Unit(SaturatingAdd(position, position_in));
        const float note = Bipolar(SaturatingAddBipolar(pitch, pitch_in)) * 64.0f;

        const bool strum_high = strum > 0;
        const bool rising_strum = strum_high && !previous_strum_;
        if (rising_strum) {
            current_voice_ = next_voice_;
            next_voice_ = (next_voice_ + 1) % polyphony_;
        }
        note_[current_voice_] = note;
        previous_strum_ = strum_high;

        const float active_frequency = Frequency(note_[current_voice_]);
        if (rising_strum && external == 0) {
            float cutoff = brightness_value * (2.0f - brightness_value);
            cutoff = active_frequency * stmlib::SemitonesToRatio((cutoff - 0.5f) * 72.0f) * 8.0f;
            if (cutoff > 0.499f) cutoff = 0.499f;
            plucker_[current_voice_].Trigger(active_frequency, cutoff, position_value);
        }

        for (int i = 0; i < size; ++i) output_[i] = aux_[i] = 0.0f;
        for (int voice = 0; voice < polyphony_; ++voice) {
            BuildExcitation(voice, input, external == 0, size);
            for (int i = 0; i < size; ++i) voice_output_[i] = voice_aux_[i] = 0.0f;

            const float frequency = Frequency(note_[voice]);
            if (selected_model == 0) {
                ProcessModal(
                    voice, frequency, structure_value, brightness_value,
                    damping_value, position_value, size);
            } else if (selected_model == 1) {
                ProcessSympathetic(
                    voice, frequency, structure_value, brightness_value,
                    damping_value, position_value, size);
            } else {
                ProcessDispersive(
                    voice, frequency, structure_value, brightness_value,
                    damping_value, position_value, size);
            }
            MixVoice(voice, size);
        }

        limiter_.Process(output_, aux_, size, selected_model == 1 ? 1.0f : 1.4f);
        for (int i = 0; i < size; ++i) {
            output[i] = ToQ27(output_[i]);
            aux[i] = ToQ27(aux_[i]);
        }
    }

private:
    static const int kMaxVoices = 4;

    void BuildExcitation(int voice, const int32_t* input, bool internal, int size) {
        if (internal) {
            plucker_[voice].Process(excitation_, size);
        } else {
            for (int i = 0; i < size; ++i) excitation_[i] = 0.0f;
        }
        if (voice == current_voice_) {
            for (int i = 0; i < size; ++i) excitation_[i] += Bipolar(input[i]);
        }
    }

    void ProcessModal(
        int voice, float frequency, float structure, float brightness,
        float damping, float position, int size) {
        rings::Resonator& resonator = resonator_[voice];
        resonator.set_frequency(frequency);
        resonator.set_structure(structure);
        resonator.set_brightness(brightness * brightness);
        resonator.set_damping(damping);
        resonator.set_position(position);
        resonator.set_resolution(64 / polyphony_ - 4);
        resonator.Process(excitation_, voice_output_, voice_aux_, size);
    }

    void ProcessSympathetic(
        int voice, float frequency, float structure, float brightness,
        float damping, float position, int size) {
        rings::String& primary = sympathetic_[voice * 2];
        primary.set_frequency(frequency);
        primary.set_dispersion(0.0f);
        primary.set_brightness(brightness);
        primary.set_damping(damping);
        primary.set_position(position);
        primary.Process(excitation_, voice_output_, voice_aux_, size);

        for (int i = 0; i < size; ++i) {
            sympathetic_input_[i] = (voice_output_[i] - voice_aux_[i]) * 0.2f;
        }
        rings::String& secondary = sympathetic_[voice * 2 + 1];
        secondary.set_frequency(
            frequency * stmlib::SemitonesToRatio((structure - 0.5f) * 24.0f));
        secondary.set_dispersion(0.0f);
        secondary.set_brightness(brightness * (2.0f - brightness));
        secondary.set_damping(0.7f + damping * 0.27f);
        secondary.set_position(1.0f - position);
        secondary.Process(sympathetic_input_, voice_output_, voice_aux_, size);
    }

    void ProcessDispersive(
        int voice, float frequency, float structure, float brightness,
        float damping, float position, int size) {
        float dispersion = structure < 0.24f
            ? (structure - 0.24f) * 4.166f
            : (structure > 0.26f ? (structure - 0.26f) * 1.35135f : 0.0f);
        rings::String& string = dispersive_[voice];
        string.set_frequency(frequency);
        string.set_dispersion(dispersion);
        string.set_brightness(brightness);
        string.set_damping(damping);
        string.set_position(position);
        string.Process(excitation_, voice_output_, voice_aux_, size);
    }

    void MixVoice(int voice, int size) {
        if (polyphony_ == 1) {
            for (int i = 0; i < size; ++i) {
                output_[i] += voice_output_[i];
                aux_[i] += voice_aux_[i];
            }
        } else {
            float* destination = voice & 1 ? aux_ : output_;
            for (int i = 0; i < size; ++i) {
                destination[i] += voice_output_[i] - voice_aux_[i];
            }
        }
    }

    static float Frequency(float note) {
        return stmlib::SemitonesToRatio(note + 60.0f - 69.0f) * rings::a3;
    }

    static int ClampInt(int value, int minimum, int maximum) {
        if (value < minimum) return minimum;
        if (value > maximum) return maximum;
        return value;
    }

    static int32_t SaturatingAdd(int32_t a, int32_t b) {
        int64_t value = static_cast<int64_t>(a) + b;
        if (value > 0x07ffffff) value = 0x07ffffff;
        if (value < 0) value = 0;
        return static_cast<int32_t>(value);
    }

    static int32_t SaturatingAddBipolar(int32_t a, int32_t b) {
        int64_t value = static_cast<int64_t>(a) + b;
        if (value > 0x07ffffff) value = 0x07ffffff;
        if (value < -0x08000000) value = -0x08000000;
        return static_cast<int32_t>(value);
    }

    static float Unit(int32_t value) {
        return static_cast<float>(value) * (1.0f / 134217728.0f);
    }

    static float Bipolar(int32_t value) {
        return static_cast<float>(value) * (1.0f / 134217728.0f);
    }

    static int32_t ToQ27(float value) {
        if (value >= 1.0f) return 0x07ffffff;
        if (value <= -1.0f) return -0x08000000;
        return static_cast<int32_t>(value * 134217728.0f);
    }

    rings::Resonator resonator_[kMaxVoices];
    rings::String sympathetic_[kMaxVoices * 2];
    rings::String dispersive_[kMaxVoices];
    rings::Plucker plucker_[kMaxVoices];
    rings::Limiter limiter_;
    float note_[kMaxVoices];
    float excitation_[rings::kMaxBlockSize];
    float sympathetic_input_[rings::kMaxBlockSize];
    float voice_output_[rings::kMaxBlockSize];
    float voice_aux_[rings::kMaxBlockSize];
    float output_[rings::kMaxBlockSize];
    float aux_[rings::kMaxBlockSize];
    bool previous_strum_;
    int current_voice_;
    int next_voice_;
    int polyphony_;
};
