"""Long country names must not break the fixed-size page.

The masthead and the chart legend both sit in boxes that cannot grow, so the
title and the legend are measured and fitted before layout. These tests pin
that: nothing may spill outside its box, whatever the name.
"""

import pytest

from country_profiles.data import dataset
from country_profiles.metrics import text_width
from country_profiles.render import (
    LEGEND_GAP,
    LEGEND_SIZE,
    LEGEND_SWATCH,
    LEGEND_WIDTH,
    TITLE_MIN_SIZE,
    TITLE_SIZE,
    TITLE_WEIGHT,
    TITLE_WIDTH,
    legend_fit,
    render_document,
)
from country_profiles.metrics import fit_size

LONGEST = "St. Vincent and the Grenadines"


def _title_size(country):
    return fit_size(
        country, TITLE_WIDTH, TITLE_SIZE, TITLE_MIN_SIZE, weight=TITLE_WEIGHT
    )


@pytest.mark.parametrize("country", dataset().countries)
def test_title_fits_on_one_line(country):
    size = _title_size(country)
    assert TITLE_MIN_SIZE <= size <= TITLE_SIZE
    assert text_width(country, size, weight=TITLE_WEIGHT) <= TITLE_WIDTH + 0.5


@pytest.mark.parametrize("country", dataset().countries)
def test_legend_fits_its_panel(country):
    size, rows = legend_fit(country)
    labels = [country, "Global Average", "Regional Average"]
    if rows == 1:
        width = sum(text_width(label, size) for label in labels)
        width += 3 * LEGEND_SWATCH + 2 * LEGEND_GAP
    else:
        # country on one row, the two averages on the next
        width = max(
            text_width(country, size) + LEGEND_SWATCH,
            sum(text_width(label, size) for label in labels[1:])
            + 2 * LEGEND_SWATCH + LEGEND_GAP,
        )
    assert width <= LEGEND_WIDTH


def test_the_longest_name_still_gets_a_readable_title():
    assert _title_size(LONGEST) < TITLE_SIZE      # it does have to shrink
    assert _title_size(LONGEST) >= 20             # but only a little


def test_peru_is_unaffected():
    """Peru is the reference profile; fitting must leave it at full size."""
    assert _title_size("Peru") == TITLE_SIZE
    assert legend_fit("Peru") == (LEGEND_SIZE, 1)


@pytest.mark.parametrize("country", [LONGEST, "Bosnia and Herzegovina", "Peru"])
def test_nothing_spills_outside_the_page(country):
    """Walk the laid-out boxes and assert they stay inside the content box."""
    px = 4 / 3
    left, right = 42 * px, 569.5 * px

    def walk(box):
        yield box
        for child in getattr(box, "children", ()):
            yield from walk(child)

    page = render_document(country).pages[0]
    for box in walk(page._page_box):
        if type(box).__name__ == "PageBox":
            continue
        x, width = getattr(box, "position_x", None), getattr(box, "width", None)
        if x is None or not isinstance(width, (int, float)):
            continue
        assert x >= left - 0.5, (country, type(box).__name__)
        assert x + width <= right + 0.5, (country, type(box).__name__)
