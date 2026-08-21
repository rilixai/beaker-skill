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

        self.assertIn("| Repository |", content)
        self.assertIn("| Named resources |", content)
        self.assertIn("Default optimization", content)
        self.assertNotIn("Harness Optimization", content)
        self.assertIn("Selected-model run", content)
        self.assertIn("optimize_only", content)
        self.assertIn("benchmark_and_optimize", content)
        self.assertIn("--watch", content)
        self.assertNotIn("--once", content)
        self.assertNotIn("benchmark_only", content)
        self.assertNotIn("--quality-tolerance", content)

    def test_skills_cover_repository_sdk_contract(self) -> None:
        setup = SKILL.read_text(encoding="utf-8")
        datasets = (SKILL.parent / "references" / "datasets-and-spec.md").read_text(
            encoding="utf-8"
        )
        usage = USAGE_SKILL.read_text(encoding="utf-8")
        reference = (USAGE_SKILL.parent / "references" / "cli-reference.md").read_text(
            encoding="utf-8"
        )
        content = "\n".join((setup, datasets, usage, reference))
        normalized = " ".join(content.split())

        self.assertIn("`@spec()` now means repository optimization", setup)
        self.assertIn('@spec(repository="all")', setup)
        self.assertIn('repository=("src/app", "config")', setup)
        self.assertIn("`@spec(repository=None)`", content)
        self.assertIn("`targets=None`", content)
        self.assertIn("Repository mode does not accept `Spec.seed_targets`", setup)
        self.assertIn("JSON-normalizable", content)
        self.assertIn("fresh evaluator process", normalized)
        self.assertIn("TEST only after selecting the winner", normalized)

    def test_skills_cover_required_evaluation_environment(self) -> None:
        setup = SKILL.read_text(encoding="utf-8")
        operations = (SKILL.parent / "references" / "cli-and-hosted-operations.md").read_text(
            encoding="utf-8"
        )
        usage = USAGE_SKILL.read_text(encoding="utf-8")
        content = "\n".join((setup, operations, usage))
        normalized = " ".join(content.split())

        self.assertIn("spec.required_env", content)
        self.assertIn("required_env:", operations)
        self.assertIn("names only", normalized)
        self.assertIn("at most 50 unique names", normalized)
        self.assertIn("`BEAKER_*`", operations)
        self.assertIn("beaker agent env list", content)
        self.assertIn("beaker agent env set DATABASE_URL --value-stdin", operations)
        self.assertIn("fails the run before", normalized)
        self.assertIn("available to the candidate application during evaluation", normalized)
        self.assertIn("evaluation-scoped, least-privilege credentials", normalized)
        self.assertIn("Declare only values that the application actually needs", normalized)

    def test_plain_hosted_launch_defaults_to_optimization_across_surfaces(self) -> None:
        usage = USAGE_SKILL.read_text(encoding="utf-8")
        reference = (USAGE_SKILL.parent / "references" / "cli-reference.md").read_text(
            encoding="utf-8"
        )
        content = "\n".join((usage, reference))
        normalized = " ".join(content.split())

        self.assertIn(
            "A plain GitHub-backed launch uses the default optimization for either editable surface",
            normalized,
        )
        self.assertIn("The seed starts with the configured production-system model behavior", normalized)
        self.assertIn("including model selection and model-call behavior", normalized)
        self.assertIn("when that improves the objective", normalized)
        self.assertIn("Named resources", content)
        self.assertIn("supplies each complete named resource", normalized)
        self.assertIn("Both use the default optimization", normalized)
        self.assertNotIn("use_harness_optimization=false", content)
        self.assertNotIn('"use_harness_optimization": false', content)
        self.assertIn("Selected-model flags choose a different optimizer workflow", normalized)
        self.assertIn("Repository-surface default optimization always evaluates only the winner", normalized)
        self.assertIn("Apply TEST candidate policy by editable surface", normalized)
        self.assertIn("The runtime ignores `--test-all-candidates` for this surface", normalized)
        self.assertIn("`--test-all-candidates` applies to the default optimization", normalized)
        self.assertIn("including resources such as `wiki`", normalized)
        self.assertIn("Named-resource default optimization with all persisted candidates evaluated on TEST", normalized)

    def test_normal_launch_prefers_the_current_remote_branch(self) -> None:
        setup = SKILL.read_text(encoding="utf-8")
        operations = (SKILL.parent / "references" / "cli-and-hosted-operations.md").read_text(
            encoding="utf-8"
        )
        usage = USAGE_SKILL.read_text(encoding="utf-8")
        reference = (USAGE_SKILL.parent / "references" / "cli-reference.md").read_text(encoding="utf-8")
        content = "\n".join((setup, operations, usage, reference))
        normalized = " ".join(content.split())

        self.assertIn("beaker run trigger", content)
        self.assertIn("current checked-out branch", normalized)
        self.assertIn("repository's GitHub default branch", normalized)
        self.assertIn("prints the current branch", normalized)
        self.assertIn("`default branch`", normalized)
        self.assertIn("remote branch override", normalized)
        self.assertIn("Tags and commit SHAs", content)
        self.assertIn("hosted sources must be branches", normalized)

    def test_usage_skill_requires_explicit_remote_choices_and_authorization(self) -> None:
        skill = USAGE_SKILL.read_text(encoding="utf-8")
        normalized = " ".join(skill.split())

        self.assertIn("Use the CLI's branch selection", normalized)
        self.assertIn("Use `--ref <remote-branch>` only for an explicit remote branch override", normalized)
        self.assertIn("Unpushed local commits", normalized)
        self.assertIn("Tags and commit SHAs passed to `--ref` return `422`", normalized)
        self.assertIn("Never pass a tag or commit SHA through `--ref`", normalized)
        self.assertIn("Ask which dataset", normalized)
        self.assertIn("Ask the developer which one to eight", normalized)
        self.assertIn("Launch only after explicit developer authorization", normalized)
        self.assertIn("Never cancel a run without explicit authorization", normalized)
        self.assertIn("Never combine selected models with the default optimization", normalized)

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

    def test_setup_skill_requires_explicit_metric_selection(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        datasets = (SKILL.parent / "references" / "datasets-and-spec.md").read_text(encoding="utf-8")
        normalized_skill = " ".join(skill.split())
        normalized_datasets = " ".join(datasets.split())
        self.assertIn(
            "Never implicitly decide what metric of quality the optimization hill-climbs",
            normalized_skill,
        )
        self.assertIn(
            "ask the developer which one to optimize; never make that decision implicitly",
            normalized_skill,
        )
        self.assertIn("confirmed by the developer", normalized_datasets)
        self.assertIn("the quality metric to hill-climb", normalized_datasets)

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
        self.assertIn('beaker agent setup "<selected-agent>"', skill)
        self.assertIn('beaker agent setup "<New Agent Name>"', skill)
        self.assertIn("beaker agent edit", operations)
        self.assertNotIn("beaker login --agent", content)
        self.assertNotIn("--agent-name", content)

    def test_agent_discovery_and_agent_page_run_history(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        operations = (SKILL.parent / "references" / "cli-and-hosted-operations.md").read_text(encoding="utf-8")
        usage = USAGE_SKILL.read_text(encoding="utf-8")
        cli_reference = (USAGE_SKILL.parent / "references" / "cli-reference.md").read_text(
            encoding="utf-8"
        )

        for text in (skill, operations):
            normalized = " ".join(text.split())
            self.assertIn("beaker auth status", normalized)
            self.assertIn("beaker agent list", normalized)
            self.assertIn("Most new users will not have an agent yet", normalized)
            self.assertIn("If several agents could match, ask the developer", normalized)

        self.assertLess(skill.index("beaker agent list"), skill.index('beaker agent setup "<selected-agent>"'))
        content = "\n".join((skill, operations, usage, cli_reference))
        normalized = " ".join(content.split())
        self.assertIn("Use the selected agent's page to view its runs and score trends", normalized)
        self.assertIn("complete run history and score trends for completed runs", normalized)

    def test_usage_documents_parallel_agent_runs_without_a_fixed_cap(self) -> None:
        skill = USAGE_SKILL.read_text(encoding="utf-8")
        reference = (USAGE_SKILL.parent / "references" / "cli-reference.md").read_text(
            encoding="utf-8"
        )
        content = " ".join("\n".join((skill, reference)).split())

        self.assertIn("An agent may have several active runs", content)
        self.assertIn("including runs that use the same selected model", content)
        self.assertIn("Do not assume a fixed per-agent or per-model run limit", content)
        self.assertNotIn("already uses one of the requested models", content)

    def test_usage_states_and_preserves_the_selected_agent(self) -> None:
        skill = USAGE_SKILL.read_text(encoding="utf-8")
        reference = (USAGE_SKILL.parent / "references" / "cli-reference.md").read_text(
            encoding="utf-8"
        )
        content = "\n".join((skill, reference))
        normalized = " ".join(content.split())

        self.assertIn("Tell the developer which agent you selected", normalized)
        self.assertIn("--agent <selected-agent>", content)
        self.assertIn("use that same agent for dataset and run commands", normalized)
        self.assertIn("`PREPARING_BUILD` or `QUEUED`", content)

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
