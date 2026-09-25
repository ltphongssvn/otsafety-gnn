# tooling/tests/test_sheet_typefaces.py
"""The sheet's typefaces are Liberation Sans and DejaVu Sans Mono (G.58).

WHY THESE. The sheet rendered in a sandbox read better than the vendored one,
and the difference was measured rather than guessed: that pdf embeds Liberation
Sans and DejaVu Sans Mono, which the sandbox had as system fonts and Chromium
substituted for the generic families.

VENDORED, NOT BORROWED. Substitution is the defect the vendored fonts exist to
prevent -- the same html once produced a 334KB pdf on macOS and a 101KB one on a
runner because each embedded its own machine's faces. So these are pinned by
digest like the others; both are redistributable, Liberation under the SIL Open
Font Licence and DejaVu under its own permissive licence.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.58")

WANTED = {"LiberationSans", "DejaVuSansMono"}


def test_the_generator_declares_the_sandbox_typefaces() -> None:
    from importlib import util

    spec = util.spec_from_file_location(
        "build_arch_onepager", REPO_ROOT / "scripts" / "build_arch_onepager.py"
    )
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    families = {family for family, _, _ in module.FONTS}
    assert families == WANTED, f"the sheet declares {sorted(families)}"


def test_every_declared_face_is_vendored_with_a_digest() -> None:
    """A declared face with no file, or no digest, is a face Chromium substitutes."""
    from importlib import util

    spec = util.spec_from_file_location(
        "build_arch_onepager", REPO_ROOT / "scripts" / "build_arch_onepager.py"
    )
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for filename, digest in module.FONTS.values():
        assert len(digest) == 64, f"{filename} has no sha256"
        assert (module.FONT_DIR / filename).is_file(), f"{filename} is declared and not vendored"
