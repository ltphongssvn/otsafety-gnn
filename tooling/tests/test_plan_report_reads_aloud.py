# tooling/tests/test_plan_report_reads_aloud.py
"""The plan report reads aloud as well as it prints (G.65).

THE WHOLE PLAN WAS READABLE IN A TERMINAL ONLY BY PASTING A SCRIPT. The sheet's
renderer already consumes a collected document, so the console needed the same
one: a second traversal of the plan would drift from the first, and the two
would disagree about the same question.

ONE COLLECTOR, TWO RENDERINGS, which is the settled 2026 shape -- the same
internal object produces a human-readable terminal view and a machine-readable
payload with stable keys. The text is a pure function of PlanReport, so it
cannot report a figure the sheet does not.

THE PAYLOAD CHANNEL STAYS CLEAN. G.42 puts the typed outcome on stdout and
everything human on stderr, which is what 2026 practice means by never
polluting stdout: a caller can still parse the envelope while a reader watches
the report scroll past.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.65")


def test_the_text_is_a_rendering_of_the_collected_report() -> None:
    """Not a second traversal: the same object the sheet prints."""
    from otsafety_tooling.planning.report import collect, render_text

    report = collect()
    text = render_text(report)
    assert str(report.steps) in text, "the total is not the collected one"
    assert str(report.steps_done) in text
    assert str(report.ready) in text
    assert str(report.blocked) in text


def test_every_phase_and_every_step_is_printed() -> None:
    """A report that quietly drops a phase is worse than no report."""
    from otsafety_tooling.planning.report import collect, render_text

    report = collect()
    text = render_text(report)
    for phase in report.phases:
        assert f"PHASE {phase.id}" in text, f"phase {phase.id} is missing"
        for step in phase.steps:
            assert step.id in text, f"step {step.id} is missing"


def test_an_open_step_shows_exactly_what_is_unmet() -> None:
    """The one thing a reader cannot derive from the rest."""
    from otsafety_tooling.planning.report import collect, render_text

    report = collect()
    text = render_text(report)
    open_steps = [s for phase in report.phases for s in phase.steps if s.state != "DONE"]
    assert open_steps, "no open steps at all"
    for step in open_steps[:20]:
        for gap in step.unmet:
            assert gap[:40] in text, f"{step.id} does not show {gap[:40]!r}"


def test_every_thread_is_shown_with_its_ratio() -> None:
    """Seven threads, each with how far it has come.

    THE TEST ASKED FOR WHAT IT DID NOT PASS. render_text takes the threads as an
    argument -- they are counted by the sheet's collector, not the plan report's
    -- so calling it with none and then demanding the titles was my error, not
    the renderer's. It renders here the way the command renders.
    """
    from otsafety_tooling.planning.edit import load
    from otsafety_tooling.planning.report import collect, render_text
    from otsafety_tooling.planning.sheet import collect as collect_facts

    text = render_text(collect(), collect_facts().threads)
    for thread in load().threads:
        assert f"{thread.id} " in text, f"thread {thread.id} is missing"
        assert thread.title[:24] in text, f"thread {thread.id} shows no title"
    assert "%" in text, "no ratio is shown at all"


def test_the_task_exists_and_calls_the_module() -> None:
    """A report nobody can run is a function, not a report."""
    from otsafety_tooling.contracts.files import read_toml
    from otsafety_tooling.contracts.mise_config import MiseConfig

    tasks = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks
    assert "plan:report" in tasks, "no plan:report task"
    body = tasks["plan:report"].run
    body = body if isinstance(body, str) else "\n".join(body)
    assert "otsafety_tooling.planning.report" in body


def test_the_payload_channel_is_not_polluted() -> None:
    """G.42: the envelope on stdout, every human line on stderr."""
    import subprocess

    from otsafety_tooling.contracts.outcome import CommandOutcome

    done = subprocess.run(
        ["uv", "run", "--no-sync", "python", "-m", "otsafety_tooling.planning.report"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert done.returncode == 0, done.stderr[-400:]
    envelope = CommandOutcome.model_validate_json(done.stdout.strip().splitlines()[-1])
    assert envelope.command == "plan:report"
    assert envelope.outcome == "success"
    assert "PHASE" in done.stderr, "the report did not reach the reader"
    assert "PHASE" not in done.stdout, "the report polluted the payload channel"
