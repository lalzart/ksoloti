#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo 'usage: ai/compile-axp.sh PATCH.axp' >&2
    exit 2
fi

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
classes_dir="$repo_dir/build/classes"
if [ ! -d "$classes_dir" ]; then
    echo 'build/classes is missing; run the repository Ant test target first' >&2
    exit 2
fi

patcher_resources=${KSAI_PATCHER_HOME:-/Applications/Ksoloti-1.1.0.app/Contents/Resources}
libraries_dir=${KSAI_LIBRARIES:-${HOME}/ksoloti/1.1.0}
firmware_dir=${KSAI_FIRMWARE:-"$repo_dir/firmware"}
link_firmware_dir=${KSAI_LINK_FIRMWARE:-"$patcher_resources/firmware"}
platform_dir=${KSAI_PLATFORM:-"$patcher_resources/platform_mac_x64"}
object_paths=${KSAI_OBJECT_PATHS:-}
java_home_dir=${JAVA_HOME:-"$patcher_resources/jre"}
java_bin="$java_home_dir/bin/java"

if [ ! -x "$java_bin" ]; then
    java_bin=$(command -v java || true)
fi
if [ -z "$java_bin" ] || [ ! -x "$java_bin" ]; then
    echo 'no Java launcher was found' >&2
    exit 2
fi

jar_classpath=$(find "$repo_dir/lib" -type f -name '*.jar' -print | sort | tr '\n' ':')
exec "$java_bin" \
    -Djava.awt.headless=true \
    -Daxoloti_home="$patcher_resources" \
    -Daxoloti_libraries="$libraries_dir" \
    -Daxoloti_firmware="$firmware_dir" \
    -Daxoloti_link_firmware="$link_firmware_dir" \
    -Daxoloti_platform="$platform_dir" \
    -Dksai.object_paths="$object_paths" \
    -cp "$classes_dir:$jar_classpath" \
    axoloti.Axoloti -compileOnly "$1"
