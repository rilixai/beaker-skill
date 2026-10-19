"""Document contract example: Beaker edits FAQ documents; the application code stays fixed."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from beaker import (
    Case,
    CaseResult,
    CaseScore,
    Check,
    CombinedRunSetup,
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
    expected: str


class Setup(CombinedRunSetup[Row]):
    row_model = Row

    @asynccontextmanager
    async def prepare_run(
        self, *, runtime: SetupRuntime
    ) -> AsyncIterator[dict[str, DocumentRunSetupResult]]:
        # One result per declared target, keyed by target kind.
        # TODO(beaker): fetch real documents, preserving source IDs and versions.
        yield {
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


def build_faq_index(targets_dir: Path) -> dict[str, str]:
    """Illustrative index of FAQ lines formatted as 'topic: answer'."""
    index: dict[str, str] = {}
    for path in sorted((targets_dir / "wiki").rglob("*")):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            topic, separator, answer = line.partition(":")
            if separator:
                index[topic.strip().casefold()] = answer.strip()
    return index


@asynccontextmanager
async def open_candidate(
    *, targets_dir: Path | None, scratch_dir: Path
) -> AsyncIterator[dict[str, str]]:
    # TODO(beaker): build whatever the application needs from this candidate's
    # documents once (an index, a loaded client). Every case of the rollout
    # shares it as runtime.candidate; release it after the yield.
    del scratch_dir
    if targets_dir is None:
        raise RuntimeError("Document targets require targets_dir")
    yield build_faq_index(targets_dir)


async def run_case(
    *, case_input: JsonValue, runtime: RolloutRuntime[dict[str, str]]
) -> CaseResult:
    # TODO(beaker): call the candidate application's real entrypoint from the
    # candidate checkout, using what open_candidate built from this candidate's
    # documents (runtime.targets_dir holds the files, one directory per group).
    if not isinstance(case_input, str):
        raise TypeError("case_input must be a question string")
    if runtime.candidate is None:
        raise RuntimeError("open_candidate did not run for this candidate")
    answer = runtime.candidate.get(case_input.strip().casefold(), "Not found")
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
    targets=documents(groups=("wiki",)),
    run_setup=Setup,
    run_case=run_case,
    score_case=score_case,
    open_candidate=open_candidate,
)
