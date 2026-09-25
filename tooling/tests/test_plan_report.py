# tooling/tests/test_plan_report.py
"""The step-level plan report, collected and printed on one page (G.60).

THE WHOLE PLAN WAS READABLE ONLY BY RUNNING A COMMAND. A reader or reviewer
needs a sheet they can carry: every step, its state, what it waits on, what
proves it, and for an open step exactly what is missing.

COLLECTED, NOT GATHERED BY THE RENDERER, for the reason the architecture sheet
is: the render image carries Playwright and pypdf and neither git nor this
package. The collector writes a document; the renderer transforms it.

IT MUST FILL THE PAGE. The first render left the bottom third empty because the
columns balanced to the content instead of the page, which on a sheet that
exists to be dense is wasted paper and a smaller typeface than necessary.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.plan_report import PlanReport
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.60")

REPORT = REPO_ROOT / "build" / "onepager" / "plan-report.json"
PDF = REPO_ROOT / "build" / "onepager" / "plan-report.pdf"


def _collected() -> PlanReport:
    """The collected report, as the model rather than as parsed text."""
    from otsafety_tooling.planning.report import collect

    return collect()


def test_every_step_in_the_plan_reaches_the_report() -> None:
    """A report that quietly drops a phase is worse than no report."""
    from otsafety_tooling.planning.edit import load

    plan = load()
    report = _collected()
    counted = sum(len(phase.steps) for phase in report.phases)
    assert counted == len(plan.steps), f"{counted} steps reported of {len(plan.steps)}"
    assert len(report.phases) == len(plan.phases)


def test_an_open_step_carries_what_is_unmet() -> None:
    """The reason a step is open is the one thing a reader cannot derive."""
    open_steps = [
        step for phase in _collected().phases for step in phase.steps if step.state != "DONE"
    ]
    assert open_steps, "no open steps at all; the report would prove nothing"
    assert all(step.unmet for step in open_steps), "an open step reports nothing unmet"


def test_the_sheet_is_one_page_and_fills_it() -> None:
    """One page, and the content reaching its foot rather than stopping short."""
    pytest.importorskip("pypdf", reason="the e2e extra is not installed")
    if not PDF.is_file():
        pytest.skip("no report built; run mise run plan:report")
    import pypdf

    reader = pypdf.PdfReader(str(PDF))
    assert len(reader.pages) == 1, f"the report rendered {len(reader.pages)} pages"
    page = reader.pages[0]
    height = float(page.mediabox.height)
    lowest = [height]

    def visit(text: str, cm: list[float], tm: list[float], font: object, size: object) -> None:
        if text.strip():
            lowest[0] = min(lowest[0], cm[1] * tm[4] + cm[3] * tm[5] + cm[5])

    page.extract_text(visitor_text=visit)
    # THE CONTENT REACHES THE FOOT. Text stopping a third of the way up is the
    # empty page this closes; the margin is 6mm, about 17 points.
    assert lowest[0] < 0.12 * height, (
        f"the lowest text sits at {lowest[0] / height:.0%} of the page; the foot is empty"
    )
