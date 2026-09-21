# tooling/src/otsafety_tooling/contracts/toolchain.py
"""toolchain.json: every executable and image this repository pins.

FIVE READERS, ONE SHAPE. Three test modules, flake.nix and the bootstrap script
each read this file, and the tests read it as untyped dicts, filtering entries by
which keys they happened to have. The model declares the two kinds explicitly.
bootstrap_toolchain.py cannot import Pydantic -- it installs the toolchain on a
machine with nothing -- so this model validating the file in the test gate is
what proves the file before bootstrap ever reads it.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Platform = Literal["aarch64-darwin", "x86_64-linux"]
PLATFORMS: tuple[Platform, ...] = ("aarch64-darwin", "x86_64-linux")
SHA256 = r"^[0-9a-f]{64}$"


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class Artifact(_Strict):
    url: str = Field(pattern=r"^https://")
    sha256: str = Field(pattern=SHA256)
    dir: str = Field(min_length=1)


class BinaryTool(_Strict):
    comment: str = Field(default="", alias="_comment")
    version: str = Field(min_length=1)
    artifacts: dict[Platform, Artifact]
    binaries: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _every_platform(self) -> Self:
        missing = [p for p in PLATFORMS if p not in self.artifacts]
        if missing:
            raise ValueError(f"no artifact for {', '.join(missing)}")
        return self


class ContainerImage(_Strict):
    comment: str = Field(default="", alias="_comment")
    tag: str = Field(min_length=1)
    platform: Literal["linux/amd64"]
    digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    reference: str = Field(min_length=1)
    index_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    resolved_on: date


class Toolchain(_Strict):
    comment: str = Field(alias="_comment")
    uv: BinaryTool
    bun: BinaryTool
    gh: BinaryTool
    mise: BinaryTool
    railway: BinaryTool
    render_image: ContainerImage
    site_image: ContainerImage

    @property
    def binaries(self) -> dict[str, BinaryTool]:
        return {n: t for n, t in self if isinstance(t, BinaryTool)}
