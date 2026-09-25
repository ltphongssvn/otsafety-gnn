# tooling/tests/test_attestation_contract.py
"""What "signed" means, stated rather than assumed (E.37).

FIVE STEPS PROMISED A SIGNATURE AND NONE NAMED A MECHANISM. The sheet says
signed model card; the plan says attested; the contract asked for a sixty-four
character hex string called attested_by. A digest is a number anyone can type,
and 2026 practice is blunt about what that is worth: a predicate document
without a signature is a file anyone could have written, and the signature is
what gives it evidentiary value.

SIGNING IS THE ACTION, NOT A SECOND STEP. A DSSE envelope pins the exact bytes
being signed; inside it an in-toto statement names its subjects as file-path and
digest pairs under a declared predicate type. Sigstore's model-transparency
project stores model card information in exactly those predicates, which is the
shape this contract takes.

THE IDENTITY, NOT THE KEY. Keyless signing binds a short-lived certificate to an
OIDC identity and records the signature in a transparency log, so a leaked
long-lived key cannot be used to backdate an artifact, and a verifier checks the
log rather than a key set it has to manage.

WHY THIS PROJECT NEEDS IT. Layer 9's record is the decision: promote or reject,
on what evidence, with which limitations declared. The back-edge means a model
that ships changes what later evidence looks like, so the record of why it
shipped must be one nobody can quietly revise afterwards.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.requirement("E.37")

DIGEST = "a" * 64


def _statement(**overrides: object) -> object:
    from otsafety_tooling.contracts.attestation import InTotoStatement

    base: dict[str, object] = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": ({"name": "model-card.json", "digest": {"sha256": DIGEST}},),
        "predicateType": "https://otsafety-gnn/model-card/v1",
        "predicate": {"verdict": "promote", "question": "Q3"},
    }
    base.update(overrides)
    return InTotoStatement.model_validate(base)


def _envelope(**overrides: object) -> object:
    from otsafety_tooling.contracts.attestation import DsseEnvelope

    base: dict[str, object] = {
        "payloadType": "application/vnd.in-toto+json",
        "payload": "eyJfdHlwZSI6ICJodHRwczovL2luLXRvdG8uaW8vU3RhdGVtZW50L3YxIn0=",
        "signatures": (
            {
                "sig": "MEUCIQD" + "A" * 57,
                "cert": "-----BEGIN CERTIFICATE-----\nMIIC\n-----END CERTIFICATE-----",
            },
        ),
        "transparency": {
            "log": "rekor.sigstore.dev",
            "entry": 148392017,
            "logged_at": "2026-09-25T10:00:00Z",
        },
    }
    base.update(overrides)
    return DsseEnvelope.model_validate(base)


def test_a_complete_attestation_validates() -> None:
    """The positive control: without it every refusal below proves nothing."""
    assert _statement()
    assert _envelope()


def test_a_statement_names_what_it_is_about() -> None:
    """An attestation with no subject binds to nothing."""
    with pytest.raises(ValidationError):
        _statement(subject=())


def test_a_subject_carries_a_sha256_digest() -> None:
    """The digest is the binding; a name alone is not one."""
    with pytest.raises(ValidationError):
        _statement(subject=({"name": "model-card.json", "digest": {}},))


def test_the_predicate_type_is_declared_and_absolute() -> None:
    """A verifier selects on predicate type, so a bare word cannot serve."""
    with pytest.raises(ValidationError):
        _statement(predicateType="model-card")


def test_an_envelope_without_a_signature_is_refused() -> None:
    """Signing is the action: an unsigned envelope is a file anyone could write."""
    with pytest.raises(ValidationError):
        _envelope(signatures=())


def test_a_signature_carries_the_identity_that_made_it() -> None:
    """Keyless signing binds a certificate, not a key someone kept."""
    with pytest.raises(ValidationError):
        _envelope(signatures=({"sig": "MEUCIQD" + "A" * 57},))


def test_an_attestation_outside_a_transparency_log_is_refused() -> None:
    """A signature nobody logged cannot be told from one backdated later."""
    with pytest.raises(ValidationError):
        _envelope(transparency=None)


def test_the_model_card_carries_the_envelope_rather_than_a_digest() -> None:
    """attested_by was a number anyone could type."""
    from otsafety_tooling.contracts.model_card import ModelCard

    assert "attestation" in ModelCard.model_fields, "the card still records no attestation"
    assert "attested_by" not in ModelCard.model_fields, (
        "the card still accepts a bare digest as its attestation"
    )
