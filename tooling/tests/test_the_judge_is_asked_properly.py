# tooling/tests/test_the_judge_is_asked_properly.py
"""How the semantic reviewer asks the judge, and what it records (G.87).

THE REAL SDK RUNS; ONLY THE WIRE IS FAKED. A hand-written protocol standing in
for the client was a copy of the SDK's signature that had already drifted --
the type checker refused the real client against it -- so tests written
against it exercised my picture of the SDK rather than the SDK. Here a real
anthropic.Anthropic builds its own request and parses its own response over an
httpx2 mock transport, so what these assert is what the API would receive.

AND NO SOCKET OPENS. The SDK moved to httpx2 in 1.0, and respx patches only
httpx -- a project trusting respx found its mocked tests sending real requests.
A transport handed to the client cannot do that: it is the only way out.

THE RESPONSE IS BUILT THROUGH THE SDK'S OWN MODEL, not typed by hand, so a
fixture shaped like my assumption rather than the API would be refused before
the test ran.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest
from pydantic import JsonValue, TypeAdapter

if TYPE_CHECKING:
    import anthropic

    from otsafety_tooling.contracts.semantic_review import SemanticReview

pytestmark = pytest.mark.requirement("G.87")

_BODY = TypeAdapter(dict[str, JsonValue])


@dataclass
class _Wire:
    """Answers in turn and keeps every request the SDK sent."""

    findings: tuple[str, ...]
    sent: list[dict[str, JsonValue]] = field(default_factory=list)


def _client(*findings: str) -> tuple[anthropic.Anthropic, _Wire]:
    sdk = pytest.importorskip("anthropic", reason="the review extra is not installed")
    import httpx2

    from otsafety_tooling.contracts.semantic_review import JUDGE_MODEL
    from otsafety_tooling.slsa.review import Verdict

    wire = _Wire(findings)

    def answer(request: httpx2.Request) -> httpx2.Response:
        wire.sent.append(_BODY.validate_json(request.content))
        finding = wire.findings[len(wire.sent) - 1]
        verdict = Verdict.model_validate({"finding": finding, "rationale": f"it is {finding}"})
        message = sdk.types.Message.model_validate(
            {
                "id": f"msg_{len(wire.sent)}",
                "type": "message",
                "role": "assistant",
                "model": JUDGE_MODEL,
                "content": [{"type": "text", "text": verdict.model_dump_json()}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        )
        return httpx2.Response(200, json=message.model_dump(mode="json"))

    client: anthropic.Anthropic = sdk.Anthropic(
        api_key="test-key-never-sent-anywhere",
        http_client=httpx2.Client(transport=httpx2.MockTransport(answer)),
    )
    return client, wire


def _ask(
    *findings: str, claim: str = "c", evidence: tuple[str, ...] = ("x",)
) -> tuple[SemanticReview, _Wire]:
    from otsafety_tooling.slsa.review import ask

    client, wire = _client(*findings)
    review = ask(client, step="G.85", claim=claim, evidence=evidence, repeats=len(findings))
    return review, wire


def test_the_verdict_comes_back_through_a_response_format_not_a_tool() -> None:
    """STRUCTURED OUTPUT, ON THE WIRE. A forced tool makes a thinking model skip
    its thinking, and the SDK no longer accepts a temperature."""
    _, wire = _ask("covered")
    sent = wire.sent[0]
    output = sent.get("output_config")
    assert isinstance(output, dict), "no output_config reached the API"
    response_format = output.get("format")
    assert isinstance(response_format, dict), "the output_config carried no format"
    assert response_format.get("type") == "json_schema"
    assert "tool_choice" not in sent, "a forced tool makes the model skip its thinking"
    assert "temperature" not in sent


def test_the_judge_is_the_one_the_requirement_chose() -> None:
    from otsafety_tooling.contracts.semantic_review import JUDGE_MODEL

    _, wire = _ask("covered")
    assert wire.sent[0]["model"] == JUDGE_MODEL


def test_the_judge_cannot_report_what_this_side_knows() -> None:
    """Finding and reason only: a model asked for its own id would invent one."""
    from otsafety_tooling.slsa.review import Verdict

    assert set(Verdict.model_fields) == {"finding", "rationale"}


def test_the_record_carries_the_contract_that_produced_it() -> None:
    from otsafety_tooling.contracts.semantic_review import SemanticReview
    from otsafety_tooling.slsa.review import RUBRIC

    review, _ = _ask("covered")
    assert isinstance(review, SemanticReview)
    assert review.judge.rubric == RUBRIC
    assert len(review.judge.prompt_sha256) == 64


def test_the_same_question_hashes_the_same() -> None:
    from otsafety_tooling.slsa.review import prompt_sha256

    first = prompt_sha256(step="G.85", claim="c", evidence=("x",))
    again = prompt_sha256(step="G.85", claim="c", evidence=("x",))
    other = prompt_sha256(step="G.85", claim="d", evidence=("x",))
    assert first == again != other


def test_the_mode_is_the_finding_and_the_split_is_counted() -> None:
    from otsafety_tooling.contracts.semantic_review import SemanticReview

    review, _ = _ask("covered", "partial", "covered")
    assert isinstance(review, SemanticReview)
    assert review.finding == "covered"
    assert (review.judge.repeats, review.judge.agreed) == (3, 2)
    assert not review.judge.unanimous


def test_a_tie_is_emitted_as_split_not_hidden_in_another_label() -> None:
    """DON'T HIDE TIES: choosing a side would invent a verdict."""
    from otsafety_tooling.contracts.semantic_review import SemanticReview

    review, _ = _ask("covered", "uncovered")
    assert isinstance(review, SemanticReview)
    assert review.finding == "split"


