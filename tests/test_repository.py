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

    def test_skills_declare_the_matching_sdk_version(self) -> None:
        version = VERSION_FILE.read_text(encoding="utf-8").strip()
        sdk_reference = re.compile(r"beaker-sdk(>=|==| )(\d+\.\d+\.\d+)")
        threshold_reference = re.compile(r"(?:older than|newer than)\s+(\d+\.\d+\.\d+)")
        for skill in (SKILL, USAGE_SKILL):
            text = skill.read_text(encoding="utf-8")
            match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
            self.assertIsNotNone(match)
            frontmatter = match.group(1) if match else ""
            self.assertIn(f'version: "{version}"', frontmatter)
            self.assertIn(f'beaker_sdk_version: "{version}"', frontmatter)
            body = text[match.end() :] if match else text
            self.assertIn(
                f"This skill ({version}) is written for beaker-sdk {version}",
                body,
            )
            for reference in sdk_reference.finditer(body):
                self.assertEqual(reference.group(2), version)
            for reference in threshold_reference.finditer(body):
                self.assertEqual(reference.group(1), version)

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
        self.assertIn("configured through the UI or `beaker agent env set`", normalized)
        self.assertIn("identifies which variables must be configured before a run can start", normalized)
        self.assertIn("do not launch until `beaker agent env list` confirms", normalized)
        self.assertIn("every name in `spec.required_env` is configured", normalized)
        self.assertIn("fails the run before", normalized)
        self.assertIn("available to the candidate application during evaluation", normalized)
        self.assertIn("evaluation-scoped, least-privilege credentials", normalized)
        self.assertIn("Declare only values that the application actually needs", normalized)
        self.assertIn("derive credential requirements", normalized)
        self.assertIn("SDK defaults and fallback branches", normalized)
        self.assertIn("Do not rely only on names already present in `spec.required_env`", normalized)
        self.assertIn("Beaker does not copy them to hosted settings", normalized)
        self.assertIn("gateway-routed calls need no credential setup", normalized)
        self.assertIn("smoke does not execute `run_case`", normalized)

    def test_skills_prefer_the_gateway_over_application_provider_keys(self) -> None:
        setup = SKILL.read_text(encoding="utf-8")
        routing = (SKILL.parent / "references" / "model-routing-and-tracing.md").read_text(
            encoding="utf-8"
        )
        operations = (SKILL.parent / "references" / "cli-and-hosted-operations.md").read_text(
            encoding="utf-8"
        )
        handoff = (SKILL.parent / "references" / "validation-and-handoff.md").read_text(
            encoding="utf-8"
        )
        content = "\n".join((setup, routing, operations, handoff))
        normalized = " ".join(content.split())

        self.assertIn("Prefer the gateway over application provider keys", routing)
        self.assertIn("Gateway-routed calls require no credential setup at all", normalized)
        self.assertIn("never create an agent or organization provider key", normalized)
        self.assertIn(
            "A direct provider call from application code has no platform fallback", normalized
        )
        self.assertIn("do not block a launch on one being absent", normalized)
        self.assertIn("the model or provider is not the constraint", normalized)
        self.assertIn("Change the endpoint, not the client type or the call shape", normalized)
        self.assertIn("classify the call site by its SDK surface, not its provider", normalized)
        self.assertIn("Before declaring a provider key, check whether the gateway", normalized)
        self.assertIn("Any call site the gateway cannot serve is named at handoff", normalized)
        self.assertIn(
            "`inference_target(runtime)` requires both a selected model and hosted run credentials",
            normalized,
        )

    def test_skills_require_preserving_the_application_client_type(self) -> None:
        setup = SKILL.read_text(encoding="utf-8")
        routing = (SKILL.parent / "references" / "model-routing-and-tracing.md").read_text(
            encoding="utf-8"
        )
        handoff = (SKILL.parent / "references" / "validation-and-handoff.md").read_text(
            encoding="utf-8"
        )
        content = "\n".join((setup, routing, handoff))
        normalized = " ".join(content.split())

        self.assertIn("Preserve the client type", routing)
        self.assertIn("Wrap the *call*, not the client", routing)
        self.assertIn("a type the application already constructs", normalized)
        self.assertIn("Do not put a transparent proxy, `__getattr__` forwarder", normalized)
        self.assertIn("keep the original unwrapped client, run untraced", normalized)
        self.assertIn("Client-type checks reject such wrappers", normalized)
        self.assertIn("exception is a framework-specific adapter", normalized)
        self.assertIn("The only exception is a framework-specific, type-preserving adapter", normalized)
        self.assertIn("passes the application's resolver or type check before a hosted baseline", normalized)
        self.assertIn("Tracing and model injection preserve the client type", handoff)
        self.assertIn("The only exception is a framework-specific, type-preserving adapter", normalized)

    def test_setup_skill_has_a_hosted_yaml_preflight(self) -> None:
        operations = (SKILL.parent / "references" / "cli-and-hosted-operations.md").read_text(
            encoding="utf-8"
        )
        handoff = (SKILL.parent / "references" / "validation-and-handoff.md").read_text(
            encoding="utf-8"
        )
        content = "\n".join((SKILL.read_text(encoding="utf-8"), operations, handoff))
        normalized = " ".join(content.split())

        self.assertIn("Beaker YAML preflight", content)
        self.assertIn('source_dir: "services/example"', operations)
        self.assertIn('package_import_root: ".beaker"', operations)
        self.assertIn("Resolve `spec.source_dir` from the Git checkout root", normalized)
        self.assertIn("Resolve `spec.package_import_root` inside `spec.source_dir`", normalized)
        self.assertIn("Install the evaluator's dependencies", normalized)
        self.assertIn("The list is an allowlist", normalized)
        self.assertIn("Runs are immutable snapshots", normalized)
        self.assertIn("does not prove that the hosted image builds", normalized)

    def test_plain_hosted_launch_defaults_to_optimization_across_surfaces(self) -> None:
        usage = USAGE_SKILL.read_text(encoding="utf-8")
        reference = (USAGE_SKILL.parent / "references" / "cli-reference.md").read_text(
            encoding="utf-8"
        )
        content = "\n".join((usage, reference))
        normalized = " ".join(content.split())

        self.assertIn(
            "A plain GitHub-backed launch starts agent optimization of the production system for either editable surface",
            normalized,
        )
        self.assertIn("The seed starts with the configured production-system model behavior", normalized)
        self.assertIn("including model selection and model-call behavior", normalized)
        self.assertIn("when that improves the objective", normalized)
        self.assertIn("Named resources", content)
        self.assertIn("supplies each complete named resource", normalized)
        self.assertIn("Both use agent optimization", normalized)
        self.assertNotIn("use_harness_optimization=false", content)
        self.assertNotIn('"use_harness_optimization": false', content)
        self.assertIn(
            "launch agent optimization unless they explicitly ask to benchmark or compare specific models",
            normalized,
        )
        self.assertIn(
            "unless the developer asked for that flag in this conversation",
            normalized,
        )
        self.assertIn("`beaker run list --agent <key> --json` reports `total`", normalized)
        self.assertIn(
            "Never add `--optimization-model` or `--test-all-candidates` to a run the developer did not ask for",
            normalized,
        )
        self.assertIn(
            "Comparison models need `@spec(repository=None)` with populated `Spec.seed_targets`",
            normalized,
        )
        self.assertIn("A repository-mode `@spec()` spec cannot take `--optimization-model`", normalized)
        self.assertIn("Repository-surface agent optimization always evaluates only the winner", normalized)
        self.assertIn("Apply TEST candidate policy by editable surface", normalized)
        self.assertIn("The runtime ignores `--test-all-candidates` for this surface", normalized)
        self.assertIn("`--test-all-candidates` applies to agent optimization", normalized)
        self.assertIn("including resources such as `wiki`", normalized)
        self.assertIn("Named-resource agent optimization with all persisted candidates evaluated on TEST", normalized)

    def test_setup_skill_defaults_the_first_hosted_run_to_agent_optimization(self) -> None:
        setup = SKILL.read_text(encoding="utf-8")
        operations = (SKILL.parent / "references" / "cli-and-hosted-operations.md").read_text(
            encoding="utf-8"
        )
        content = "\n".join((setup, operations))
        normalized = " ".join(content.split())
        self.assertIn("The first hosted run is agent optimization of the production system", normalized)
        self.assertIn(
            "Do not pass `--optimization-model` unless the developer explicitly asked to compare specific models",
            normalized,
        )
        self.assertIn(
            "Comparison models currently need `@spec(repository=None)` with populated `Spec.seed_targets`",
            normalized,
        )
        self.assertIn("Call the named target the **Beaker agent**", setup)
        self.assertIn("and the run type **agent optimization**", setup)
        self.assertNotIn("Harness Optimization", content)

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
        self.assertIn("Ask the developer which models to use (one to eight", normalized)
        self.assertIn("Launch only after explicit developer authorization", normalized)
        self.assertIn("Never cancel a run without explicit authorization", normalized)
        self.assertIn("Never use `--optimization-model` when `Spec.seed_targets` is absent", normalized)
        self.assertIn("Never pass `--optimization-model` unless the developer explicitly asked to compare specific models", normalized)

    def test_usage_skill_preserves_agent_operational_details(self) -> None:
        skill = USAGE_SKILL.read_text(encoding="utf-8")
        reference = (USAGE_SKILL.parent / "references" / "cli-reference.md").read_text(encoding="utf-8")
        content = "\n".join((skill, reference))
        normalized = " ".join(content.split()).lower()

        self.assertIn("--config-file", content)
        self.assertIn("BEAKER_CONFIG_FILE", skill)
        self.assertIn("exit code `3` as an active run", skill)
        self.assertIn("full run `id`", skill)
        self.assertIn("`web_url`", skill)
        self.assertIn("repository setup is finished and the hosted run has started", normalized)
        self.assertIn("remaining wait is for beaker's hosted results, not more integration work", normalized)
        self.assertIn("do not imply that repository integration is still underway", normalized)
        self.assertIn("Do not hand-author", skill)
        self.assertIn("Do not overwrite an existing result directory", skill)
        self.assertIn("use `$beaker-setup`", skill)

    def test_skills_forbid_tests_and_cicd_automation(self) -> None:
        setup = SKILL.read_text(encoding="utf-8")
        datasets = (SKILL.parent / "references" / "datasets-and-spec.md").read_text(
            encoding="utf-8"
        )
        handoff = (SKILL.parent / "references" / "validation-and-handoff.md").read_text(
            encoding="utf-8"
        )
        usage = USAGE_SKILL.read_text(encoding="utf-8")
        content = "\n".join((setup, datasets, handoff, usage))
        normalized = " ".join(content.split())

        self.assertIn("never adding or modifying tests or CI/CD automation", setup)
        self.assertIn("Write no tests and no CI/CD automation", setup)
        self.assertIn("do not write a test that imports `beaker_spec.py`", normalized)
        self.assertIn("Never add CI/CD automation for Beaker", normalized)
        self.assertIn("No CI/CD automation was created or modified", normalized)
        self.assertIn(
            "Running the repository's existing linters, formatters, or type checkers",
            normalized,
        )
        self.assertIn("Do not run the repository's test suite as part of onboarding", normalized)
        self.assertIn("do not run the repository's test suite during onboarding", normalized)
        self.assertIn("running the repository's test suite is not part of onboarding", normalized)
        self.assertIn("the repository's test suite was not run", normalized)

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
            "ask the developer which metric to optimize; never make that decision implicitly",
            normalized_skill,
        )
        self.assertIn("confirmed by the developer", normalized_datasets)
        self.assertIn("the quality metric to hill-climb", normalized_datasets)
        self.assertIn("keep replacing `TODO(beaker)`", normalized_skill)
        self.assertIn("while waiting", normalized_datasets)

    def test_setup_skill_keeps_predictions_compact_and_diagnostics_in_context(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        datasets = (SKILL.parent / "references" / "datasets-and-spec.md").read_text(encoding="utf-8")
        handoff = (SKILL.parent / "references" / "validation-and-handoff.md").read_text(encoding="utf-8")
        content = " ".join((skill + datasets + handoff).split())

        self.assertIn("keep `output` limited to fields the scorer reads", content)
        self.assertIn("trajectories, tool history, end state, and other diagnostic evidence", content)
        self.assertIn("do not duplicate large evidence in both", content)

    def test_setup_skill_installs_before_loading_and_batches_known_questions(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        skill = SKILL.read_text(encoding="utf-8")
        normalized = " ".join(skill.split())

        self.assertIn("finish before the newly installed skill is loaded", " ".join(readme.split()).lower())
        self.assertIn("Never install or update the skill in parallel with loading it", normalized)
        self.assertIn("all currently known unresolved decisions together", normalized)
        self.assertIn("Do not wait for discovery to be exhaustive", normalized)
        self.assertIn("continue independent discovery and implementation while the developer responds", normalized)
        self.assertIn("Batching is best effort", normalized)
        self.assertIn("if later discovery reveals another required decision, ask it then", normalized)

    def test_setup_skill_finalizes_data_before_one_push(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        operations = (SKILL.parent / "references" / "cli-and-hosted-operations.md").read_text(encoding="utf-8")
        handoff = (SKILL.parent / "references" / "validation-and-handoff.md").read_text(encoding="utf-8")
        usage = USAGE_SKILL.read_text(encoding="utf-8")
        usage_reference = (USAGE_SKILL.parent / "references" / "cli-reference.md").read_text(encoding="utf-8")
        happy_path = skill[
            skill.index("## Happy path") : skill.index("## Keep the onboarding loop explicit")
        ]
        normalized = " ".join(skill.split())

        self.assertLess(happy_path.index("Upload or select the labeled dataset"), happy_path.index("Commit and push once"))
        self.assertIn("ask the developer to begin those actions immediately", normalized)
        self.assertIn("Do not push an incomplete integration and then push again", normalized)
        self.assertIn("pass that same selector explicitly to smoke and launch", normalized)
        self.assertIn("Do not commit an organization-specific dataset selector to YAML by default", normalized)
        datasets = (SKILL.parent / "references" / "datasets-and-spec.md").read_text(encoding="utf-8")
        normalized_datasets = " ".join(datasets.split())
        self.assertIn("pass the same selector explicitly to smoke and launch", normalized_datasets)
        self.assertNotIn("For hosted data, configure one immutable selector instead", datasets)
        for content in (skill, operations, handoff, usage, usage_reference):
            normalized_content = " ".join(content.split())
            self.assertIn("Do not perform `integration_pushed`", normalized_content)
            self.assertIn("`dataset_available` or `required_env_configured` is incomplete", normalized_content)

    def test_setup_skill_documents_the_happy_path_and_status_cadence(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        operations = (SKILL.parent / "references" / "cli-and-hosted-operations.md").read_text(
            encoding="utf-8"
        )
        handoff = (SKILL.parent / "references" / "validation-and-handoff.md").read_text(
            encoding="utf-8"
        )
        self.assertLess(
            skill.index("## Happy path"),
            skill.index("## Keep the onboarding loop explicit"),
        )
        happy_path = skill[
            skill.index("## Happy path") : skill.index("## Keep the onboarding loop explicit")
        ]
        for phrase in (
            "spec.source_dir",
            "agent_key",
            "beaker agent setup",
            "which metric to optimize",
            "beaker run trigger",
            "Do not pass `--optimization-model` unless",
        ):
            self.assertIn(phrase, happy_path)
        self.assertIn("Check the generated `spec.source_dir`", happy_path)
        self.assertIn("After `beaker init`, verify", operations)
        self.assertIn("Set source_dir to services/invoices", skill)
        self.assertIn("Setup records the agent key in `agent_key`", happy_path)
        self.assertIn("developer supplied the agent name", skill)
        for text in (skill, operations, handoff):
            self.assertIn("after a completed onboarding step", text)
            self.assertIn("read-only probes", text)
        all_setup_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "skills").rglob("*")
            if path.is_file()
        )
        for phrase in (
            "after every Beaker command",
            "after every CLI command",
            "after each CLI command",
            "after every command",
        ):
            self.assertNotIn(phrase, all_setup_text)

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

    def test_tracing_guidance_preflights_nominal_client_wrappers(self) -> None:
        routing = (SKILL.parent / "references" / "model-routing-and-tracing.md").read_text(encoding="utf-8")
        normalized = " ".join(routing.split())

        self.assertIn("delegates through `__getattr__`", routing)
        self.assertIn("`isinstance(...)`", routing)
        self.assertIn("subclass the public client base", normalized)
        self.assertIn("exact resolver or type check the application uses", normalized)
        self.assertIn("Before a hosted baseline", routing)
        self.assertIn("Only execute the traced call after that preflight succeeds", normalized)

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

    def test_smoke_supports_local_and_exact_remote_datasets(self) -> None:
        setup_content = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SKILL, *(SKILL.parent / "references").glob("*.md")]
        )
        usage_reference = (
            USAGE_SKILL.parent / "references" / "cli-reference.md"
        ).read_text(encoding="utf-8")
        normalized = " ".join(setup_content.split())

        self.assertNotIn("spec_validated", setup_content)
        self.assertNotIn("spec_validated", usage_reference)
        self.assertIn(
            "beaker run smoke --strict --agent <selected-agent> --dataset <name@revision>",
            normalized,
        )
        self.assertIn("--dataset-id <artifact-id>", normalized)
        self.assertIn("local_dataset_path", setup_content)
        self.assertIn("config_defaults.dataset_ref", setup_content)
        self.assertIn("config_defaults.dataset_id", setup_content)
        self.assertIn("optional repository defaults", setup_content)
        self.assertIn("Local-path smoke is offline", setup_content)
        self.assertIn("presigned URLs", setup_content)

    def test_smoke_and_launch_reuse_one_immutable_dataset_selector(self) -> None:
        operations = (
            SKILL.parent / "references" / "cli-and-hosted-operations.md"
        ).read_text(encoding="utf-8")
        normalized = " ".join(operations.split())

        self.assertIn("dataset_revision", operations)
        self.assertIn("artifact_id", operations)
        self.assertIn("reusing the selector that passed smoke", normalized)
        self.assertIn("must not be combined", normalized)
        self.assertIn("--dataset <dataset-name@revision>", operations)

    def test_skill_explains_nested_beaker_config_paths(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        operations = (SKILL.parent / "references" / "cli-and-hosted-operations.md").read_text(encoding="utf-8")
        for text in (skill, operations):
            self.assertIn("beaker_config_path", text)
            self.assertIn("--config-file", text)
            self.assertIn("BEAKER_CONFIG_FILE", text)
            self.assertIn("services/invoices/.beaker/beaker.yaml", text)
            self.assertIn("relative to the Git root", " ".join(text.split()))

    def test_skill_explains_legacy_nested_source_dir_migration(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        operations = (SKILL.parent / "references" / "cli-and-hosted-operations.md").read_text(encoding="utf-8")
        for text in (skill, operations):
            normalized = " ".join(text.split())
            self.assertIn('source_dir: "."', text)
            self.assertIn("means the Git root", normalized)
            self.assertIn("Set source_dir to services/invoices", normalized)
            self.assertIn("paths containing `..`", normalized)

    def test_setup_skill_stages_only_intended_integration_files(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        handoff = (SKILL.parent / "references" / "validation-and-handoff.md").read_text(
            encoding="utf-8"
        )
        normalized = " ".join((skill + "\n" + handoff).split())

        self.assertIn("git status --short", skill)
        self.assertIn("git diff --cached --name-only", skill)
        self.assertNotIn("git add .beaker pyproject.toml uv.lock", skill)
        self.assertIn("intentionally ignores other untracked files", normalized)
        self.assertIn("Never stage an unrelated dataset or source file", normalized)

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

    def test_agent_discovery_carries_the_repository_config_path(self) -> None:
        setup = SKILL.read_text(encoding="utf-8")
        usage = USAGE_SKILL.read_text(encoding="utf-8")
        content = " ".join((setup + "\n" + usage).split())
        start_safely = setup.split("## Start safely", 1)[1].split("## Implement the real integration", 1)[0]
        normalized_start = " ".join(start_safely.split())

        self.assertIn("beaker agent list --json", content)
        self.assertIn("uvx --from beaker-sdk beaker agent list --json", setup)
        self.assertIn("github_repository", content)
        self.assertIn("beaker_config_path", content)
        self.assertIn("global `--config-file` selector", content)
        discovery_command = "uvx --from beaker-sdk beaker agent list --json"
        self.assertLess(start_safely.index(discovery_command), start_safely.index("beaker init --print"))
        self.assertIn("before `beaker init` or the first `beaker onboarding status`", normalized_start)

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
        self.assertIn("use that same Beaker agent for dataset and run commands", normalized)
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
        self.assertIn('"--json"', datasets)
        self.assertIn("dataset_revision", datasets)
        self.assertIn('"beaker", "run", "smoke"', datasets)
        self.assertIn("authoritative check", datasets)
        self.assertIn("before the temporary directory is removed", operations)


if __name__ == "__main__":
    unittest.main()
