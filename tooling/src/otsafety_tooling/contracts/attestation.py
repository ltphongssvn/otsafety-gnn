# tooling/src/otsafety_tooling/contracts/attestation.py
"""attestation/v1: what "signed" means here, stated rather than assumed.

FIVE STEPS PROMISED A SIGNATURE AND NONE NAMED A MECHANISM. The sheet said
signed model card, the plan said attested, and the card asked for a sixty-four
character hex string. A digest is a number anyone can type; 2026 practice is
blunt that a predicate document without a signature is a file anyone could have
written, and that the signature is what gives it evidentiary value.

THE SHAPE IS THE ONE THE ECOSYSTEM ALREADY VERIFIES. A DSSE envelope pins the
exact bytes being signed. Inside it an in-toto statement names its subjects as
name and digest pairs under a declared predicate type, and carries the
predicate itself. Nothing here is invented: a verifier that knows DSSE and
in-toto can check this without knowing anything about this repository.

IDENTITY RATHER THAN A KEY SOMEONE KEEPS. Keyless signing binds a short-lived
certificate to an OIDC identity, and the signature is recorded in a transparency
log. A leaked long-lived key can be used to backdate an artifact; a log entry
cannot be created in the past. So the certificate and the log entry are required
fields, not optional decoration -- policies consume the attestation, not the
signature alone.

WHY LAYER 9 NEEDS THIS AND NOT A CHECKSUM. The verdict records a decision:
promote or reject, on what evidence, with which limitations declared. The
back-edge means a model that ships changes what later evidence looks like, so
the record of why it shipped must be one nobody can quietly revise afterwards.
"""

from __future__ import annotations

from typing import ClassVar, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_serializer,
    model_validator,
)


class Digest(BaseModel):
    """How a subject is bound: by content, not by name.

    TWO ALGORITHMS, BECAUSE TWO KINDS OF SUBJECT. A file is bound by the SHA-256
    of its bytes. A git revision is not a file, and the DigestSet specification
    defines gitCommit for exactly that -- the lowercase hex SHA-1 or SHA-256 of
    a commit object -- which v1.1.0 added to the pre-defined algorithms so a
    revision could be a subject at all. SLSA's own Source VSA binds its subject
    that way. Hashing a forty-character revision as file content would produce
    a number no verifier ever computes.

    ONE OF THEM IS REQUIRED. An empty digest map validates against a looser
    schema and binds the attestation to nothing.

    THE COST IS KNOWN IN ADVANCE: sigstore-python rejects a statement whose
    subject uses gitCommit, because its own DigestSet is restricted to SHA-2
    and SHA-3. Signing one through that client means giving up the DSSE
    envelope -- something the signing step must answer rather than discover.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    # The wire name is the specification's; the attribute stays usable here.
    git_commit: str | None = Field(
        default=None, alias="gitCommit", pattern=r"^[0-9a-f]{40}$|^[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def _binds_to_something(self) -> Self:
        if self.sha256 is None and self.git_commit is None:
            raise ValueError("a digest with no algorithm binds the attestation to nothing")
        return self

    @model_serializer
    def _only_the_algorithms_present(self) -> dict[str, str]:
        """The map the specification describes: names to digests, nothing else."""
        return {
            name: value
            for name, value in (("sha256", self.sha256), ("gitCommit", self.git_commit))
            if value is not None
        }


class Subject(BaseModel):
    """One artifact this attestation is about."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    digest: Digest


class InTotoStatement(BaseModel):
    """The claim: these artifacts, this predicate type, this content."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    CONTRACT_ID: ClassVar[str] = "in-toto-statement/v1"

    # The field is _type in the specification; the alias keeps the wire format
    # exact while the attribute stays usable from Python.
    type_: Literal["https://in-toto.io/Statement/v1"] = Field(
        default="https://in-toto.io/Statement/v1", alias="_type"
    )
    subject: tuple[Subject, ...] = Field(min_length=1)
    # A VERIFIER SELECTS ON THIS, so it is an absolute URI rather than a word.
    predicate_type: str = Field(alias="predicateType", pattern=r"^https://\S+$")
    # THE PREDICATE IS AN ARBITRARY OBJECT, as the specification says: its
    # predicateType selects the schema, and the statement layer does not know
    # it. dict[str, str] could not carry a verdict beside an observation and a
    # time, so a decision had to be flattened into strings to fit -- the
    # statement being narrower than the framework it implements. Each predicate
    # is validated by ITS OWN typed model before it is placed here.
    predicate: dict[str, JsonValue] = Field(min_length=1)


class Signature(BaseModel):
    """One signature, and the identity that made it.

    THE CERTIFICATE IS REQUIRED. Keyless signing binds an ephemeral key to an
    OIDC identity through a short-lived certificate; a bare signature says
    something was signed without saying by whom.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sig: str = Field(min_length=64)
    cert: str = Field(pattern=r"^-----BEGIN CERTIFICATE-----")


class TransparencyEntry(BaseModel):
    """Where the signature was logged, and when.

    A SIGNATURE NOBODY LOGGED CANNOT BE TOLD FROM ONE BACKDATED LATER, which is
    the attack a transparency log exists to close.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    log: str = Field(min_length=3)
    entry: int = Field(gt=0)
    logged_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T")


class DsseEnvelope(BaseModel):
    """The signed thing: bytes, their type, and who vouched for them."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    CONTRACT_ID: ClassVar[str] = "dsse-envelope/v1"

    payload_type: Literal["application/vnd.in-toto+json"] = Field(
        default="application/vnd.in-toto+json", alias="payloadType"
    )
    # The statement, base64 of the exact bytes signed -- which is the point of
    # the envelope: a re-serialisation would not verify.
    payload: str = Field(min_length=16)
    signatures: tuple[Signature, ...] = Field(min_length=1)
    transparency: TransparencyEntry
