# tooling/tests/test_flow_is_legible.py
"""The execution spine is legible in print (G.59).

ITS LABELS RENDERED AT 6.1 TO 6.6 POINT. 2026 print guidance puts the floor for
readable text at six -- below it most people need a magnifier -- and comfortable
secondary text at eight, with leading a fifth greater again. The panel sat at the
floor while the column below it was empty, so the sheet was squeezing text into
space it did not need to save.

MEASURED FROM THE RENDERED SVG, not from the constants. The diagram computes its
own geometry, so a constant can be raised while a label still emits the old size
from somewhere else; reading the emitted font-size attributes catches that.
"""

from __future__ import annotations

import re

import pytest

from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.59")

GENERATOR = REPO_ROOT / "scripts" / "build_arch_onepager.py"

# THE FLOOR, IN POINTS. The svg is drawn in user units that map to points at the
# scale this sheet prints, so the numbers compare directly with the guidance.
BODY = 7.4
TITLE = 9.0

SIZE = re.compile(r'font-size="([0-9.]+)"')


def _svg() -> str:
    from importlib import util

    spec = util.spec_from_file_location("build_arch_onepager", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    drawn: str = module.flow_svg()
    return drawn


def test_no_label_is_below_the_print_floor() -> None:
    sizes = sorted({float(found) for found in SIZE.findall(_svg())})
    assert sizes, "the diagram emits no sized text at all"
    assert sizes[0] >= BODY, (
        f"the smallest label is {sizes[0]}pt; under {BODY}pt reads as fine print"
    )


def test_each_stage_is_titled_larger_than_its_detail() -> None:
    """A stage name that matches its own caption gives the eye nothing to follow."""
    sizes = sorted({float(found) for found in SIZE.findall(_svg())})
    assert sizes[-1] >= TITLE, f"the stage titles are {sizes[-1]}pt, under {TITLE}pt"


def test_the_diagram_fills_the_height_it_is_given() -> None:
    """The stages carry print-size text, so the boxes are taller than they were.

    THE BOUND WAS GUESSED AND THE RENDER CORRECTED IT. 0.95 was picked before
    anything measured what the page could hold; at that ratio the sheet
    paginated, and the footer's last rows fell onto a second page. 0.83 fits with
    every label above the print floor, which is what the requirement asks. A
    number chosen before the measurement is a preference, not a criterion.
    """
    from importlib import util

    spec = util.spec_from_file_location("build_arch_onepager", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    found = re.search(r'viewBox="0 0 (\d+) ([0-9.]+)"', module.flow_svg())
    assert found, "the diagram declares no viewBox"
    ratio = float(found[2]) / float(found[1])
    assert ratio >= 0.80, f"the diagram is {ratio:.2f} of its width; it was 0.72 when squeezed"
