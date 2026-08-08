/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * Dormant Ksoloti patch ABI v1 contract.
 *
 * This header deliberately does not modify patchMeta_t or the running firmware.
 * A later negotiated integration may publish one offset-based ABI blob while
 * retaining the 1.1.0 entry points for patches that do not advertise it.
 */

#ifndef KSOLOTI_PATCH_ABI_V1_H
#define KSOLOTI_PATCH_ABI_V1_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define KSAI_PATCH_ABI_V1_MAGIC UINT32_C(0x4B534131) /* "KSA1" */
#define KSAI_PATCH_ABI_V1_MAJOR UINT16_C(1)
#define KSAI_PATCH_ABI_V1_MINOR UINT16_C(0)
#define KSAI_PATCH_ABI_V1_ALIGNMENT UINT32_C(4)

typedef struct {
    uint8_t bytes[16];
} ksai_id128_t;

typedef enum {
    KSAI_PARAMETER_Q27_SIGNED = 1,
    KSAI_PARAMETER_Q27_UNSIGNED = 2,
    KSAI_PARAMETER_INT32 = 3,
    KSAI_PARAMETER_BOOL = 4,
    KSAI_PARAMETER_ENUM = 5
} ksai_parameter_kind_v1_t;

enum {
    KSAI_PARAMETER_AUTOMATABLE = UINT16_C(1) << 0,
    KSAI_PARAMETER_READ_ONLY = UINT16_C(1) << 1,
    KSAI_PARAMETER_PER_VOICE = UINT16_C(1) << 2,
    KSAI_PARAMETER_DISCRETE = UINT16_C(1) << 3
};

typedef struct {
    ksai_id128_t stable_id;
    int32_t minimum;
    int32_t maximum;
    int32_t default_value;
    uint16_t kind;
    uint16_t flags;
    uint32_t display_order;
    uint32_t reserved[3];
} ksai_parameter_descriptor_v1_t;

typedef enum {
    KSAI_EVENT_SET_PARAMETER = 1,
    KSAI_EVENT_TRIGGER = 2,
    KSAI_EVENT_NOTE_ON = 3,
    KSAI_EVENT_NOTE_OFF = 4,
    KSAI_EVENT_PRESSURE = 5,
    KSAI_EVENT_TIMBRE = 6,
    KSAI_EVENT_PITCH = 7,
    KSAI_EVENT_ALL_NOTES_OFF = 8
} ksai_event_kind_v1_t;

enum {
    KSAI_EVENT_INTERPOLATE = UINT16_C(1) << 0,
    KSAI_EVENT_RELATIVE = UINT16_C(1) << 1
};

typedef struct {
    uint32_t sequence;
    uint32_t frame_offset;
    ksai_id128_t target_id;
    int32_t value;
    uint16_t kind;
    uint16_t flags;
} ksai_event_v1_t;

typedef struct {
    uint32_t abi_errors;
    uint32_t events_dropped;
    uint32_t events_late;
    uint32_t maximum_queue_depth;
    uint32_t maximum_process_cycles;
    uint32_t current_process_cycles;
    uint32_t reserved[2];
} ksai_telemetry_v1_t;

/*
 * All offsets are unsigned byte offsets from the first byte of this header.
 * Zero means absent unless a field is required. Event capacity must be a power
 * of two. Producer and consumer publish monotonically increasing sequences in
 * the two uint32_t locations named below; memory barriers are integration-owned.
 */
typedef struct {
    uint32_t magic;
    uint16_t abi_major;
    uint16_t abi_minor;
    uint32_t byte_size;
    uint32_t flags;
    ksai_id128_t patch_id;
    uint32_t parameter_count;
    uint32_t parameter_descriptors_offset;
    uint32_t event_capacity;
    uint32_t events_offset;
    uint32_t producer_sequence_offset;
    uint32_t consumer_sequence_offset;
    uint32_t telemetry_offset;
    uint32_t reserved;
} ksai_patch_abi_v1_t;

#if defined(__cplusplus)
#define KSAI_ABI_STATIC_ASSERT(condition, message) static_assert(condition, message)
#elif defined(__STDC_VERSION__) && __STDC_VERSION__ >= 201112L
#define KSAI_ABI_STATIC_ASSERT(condition, message) _Static_assert(condition, message)
#else
#define KSAI_ABI_STATIC_ASSERT_JOIN_(left, right) left##right
#define KSAI_ABI_STATIC_ASSERT_JOIN(left, right) KSAI_ABI_STATIC_ASSERT_JOIN_(left, right)
#define KSAI_ABI_STATIC_ASSERT(condition, message) \
    typedef char KSAI_ABI_STATIC_ASSERT_JOIN(ksai_abi_assert_, __LINE__)[(condition) ? 1 : -1]
#endif

KSAI_ABI_STATIC_ASSERT(sizeof(ksai_id128_t) == 16, "ksai_id128_t size");
KSAI_ABI_STATIC_ASSERT(sizeof(ksai_parameter_descriptor_v1_t) == 48,
                       "ksai_parameter_descriptor_v1_t size");
KSAI_ABI_STATIC_ASSERT(sizeof(ksai_event_v1_t) == 32, "ksai_event_v1_t size");
KSAI_ABI_STATIC_ASSERT(sizeof(ksai_telemetry_v1_t) == 32, "ksai_telemetry_v1_t size");
KSAI_ABI_STATIC_ASSERT(sizeof(ksai_patch_abi_v1_t) == 64, "ksai_patch_abi_v1_t size");

#undef KSAI_ABI_STATIC_ASSERT

#ifdef __cplusplus
}
#endif

#endif /* KSOLOTI_PATCH_ABI_V1_H */
