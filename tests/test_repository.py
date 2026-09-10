from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "beaker-setup" / "SKILL.md"
USAGE_SKILL = ROOT / "skills" / "beaker-usage" / "SKILL.md"
VERSION_FILE = ROOT / "VERSION"
sys.path.insert(0, str(ROOT / "scripts"))

from sync_version import sync_skill


class RepositoryContractTests(unittest.TestCase):
    def test_skill_has_portable_frontmatter(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
        self.assertIsNotNone(match)
        frontmatter = match.group(1) if match else ""
        self.assertIn("name: beaker-setup", frontmatter)
        self.assertIn("description:", frontmatter)
        self.assertIn("license: MIT", frontmatter)
        self.assertNotIn("TODO", frontmatter)

    def test_skills_declare_the_matching_sdk_version(self) -> None:
        version = VERSION_FILE.read_text(encoding="utf-8").strip()
        for skill in (SKILL, USAGE_SKILL):
            text = skill.read_text(encoding="utf-8")
            match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
            self.assertIsNotNone(match)
            frontmatter = match.group(1) if match else ""
            self.assertIn(f'version: "{version}"', frontmatter)
            self.assertIn(f'beaker_sdk_version: "{version}"', frontmatter)
            self.assertFalse(sync_skill(skill, version, check=True))
            body = text[match.end() :] if match else text
            self.assertIn(
                f"This skill ({version}) is written for beaker-sdk {version}",
                body,
            )

    def test_references_are_real_and_one_level_deep(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        references = re.findall(r"\]\((references/[^)]+\.md)\)", text)
        self.assertGreaterEqual(len(references), 4)
        for reference in references:
            self.assertTrue((SKILL.parent / reference).is_file(), reference)
            self.assertEqual(len(Path(reference).parts), 2)

    def test_marketplaces_resolve_the_canonical_skill(self) -> None:
        claude = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual(
            claude["plugins"][0]["skills"],
            ["./skills/beaker-setup", "./skills/beaker-usage"],
        )

        codex = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
        self.assertEqual(codex["skills"], "./skills/")

        marketplace = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text()
        )
        self.assertEqual(marketplace["plugins"][0]["source"]["path"], ".")
        self.assertTrue(SKILL.is_file())
        self.assertTrue(USAGE_SKILL.is_file())

    def test_usage_skill_has_portable_frontmatter_and_metadata(self) -> None:
        text = USAGE_SKILL.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
        self.assertIsNotNone(match)
        frontmatter = match.group(1) if match else ""
        self.assertIn("name: beaker-usage", frontmatter)
        self.assertIn("description:", frontmatter)
        self.assertIn("license: MIT", frontmatter)
        self.assertNotIn("TODO", frontmatter)

        metadata = (USAGE_SKILL.parent / "agents" / "openai.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn('display_name: "Beaker Usage"', metadata)
        self.assertIn("$beaker-usage", metadata)

    def test_usage_references_are_real_and_one_level_deep(self) -> None:
        text = USAGE_SKILL.read_text(encoding="utf-8")
        references = re.findall(r"\]\((references/[^)]+\.md)\)", text)
        self.assertGreaterEqual(len(references), 1)
        for reference in references:
            self.assertTrue((USAGE_SKILL.parent / reference).is_file(), reference)
            self.assertEqual(len(Path(reference).parts), 2)

    def test_usage_skill_covers_the_hosted_run_lifecycle(self) -> None:
        reference = (USAGE_SKILL.parent / "references" / "cli-reference.md").read_text(
            encoding="utf-8"
        )
        content = "\n".join((USAGE_SKILL.read_text(encoding="utf-8"), reference))

        for command in (
            "beaker github branches",
            "beaker dataset list",
            "beaker model list --available-only --json",
            "beaker run trigger",
            "beaker run list",
            "beaker run status",
            "beaker run pull",
            "beaker run cancel",
        ):
            self.assertIn(command, content)

        self.assertIn("Repository", content)
        self.assertIn("document", content)
        self.assertIn("agent optimization", content)
        self.assertNotIn("Harness Optimization", content)
        self.assertNotIn("Default optimization", content)
        self.assertNotIn("optimize_only", content)
        self.assertNotIn("benchmark_and_optimize", content)
        self.assertIn("--optimization-model", content)
        self.assertIn("--watch", content)
        self.assertNotIn("--once", content)
        self.assertNotIn("benchmark_only", content)
        self.assertNotIn("--quality-tolerance", content)

    def test_every_local_reference_resolves(self):
        for path in (ROOT / "skills").rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                self.assertTrue(
                    (path.parent / target.split("#")[0]).is_file(), (path, target)
                )

    def test_active_guidance_contains_no_removed_contract_or_flags(self):
        removed = (
            "@spec",
            "@integration",
            "Spec.seed_targets",
            "CaseResult.context",
            "CaseScore.key",
            "CaseResult.failed",
            "context=",
            "runtime.canonical_model_id",
            "targets=None",
            "repository=None",
            "--task-type",
            "OptimizationContext",
            "--benchmark-split",
            "--benchmark-max-cases",
            "--final-eval-split",
        )
        for path in (ROOT / "skills").rglob("*.md"):
            content = path.read_text()
            for token in removed:
                self.assertNotIn(token, content, str(path))

    def test_both_skills_describe_consistent_integration_selection(self):
        for skill in (SKILL, USAGE_SKILL):
            content = skill.read_text()
            content += "\n".join(
                path.read_text() for path in (skill.parent / "references").glob("*.md")
            )
            for token in (
                "--integration-id",
                "default_integration",
                "integrations.<id>",
            ):
                self.assertIn(token, content, str(skill))

    def test_examples_compile_without_sdk_dependencies(self):
        for path in (SKILL.parent / "references").glob("*_integration.py"):
            compile(path.read_text(), str(path), "exec")


if __name__ == "__main__":
    unittest.main()
