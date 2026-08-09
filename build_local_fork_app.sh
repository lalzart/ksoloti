#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
readonly BASELINE_APP="${1:-/Applications/Ksoloti-1.1.0.app}"
readonly LOCAL_APP="${2:-/Applications/Ksoloti Local.app}"
readonly BASELINE_JAR="$BASELINE_APP/Contents/Resources/Ksoloti.jar"
readonly LOCAL_RESOURCES="$LOCAL_APP/Contents/Resources"
readonly LOCAL_PLIST="$LOCAL_APP/Contents/Info.plist"
readonly LOCAL_BUNDLE_ID='org.axoloti.ksoloti.local'

set_plist_string() {
    local key="$1"
    local value="$2"

    if /usr/libexec/PlistBuddy -c "Print :$key" "$LOCAL_PLIST" >/dev/null 2>&1; then
        /usr/libexec/PlistBuddy -c "Set :$key $value" "$LOCAL_PLIST"
    else
        /usr/libexec/PlistBuddy -c "Add :$key string $value" "$LOCAL_PLIST"
    fi
}

if [[ ! -d "$BASELINE_APP" || ! -f "$BASELINE_JAR" ]]; then
    printf 'Baseline Ksoloti 1.1.0 application not found: %s\n' "$BASELINE_APP" >&2
    exit 1
fi

if [[ -e "$LOCAL_APP" ]]; then
    existing_bundle_id="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$LOCAL_PLIST" 2>/dev/null || true)"
    if [[ ! -d "$LOCAL_APP" || "$existing_bundle_id" != "$LOCAL_BUNDLE_ID" ]]; then
        printf 'Refusing to overwrite an application that is not the local fork: %s\n' "$LOCAL_APP" >&2
        exit 1
    fi

    if pgrep -f "$LOCAL_APP/Contents/MacOS/Ksoloti" >/dev/null; then
        printf 'Quit %s before updating it.\n' "$LOCAL_APP" >&2
        exit 1
    fi
fi

baseline_version="$(unzip -p "$BASELINE_JAR" META-INF/MANIFEST.MF \
    | tr -d '\r' \
    | awk -F': ' '$1 == "Implementation-Version" && !found { print $2; found = 1 }')"

if [[ "$baseline_version" != 1.1.0-* ]]; then
    printf 'Expected a 1.1.0 baseline, found Implementation-Version %s\n' "$baseline_version" >&2
    exit 1
fi

(
    cd "$SCRIPT_DIR"
    ant jar
)

if ! unzip -Z1 "$SCRIPT_DIR/dist/Ksoloti.jar" \
    | grep -Fx 'axoloti/BuildIdentity.class' >/dev/null; then
    printf 'The built Patcher does not contain the local-fork identity.\n' >&2
    exit 1
fi

if [[ ! -d "$LOCAL_APP" ]]; then
    ditto "$BASELINE_APP" "$LOCAL_APP"
fi

install -m 0644 "$SCRIPT_DIR/dist/Ksoloti.jar" "$LOCAL_RESOURCES/Ksoloti.jar"

set_plist_string CFBundleName 'Ksoloti Local'
set_plist_string CFBundleIdentifier "$LOCAL_BUNDLE_ID"
set_plist_string CFBundleGetInfoString 'Ksoloti 1.1 - Local Fork'
set_plist_string CFBundleDisplayName 'Ksoloti Local'
set_plist_string KsolotiEdition 'Local Fork'

{
    printf 'Edition: Local Fork\n'
    printf 'Baseline: %s\n' "$baseline_version"
    printf 'Source: %s\n' "$SCRIPT_DIR"
    printf 'Revision: %s\n' "$(git -C "$SCRIPT_DIR" describe --always --dirty)"
} > "$LOCAL_RESOURCES/LOCAL_FORK_BUILD.txt"

printf 'Created %s\n' "$LOCAL_APP"
printf 'The public baseline remains unchanged at %s\n' "$BASELINE_APP"
