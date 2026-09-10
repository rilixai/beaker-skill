"""Document contract example; load the customer's real documents in prepare_run."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from beaker import (
    Case,
    CaseResult,
    CaseScore,
    Check,
    DocumentRunSetup,
    DocumentRunSetupResult,
    Integration,
    JsonValue,
    RolloutRuntime,
    SetupRuntime,
    TargetDocument,
    documents,
)
from pydantic import BaseModel


class Row(BaseModel):
    id: str
    input: str
    expected: dict[str, str]


class Setup(DocumentRunSetup[Row, dict[str, str]]):
    row_model = Row

    @asynccontextmanager
    async def prepare_run(self, *, runtime: SetupRuntime):
        # TODO(beaker): fetch real documents, preserving source IDs and versions.
        yield DocumentRunSetupResult(
            target_documents=(
                TargetDocument(
                    source_id="guide",
                    group="wiki",
                    name="guide.md",
                    content="Example guide",
                ),
            )
        )

    async def load_cases(
        self, row: Row, *, runtime: SetupRuntime
    ) -> AsyncIterator[Case]:
        yield Case(id=row.id, input=row.input, expected=row.expected)

    @asynccontextmanager
    async def open_candidate(self, *, targets_dir: Path, scratch_dir: Path):
        # Read the current tree, including additions and excluding deletions.
        # An application may instead build an index under scratch_dir here and
        # close it when this context exits. Never mutate targets_dir.
        yield {
            path.relative_to(targets_dir).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(targets_dir.rglob("*"))
            if path.is_file()
        }


async def run_case(
    *, case_input: JsonValue, runtime: RolloutRuntime[dict[str, str]]
) -> CaseResult:
    # TODO(beaker): pass case_input and this context into the real application.
    return CaseResult(output=runtime.candidate_runtime, output_kind="text")


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
                name="Document content matches expected",
                verdict="pass" if exact else "fail",
                expected=case.expected,
                predicted=result.output,
            ),
        ),
    )


integration = Integration(
    targets=documents(groups=("wiki",)),
    run_setup=Setup,
    run_case=run_case,
    score_case=score_case,
)
