/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "firmware/patch_abi_v1.h"
#include <string.h>

int main(void) {
    ksai_patch_abi_v1_t abi;
    ksai_event_v1_t event;
    memset(&abi, 0, sizeof(abi));
    memset(&event, 0, sizeof(event));
    abi.magic = KSAI_PATCH_ABI_V1_MAGIC;
    abi.abi_major = KSAI_PATCH_ABI_V1_MAJOR;
    event.kind = KSAI_EVENT_SET_PARAMETER;
    return (abi.magic != KSAI_PATCH_ABI_V1_MAGIC) || (event.kind == 0);
}