def test_the_question_names_the_claim_and_its_evidence() -> None:
    """Read from the request body: exactly what the API receives."""
    _, wire = _ask(
        "covered", claim="the level is enforced", evidence=("policy/slsa.rego", "slsa:source")
    )
    sent = str(wire.sent[0]["messages"])
    for named in ("the level is enforced", "policy/slsa.rego", "slsa:source"):
        assert named in sent, f"{named} never reached the API"


def test_the_judge_is_asked_exactly_as_often_as_recorded() -> None:
    """The count in the record is the count of requests sent, not a claim."""
    from otsafety_tooling.contracts.semantic_review import SemanticReview

    review, wire = _ask("covered", "covered", "covered", "covered", "covered")
    assert isinstance(review, SemanticReview)
    assert len(wire.sent) == review.judge.repeats == 5


def test_the_module_does_not_require_the_optional_extra() -> None:
    """A module-scope import of the optional SDK would fail every test that
    imports this file on a runner without the extra."""
    import ast as syntax

    from otsafety_tooling.paths import REPO_ROOT

    source = REPO_ROOT / "tooling" / "src" / "otsafety_tooling" / "slsa" / "review.py"
    tree = syntax.parse(source.read_text(encoding="utf-8"))
    top_level = {
        alias.name.split(".")[0]
        for node in tree.body
        if isinstance(node, syntax.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in tree.body
        if isinstance(node, syntax.ImportFrom) and node.module
    }
    assert "anthropic" not in top_level, "the optional SDK is imported at module scope"


def test_the_key_is_read_through_the_settings_model() -> None:
    from pydantic import SecretStr

    from otsafety_tooling.contracts.settings import ProjectSettings

    declared = ProjectSettings.model_fields["anthropic_api_key"]
    assert declared.alias == "ANTHROPIC_API_KEY"
    assert SecretStr in getattr(declared.annotation, "__args__", (declared.annotation,))


def test_no_key_is_a_refusal_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a key the command says so, and never reaches the network."""
    from otsafety_tooling.cli import CommandRefused
    from otsafety_tooling.contracts.settings import ProjectSettings
    from otsafety_tooling.slsa import review

    monkeypatch.setattr(review, "settings", lambda: ProjectSettings.model_validate({}))
    with pytest.raises(CommandRefused):
        review.client_from_settings()
