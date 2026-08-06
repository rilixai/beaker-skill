from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
MANIFESTS = (
    ROOT / ".codex-plugin" / "plugin.json",
    ROOT / ".claude-plugin" / "marketplace.json",
)
VERSION_PATTERN = re.compile(r'("version"\s*:\s*")[^"]+(")')


def read_version() -> str:
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(f"VERSION must contain a semantic version, got {version!r}")
    return version


def manifest_version(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if path.name == "plugin.json":
        return str(payload["version"])
    return str(payload["metadata"]["version"])


def sync_version(version: str, *, check: bool) -> int:
    mismatches: list[str] = []
    for path in MANIFESTS:
        if manifest_version(path) == version:
            continue
        mismatches.append(str(path.relative_to(ROOT)))
        if not check:
            text = path.read_text(encoding="utf-8")
            updated, count = VERSION_PATTERN.subn(rf"\g<1>{version}\g<2>", text, count=1)
            if count != 1:
                raise ValueError(f"Could not find a version field in {path}")
            path.write_text(updated, encoding="utf-8")
    if mismatches and check:
        print(f"Version {version} is out of sync: {', '.join(mismatches)}")
        return 1
    if mismatches:
        print(f"Updated {', '.join(mismatches)} to {version}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync plugin manifest versions from VERSION.")
    parser.add_argument("--check", action="store_true", help="Fail instead of updating stale manifests.")
    args = parser.parse_args()
    return sync_version(read_version(), check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
