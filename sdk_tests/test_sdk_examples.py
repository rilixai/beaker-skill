"""Explicit SDK compatibility suite; requires the SDK version declared in VERSION."""

import asyncio
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "skills/beaker-setup/references"


class IntegrationExamples(unittest.TestCase):
    def test_examples_use_public_types_and_complete_lifecycle(self):
        import beaker

        self.assertEqual(beaker.__version__, (ROOT / "VERSION").read_text().strip())
        from beaker.sdk._integration_lifecycle import (
            DocumentSnapshot,
            ResolvedIntegration,
            open_integration_attempt,
        )
        from beaker.tracing import current_trace

        for path in EXAMPLES.glob("*_integration.py"):
            with (
                self.subTest(example=path.name),
                tempfile.TemporaryDirectory() as temporary,
            ):
                spec = importlib.util.spec_from_file_location(path.stem, path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[path.stem] = module
                try:
                    spec.loader.exec_module(module)
                    resolved = ResolvedIntegration.load(
                        name=path.stem, entrypoint=f"{path.stem}:integration"
                    )
                    case_input, expected = (
                        ("Refund window", "30 days")
                        if isinstance(
                            module.integration.targets, beaker.DocumentTargets
                        )
                        else ("input", "input")
                    )
                    row = resolved.row_adapter.validate_python(
                        {"id": "case", "input": case_input, "expected": expected}
                    )

                    async def execute(root, resolved, row, module):
                        async with open_integration_attempt(
                            integration=resolved,
                            run_id="example",
                            config_extra={},
                            dataset=beaker.PinnedDatasetInfo(
                                name="example",
                                revision="1",
                                split_row_counts={"train": 1, "test": 0},
                            ),
                            case_files_root=root / "cases",
                        ) as attempt:
                            case = (await attempt.load_cases([row]))[0]
                            runtime = beaker.RolloutRuntime(
                                case_files_dir=attempt.files.view(case.id),
                                trace=current_trace(),
                            )
                            if isinstance(
                                module.integration.targets, beaker.DocumentTargets
                            ):
                                snapshot = DocumentSnapshot.build(
                                    attempt.setup_result, module.integration.targets
                                )
                                targets = root / "targets"
                                snapshot.materialize(targets)
                                async with attempt.setup.open_candidate(
                                    targets_dir=targets, scratch_dir=root / "scratch"
                                ) as candidate:
                                    runtime = beaker.RolloutRuntime(
                                        case_files_dir=runtime.case_files_dir,
                                        trace=runtime.trace,
                                        targets_dir=targets,
                                        candidate_runtime=candidate,
                                    )
                                    result = await module.integration.run_case(
                                        case_input=case.input, runtime=runtime
                                    )
                            else:
                                result = await module.integration.run_case(
                                    case_input=case.input, runtime=runtime
                                )
                            score = await module.integration.score_case(
                                case=case,
                                result=result,
                                case_files_dir=runtime.case_files_dir,
                            )
                            self.assertIsInstance(result, beaker.CaseResult)
                            self.assertIsInstance(score, beaker.CaseScore)
                            self.assertEqual(score.objective, 1.0)
                            self.assertTrue(score.checks)
                            self.assertTrue(
                                all(check.verdict == "pass" for check in score.checks)
                            )
                            failed = await module.integration.score_case(
                                case=case,
                                result=beaker.CaseResult(output="Incorrect answer"),
                                case_files_dir=runtime.case_files_dir,
                            )
                            self.assertEqual(failed.objective, 0.0)
                            self.assertTrue(
                                any(check.verdict == "fail" for check in failed.checks)
                            )
                            self.assertEqual(failed.checks[0].expected, case.expected)

                    asyncio.run(execute(Path(temporary), resolved, row, module))
                finally:
                    sys.modules.pop(path.stem, None)

    def test_document_edits_reach_the_application(self):
        from beaker import DocumentRunSetupResult, RolloutRuntime, TargetDocument
        from beaker.sdk._integration_lifecycle import DocumentSnapshot
        from beaker.tracing import current_trace

        path = EXAMPLES / "document_integration.py"
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        try:
            spec.loader.exec_module(module)
            snapshot = DocumentSnapshot.build(
                DocumentRunSetupResult(
                    target_documents=(
                        TargetDocument(
                            source_id="guide",
                            group="wiki",
                            name="guide.md",
                            content="Refund window: 30 days",
                        ),
                    )
                ),
                module.integration.targets,
            )
            variants = (
                (
                    {
                        "wiki/guide.md": "Refund window: 60 days\nSupport hours: 09:00-17:00 UTC"
                    },
                    {
                        "Refund window": "60 days",
                        "Support hours": "09:00-17:00 UTC",
                        "Cancellation window": "Not found",
                    },
                ),
                (
                    {
                        "wiki/guide.md": "Refund window: 30 days",
                        "wiki/nested/new.txt": "Cancellation window: 24 hours",
                    },
                    {"Refund window": "30 days", "Cancellation window": "24 hours"},
                ),
                (
                    {"wiki/replacement.txt": "Refund window: 14 days"},
                    {"Refund window": "14 days"},
                ),
                ({}, {"Refund window": "Not found"}),
            )
            for documents, answers in variants:
                with (
                    self.subTest(documents=documents),
                    tempfile.TemporaryDirectory() as temporary,
                ):
                    root = Path(temporary)
                    targets = root / "targets"
                    targets.mkdir()
                    for name, content in documents.items():
                        file = targets / name
                        file.parent.mkdir(parents=True, exist_ok=True)
                        file.write_text(content, encoding="utf-8")
                    # These edits are valid candidates, not malformed fixtures.
                    self.assertTrue(
                        snapshot.changes(
                            run_id="example", candidate_root=targets
                        ).changes
                    )

                    async def execute(targets, root, documents, answers):
                        async with module.Setup().open_candidate(
                            targets_dir=targets, scratch_dir=root / "scratch"
                        ) as candidate:
                            self.assertEqual(candidate, documents)
                            runtime = RolloutRuntime(
                                case_files_dir=root / "cases",
                                trace=current_trace(),
                                targets_dir=targets,
                                candidate_runtime=candidate,
                            )
                            for question, expected in answers.items():
                                with self.subTest(question=question):
                                    result = await module.integration.run_case(
                                        case_input=question, runtime=runtime
                                    )
                                    self.assertEqual(result.output, expected)
                                    self.assertEqual(result.output_kind, "value")

                    asyncio.run(execute(targets, root, documents, answers))
        finally:
            sys.modules.pop(path.stem, None)

    def test_unfinished_examples_fail_strict_smoke(self):
        for path in EXAMPLES.glob("*_integration.py"):
            with (
                self.subTest(example=path.name),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                (root / ".beaker").mkdir()
                (root / "dataset").mkdir()
                (root / "pyproject.toml").write_text(
                    '[project]\nname="example"\nversion="1"\n'
                )
                (root / ".beaker/beaker_integration.py").write_text(path.read_text())
                config = root / ".beaker/beaker.yaml"
                config.write_text(
                    "integrations:\n  example:\n    entrypoint: beaker_integration:integration\n"
                    "    source_dir: .\n    package_import_root: .beaker\n"
                    "config_defaults:\n  local_dataset_path: dataset\n"
                )
                case_input, expected = (
                    ("Refund window", "30 days")
                    if path.stem == "document_integration"
                    else ("input", "input")
                )
                for split in ("train", "test"):
                    (root / f"dataset/{split}.jsonl").write_text(
                        json.dumps(
                            {"id": split, "input": case_input, "expected": expected}
                        )
                        + "\n"
                    )
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "beaker.cli",
                        "--config-file",
                        ".beaker/beaker.yaml",
                        "run",
                        "smoke",
                        "--strict",
                        "--integration-id",
                        "example",
                    ],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                output = result.stdout + result.stderr
                self.assertEqual(result.returncode, 2, output)
                self.assertIn("SCAFFOLD", output)
