"""Document contract example; load the customer's real documents in prepare_run."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from pydantic import BaseModel
from beaker import (
    Case,
    CaseResult,
    CaseScore,
    DocumentRunSetup,
    DocumentRunSetupResult,
    Integration,
    JsonValue,
    RolloutRuntime,
    SetupRuntime,
    TargetDocument,
    documents,
)


class Row(BaseModel):
    id: str
    input: str
    expected: str


class Setup(DocumentRunSetup[Row, str]):
    row_model = Row

    @asynccontextmanager
    async def prepare_run(self, *, runtime: SetupRuntime):
        # Replace this with the real content store, preserving source IDs/versions.
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
        # A real application may build an index under scratch_dir here.
        yield (targets_dir / "wiki" / "guide.md").read_text()


async def run_case(
    *, case_input: JsonValue, runtime: RolloutRuntime[str]
) -> CaseResult:
    # Pass case_input and this candidate context into the real application.
    return CaseResult(output=runtime.candidate_runtime, output_kind="text")


async def score_case(
    *, case: Case, result: CaseResult, case_files_dir: Path
) -> CaseScore:
    exact = float(result.output == case.expected)
    return CaseScore(objective=exact, field_scores={"exact": exact})


integration = Integration(
    targets=documents(groups=("wiki",)),
    run_setup=Setup,
    run_case=run_case,
    score_case=score_case,
)
