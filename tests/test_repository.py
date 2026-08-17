from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "beaker-setup" / "SKILL.md"
USAGE_SKILL = ROOT / "skills" / "beaker-usage" / "SKILL.md"
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
        self.assertEqual(
            claude["plugins"][0]["skills"],
            ["./skills/beaker-setup", "./skills/beaker-usage"],
        )

        codex = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
        self.assertEqual(codex["skills"], "./skills/")

        marketplace = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text())
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

        metadata = (USAGE_SKILL.parent / "agents" / "openai.yaml").read_text(encoding="utf-8")
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
        reference = (USAGE_SKILL.parent / "references" / "cli-reference.md").read_text(encoding="utf-8")
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

        self.assertIn("Ordinary prompt optimization", content)
        self.assertIn("Harness Optimization", content)
        self.assertIn("Selected-model run", content)
        self.assertIn("optimize_only", content)
        self.assertIn("benchmark_and_optimize", content)
        self.assertIn("--watch", content)
        self.assertNotIn("--once", content)
        self.assertNotIn("benchmark_only", content)
        self.assertNotIn("--quality-tolerance", content)

    def test_usage_skill_requires_explicit_remote_choices_and_authorization(self) -> None:
        skill = USAGE_SKILL.read_text(encoding="utf-8")
        normalized = " ".join(skill.split())

        self.assertIn("Ask which remote GitHub branch to use", normalized)
        self.assertIn("unpushed local commits", normalized)
        self.assertIn("Ask which dataset", normalized)
        self.assertIn("Ask the developer which one to eight", normalized)
        self.assertIn("Launch only after explicit developer authorization", normalized)
        self.assertIn("Never cancel a run without explicit authorization", normalized)
        self.assertIn("Never combine selected models with Harness Optimization", normalized)

    def test_usage_skill_preserves_agent_operational_details(self) -> None:
        skill = USAGE_SKILL.read_text(encoding="utf-8")
        reference = (USAGE_SKILL.parent / "references" / "cli-reference.md").read_text(encoding="utf-8")
        content = "\n".join((skill, reference))

        self.assertIn("--config-file", content)
        self.assertIn("BEAKER_CONFIG_FILE", skill)
        self.assertIn("exit code `3` as an active run", skill)
        self.assertIn("full run `id`", skill)
        self.assertIn("`web_url`", skill)
        self.assertIn("Do not hand-author", skill)
        self.assertIn("Do not overwrite an existing result directory", skill)
        self.assertIn("use `$beaker-setup`", skill)

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
        self.assertIn("local application or evaluation runs", routing)

    def test_tracing_is_scoped_to_candidate_agent(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        routing = (SKILL.parent / "references" / "model-routing-and-tracing.md").read_text(encoding="utf-8")
        for content in (skill, routing):
            normalized = " ".join(content.split())
            self.assertIn("candidate workflow rooted at the main workflow agent", normalized)
            self.assertIn("sub-agents, tools, retrievers, and nested model calls", normalized)
            self.assertIn("Spec.run_case", normalized)
        normalized_routing = " ".join(routing.split())
        normalized_skill = " ".join(skill.split())
        self.assertIn("Never instrument scorer, rubric judge, evaluator, post-processing, or post-rollout model calls", normalized_skill)
        self.assertIn("capture containing only judge or scorer calls", normalized_routing)
        self.assertIn("Never add Beaker tracing to scorers, rubric judges, evaluators, post-processing, or post-rollout model calls", normalized_routing)
        self.assertNotIn("inner=True", normalized_routing)
        self.assertNotIn("inner=True", normalized_skill)

    def test_skill_uses_structural_smoke_validation(self) -> None:
        skill_dir = SKILL.parent
        content = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SKILL, *(skill_dir / "references").glob("*.md")]
        )
        self.assertNotIn("beaker run dry-run", content)
        self.assertNotIn("smoke --trace", content)
        self.assertIn("beaker run smoke --strict", content)
        self.assertIn("does not execute `run_case`", content)
        self.assertIn("PASS", content)
        self.assertIn("FAIL", content)

    def test_skill_explains_nested_beaker_config_paths(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        operations = (SKILL.parent / "references" / "cli-and-hosted-operations.md").read_text(encoding="utf-8")
        for text in (skill, operations):
            self.assertIn("beaker_config_path", text)
            self.assertIn("--config-file", text)
            self.assertIn("BEAKER_CONFIG_FILE", text)
            self.assertIn("services/invoices/.beaker/beaker.yaml", text)
            self.assertIn("relative to the Git root", " ".join(text.split()))

    def test_setup_skill_uses_structural_smoke_validation(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        handoff = (SKILL.parent / "references" / "validation-and-handoff.md").read_text(encoding="utf-8")
        content = "\n".join((skill, handoff))

        self.assertIn("beaker run smoke --strict", content)
        self.assertIn("does not execute a rollout, model call, or scoring call", content)
        self.assertIn("beaker trace doctor --require-model-calls", content)
        self.assertNotIn("beaker run dry-run", content)

    def test_skill_uses_current_login_and_agent_setup_commands(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        operations = (SKILL.parent / "references" / "cli-and-hosted-operations.md").read_text(encoding="utf-8")
        content = "\n".join((skill, operations))

        self.assertIn("beaker login", content)
        self.assertIn('beaker agent setup "<Existing Agent Name or key>"', skill)
        self.assertIn('beaker agent setup "<New Agent Name>"', skill)
        self.assertIn("beaker agent edit", operations)
        self.assertNotIn("beaker login --agent", content)
        self.assertNotIn("--agent-name", content)

    def test_agent_discovery_precedes_creation_and_scopes_are_opt_in(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        operations = (SKILL.parent / "references" / "cli-and-hosted-operations.md").read_text(encoding="utf-8")

        for text in (skill, operations):
            normalized = " ".join(text.split())
            self.assertIn("beaker auth status", normalized)
            self.assertIn("beaker agent list", normalized)
            self.assertIn("no explicit scope", normalized)
            self.assertIn("reuse", normalized)
            self.assertIn("create a different agent", normalized)
            self.assertIn("custom scope", normalized)

        self.assertLess(skill.index("beaker agent list"), skill.index('beaker agent setup "<Existing Agent'))
        self.assertIn("Never set `scope_key` or pass `--scope-key` in an ordinary setup", skill)

    def test_skill_keeps_beaker_out_of_production_runtime(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        datasets = (SKILL.parent / "references" / "datasets-and-spec.md").read_text(encoding="utf-8")
        routing = (SKILL.parent / "references" / "model-routing-and-tracing.md").read_text(encoding="utf-8")
        handoff = (SKILL.parent / "references" / "validation-and-handoff.md").read_text(encoding="utf-8")

        self.assertIn("Treat Beaker as development/evaluation tooling, not an application runtime", skill)
        self.assertIn("Keep every Beaker-owned file under the selected project's `.beaker/`", skill)
        self.assertIn("Never import or initialize Beaker from production entrypoints", skill)
        self.assertIn("Never create or modify test", datasets)
        self.assertIn("Keep all Beaker imports", routing)
        self.assertIn("Do not modify a central LLM wrapper", routing)
        self.assertIn("Production entrypoints and deployment/runtime configuration", handoff)

    def test_skill_never_adds_consumer_tests(self) -> None:
        skill_dir = SKILL.parent
        content = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SKILL, *(skill_dir / "references").glob("*.md")]
        )
        self.assertIn("Never create or modify tests", content)
        self.assertIn("existing tests are read-only sources of truth", content)
        self.assertNotIn(".beaker/tests", content)
        self.assertNotIn("Add a smoke assertion", content)

    def test_generated_jsonl_is_temporary_and_uploaded_before_cleanup(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        datasets = (SKILL.parent / "references" / "datasets-and-spec.md").read_text(encoding="utf-8")
        operations = (SKILL.parent / "references" / "cli-and-hosted-operations.md").read_text(encoding="utf-8")

        self.assertIn("Never save generated JSONL dataset files", skill)
        self.assertIn("tempfile.TemporaryDirectory", datasets)
        self.assertIn("subprocess.run", datasets)
        self.assertIn("before the temporary directory is removed", operations)


if __name__ == "__main__":
    unittest.main()
