"""Contract example: replace the echo application and metric with the real task."""

from collections.abc import AsyncIterator
from pathlib import Path
from pydantic import BaseModel
from beaker import (
    Case,
    CaseResult,
    CaseScore,
    Integration,
    JsonValue,
    RepositoryRunSetup,
    RolloutRuntime,
    SetupRuntime,
    repository,
)


class Row(BaseModel):
    id: str
    input: str
    expected: str


class Setup(RepositoryRunSetup[Row]):
    row_model = Row

    async def load_cases(
        self, row: Row, *, runtime: SetupRuntime
    ) -> AsyncIterator[Case]:
        yield Case(id=row.id, input=row.input, expected=row.expected)


async def run_case(*, case_input: JsonValue, runtime: RolloutRuntime) -> CaseResult:
    # Import and call the candidate application's actual entrypoint here.
    return CaseResult(output=case_input, output_kind="value")


async def score_case(
    *, case: Case, result: CaseResult, case_files_dir: Path
) -> CaseScore:
    exact = float(result.output == case.expected)
    return CaseScore(objective=exact, field_scores={"exact": exact})


integration = Integration(
    targets=repository(), run_setup=Setup, run_case=run_case, score_case=score_case
)
