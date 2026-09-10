"""Run with matching beaker-sdk installed to verify the documented lifecycle."""

import asyncio
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    importlib.util.find_spec("beaker"),
    "Install matching beaker-sdk to execute contract examples",
)
class IntegrationExamples(unittest.TestCase):
    def test_examples_use_public_types_and_complete_lifecycle(self):
        import beaker

        self.assertEqual(beaker.__version__, (ROOT / "VERSION").read_text().strip())
        from beaker.sdk._integration_lifecycle import (
            ResolvedIntegration,
            open_integration_attempt,
            DocumentSnapshot,
        )
        from beaker.tracing import current_trace

        for path in (ROOT / "skills/beaker-setup/references").glob("*_integration.py"):
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
                    expected = (
                        "Example guide"
                        if isinstance(
                            module.integration.targets, beaker.DocumentTargets
                        )
                        else "input"
                    )
                    row = resolved.row_adapter.validate_python(
                        {"id": "case", "input": "input", "expected": expected}
                    )

                    async def execute():
                        root = Path(temporary)
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

                    asyncio.run(execute())
                finally:
                    sys.modules.pop(path.stem, None)
