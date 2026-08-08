#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Parse every complete kpatch example embedded in the AI documentation."""

import re
import sys
from pathlib import Path


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

import ksai  # noqa: E402


FENCE_RE = re.compile(r"```kpatch\s*\n(.*?)```", re.DOTALL)


def main() -> int:
    checked = 0
    failures = []
    for path in sorted(AI_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for index, source in enumerate(FENCE_RE.findall(text), 1):
            _, _, diagnostics = ksai.parse_patch_text(source)
            errors = [item.to_dict() for item in diagnostics if item.severity == "error"]
            checked += 1
            if errors:
                failures.append({"file": str(path), "example": index, "diagnostics": errors})
    if checked == 0:
        failures.append({"diagnostics": [{"code": "E_DOCS_EMPTY", "message": "no kpatch examples found"}]})
    if failures:
        import json

        print(json.dumps({"ok": False, "checked": checked, "failures": failures}, sort_keys=True))
        return 2
    print(f"documentation examples: {checked} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
