"""Combined contract example: Beaker edits application code and its FAQ documents."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from beaker import (
    Case,
    CaseResult,
    CaseScore,
    Check,
    RunSetup,
    DocumentRunSetupResult,
    Integration,
    JsonValue,
    RepositoryRunSetupResult,
    RolloutRuntime,
    SetupRuntime,
    TargetDocument,
    documents,
    repository,
)
from pydantic import BaseModel


class Row(BaseModel):
    id: str
    input: str
    expected: str


class Setup(RunSetup[Row]):
    row_model = Row

    @asynccontextmanager
    async def prepare_run(
        self, *, runtime: SetupRuntime
    ) -> AsyncIterator[dict[str, RepositoryRunSetupResult | DocumentRunSetupResult]]:
        # One result per declared target, keyed by target kind.
        # TODO(beaker): fetch real documents, preserving source IDs and versions.
        yield {
            "repository": RepositoryRunSetupResult(),
            "documents": DocumentRunSetupResult(
                target_documents=(
                    TargetDocument(
                        source_id="guide",
                        group="wiki",
                        name="guide.md",
                        content="Refund window: 30 days\nSupport hours: 09:00-17:00 UTC",
                    ),
                )
            ),
        }

    async def load_cases(
        self, row: Row, *, runtime: SetupRuntime
    ) -> AsyncIterator[Case]:
        yield Case(id=row.id, input=row.input, expected=row.expected)


def answer_question(question: str, targets_dir: Path) -> str:
    """Illustrative lookup in FAQ lines formatted as 'topic: answer'."""
    for path in sorted((targets_dir / "wiki").rglob("*")):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            topic, separator, answer = line.partition(":")
            if separator and topic.strip().casefold() == question.strip().casefold():
                return answer.strip()
    return "Not found"


async def run_case(*, case_input: JsonValue, runtime: RolloutRuntime) -> CaseResult:
    # TODO(beaker): call the candidate application's real entrypoint from the
    # candidate checkout. This candidate's documents are under runtime.targets_dir
    # (one directory per group).
    if not isinstance(case_input, str):
        raise TypeError("case_input must be a question string")
    if runtime.targets_dir is None:
        raise RuntimeError("Combined targets require runtime.targets_dir")
    answer = answer_question(case_input, runtime.targets_dir)
    return CaseResult(output=answer, output_kind="value")


async def score_case(
    *, case: Case, result: CaseResult, case_files_dir: Path
) -> CaseScore:
    # TODO(beaker): use the task's agreed metric; exact match is illustrative.
    exact = float(result.output == case.expected)
    return CaseScore(
        objective=exact,
        field_scores={"exact": exact},
        checks=(
            Check(
                name="Answer matches expected",
                verdict="pass" if exact else "fail",
                expected=case.expected,
                predicted=result.output,
            ),
        ),
    )


integration = Integration(
    targets=(repository(), documents(groups=("wiki",))),
    run_setup=Setup,
    run_case=run_case,
    score_case=score_case,
)
