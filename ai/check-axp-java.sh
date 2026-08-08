#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
set -eu

if [ "$#" -ne 1 ]; then
    echo "usage: ai/check-axp-java.sh PATCH.axp" >&2
    exit 2
fi

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
classes_dir="$repo_dir/build/classes"
simple_xml="$repo_dir/lib/simple-xml-2.7.1.jar"
source_file="$repo_dir/ai/java/AxpDeserializeCheck.java"
jar_classpath=$(find "$repo_dir/lib" -type f -name '*.jar' -print | sort | tr '\n' ':')

if [ ! -d "$classes_dir" ]; then
    echo "build/classes is missing; run the repository's Ant test target first" >&2
    exit 2
fi

check_dir=$(mktemp -d "${TMPDIR:-/tmp}/ksoloti-axp-check.XXXXXX")
trap 'rm -rf -- "$check_dir"' EXIT HUP INT TERM

javac -cp "$classes_dir:$simple_xml" -d "$check_dir" "$source_file"
java -Djava.awt.headless=true -cp "$check_dir:$classes_dir:$jar_classpath" AxpDeserializeCheck "$1"
