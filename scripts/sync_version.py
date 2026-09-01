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
SKILLS = (
    ROOT / "skills" / "beaker-setup" / "SKILL.md",
    ROOT / "skills" / "beaker-usage" / "SKILL.md",
)
VERSION_PATTERN = re.compile(r'("version"\s*:\s*")[^"]+(")')
FRONTMATTER_PATTERN = re.compile(r"\A---\n(?P<frontmatter>.*?)\n---\n", flags=re.DOTALL)
SKILL_VERSION_PATTERN = re.compile(r'(?m)^  version: "\d+\.\d+\.\d+"$')
SKILL_SDK_VERSION_PATTERN = re.compile(r'(?m)^  beaker_sdk_version: "\d+\.\d+\.\d+"$')
SKILL_TEXT_VERSION_PATTERN = re.compile(
    r"beaker-sdk(?P<operator>>=|==| )(?P<sdk_version>\d+\.\d+\.\d+)"
    r"|This skill \((?P<skill_version>\d+\.\d+\.\d+)\)"
)


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


def skill_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_PATTERN.match(text)
    if match is None:
        raise ValueError(f"Could not find frontmatter in {path}")
    version = re.search(r'(?m)^  beaker_sdk_version: "([^"]+)"$', match.group("frontmatter"))
    if version is None:
        raise ValueError(f"Could not find beaker_sdk_version in {path}")
    return version.group(1)


def sync_skill(path: Path, version: str, *, check: bool) -> bool:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_PATTERN.match(text)
    if match is None:
        raise ValueError(f"Could not find frontmatter in {path}")
    frontmatter = match.group("frontmatter")
    sdk_version = skill_version(path)
    in_sync = (
        sdk_version == version
        and f'  version: "{version}"' in frontmatter
        and f'  beaker_sdk_version: "{version}"' in frontmatter
        and all(
            (match.group("sdk_version") or match.group("skill_version")) == version
            for match in SKILL_TEXT_VERSION_PATTERN.finditer(text)
        )
    )
    if in_sync:
        return False

    if check:
        return True

    updated_frontmatter, version_count = SKILL_VERSION_PATTERN.subn(
        f'  version: "{version}"', frontmatter, count=1
    )
    updated_frontmatter, sdk_version_count = SKILL_SDK_VERSION_PATTERN.subn(
        f'  beaker_sdk_version: "{version}"', updated_frontmatter, count=1
    )
    if version_count != 1 or sdk_version_count != 1:
        raise ValueError(f"Could not find skill metadata versions in {path}")
    updated = text[: match.start("frontmatter")] + updated_frontmatter + text[match.end("frontmatter") :]

    def replace_text_version(text_match: re.Match[str]) -> str:
        if text_match.group("operator") is not None:
            return f"beaker-sdk{text_match.group('operator')}{version}"
        return f"This skill ({version})"

    updated = SKILL_TEXT_VERSION_PATTERN.sub(replace_text_version, updated)
    path.write_text(updated, encoding="utf-8")
    return True


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
    for path in SKILLS:
        if sync_skill(path, version, check=check):
            mismatches.append(str(path.relative_to(ROOT)))
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
