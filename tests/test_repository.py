from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "beaker-setup" / "SKILL.md"
VERSION_FILE = ROOT / "VERSION"


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

    def test_references_are_real_and_one_level_deep(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        references = re.findall(r"\]\((references/[^)]+\.md)\)", text)
        self.assertGreaterEqual(len(references), 4)
        for reference in references:
            self.assertTrue((SKILL.parent / reference).is_file(), reference)
            self.assertEqual(len(Path(reference).parts), 2)

    def test_marketplaces_resolve_the_canonical_skill(self) -> None:
        claude = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual(claude["plugins"][0]["skills"], ["./skills/beaker-setup"])

        codex = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
        self.assertEqual(codex["skills"], "./skills/")

        marketplace = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text())
        self.assertEqual(marketplace["plugins"][0]["source"]["path"], ".")
        self.assertTrue(SKILL.is_file())

    def test_manifest_versions_match_central_version(self) -> None:
        version = VERSION_FILE.read_text(encoding="utf-8").strip()
        codex = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
        claude = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual(codex["version"], version)
        self.assertEqual(claude["metadata"]["version"], version)

    def test_public_content_has_no_private_source_dependency(self) -> None:
        allowed_suffixes = {".md", ".json", ".yml", ".yaml", ".py"}
        content = "\n".join(
            path.read_text(encoding="utf-8")
            for path in ROOT.rglob("*")
            if path.is_file()
            and path.suffix in allowed_suffixes
            and ".git" not in path.parts
            and "tests" not in path.parts
        )
        self.assertNotIn("git@github.com/" + "rilixai/rilixai", content)
        self.assertNotIn("packages/" + "beaker", content)
        self.assertNotIn("BEAKER_SETUP" + "_CORE", content)

    def test_llm_judge_routing_uses_public_gateway_helper(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        routing = (SKILL.parent / "references" / "model-routing-and-tracing.md").read_text(encoding="utf-8")
        self.assertIn("scoring_inference_target", skill)
        self.assertIn("scoring_inference_target", routing)
        self.assertIn("LLM-as-a-judge scoring", routing)
        self.assertIn("local dry-runs", routing)


if __name__ == "__main__":
    unittest.main()
