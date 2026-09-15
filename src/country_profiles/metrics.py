"""Text measurement against the embedded fonts.

A print layout has no room to reflow: the page is one fixed sheet, so a long
country name has to be fitted before it is laid out rather than after. CSS
cannot do that on its own, so we measure the string against the actual font.

Advance widths only -- kerning and ligatures are ignored, which makes these
estimates run slightly wide. That is the safe direction to be wrong in.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

FONTS = Path(__file__).resolve().parent / "static" / "fonts"

_FILES = {
    400: "InterTight-Regular.ttf",
    500: "InterTight-Medium.ttf",
    600: "InterTight-SemiBold.ttf",
    700: "InterTight-Bold.ttf",
    800: "InterTight-ExtraBold.ttf",
}


@lru_cache(maxsize=len(_FILES))
def _font(weight: int):
    from fontTools.ttLib import TTFont

    font = TTFont(FONTS / _FILES[weight])
    return font.getBestCmap(), font["hmtx"].metrics, font["head"].unitsPerEm


def text_width(text: str, size: float, weight: int = 400) -> float:
    """Width of ``text`` in points when set at ``size``."""
    cmap, widths, upem = _font(weight)
    units = sum(
        widths[cmap[ord(char)]][0] for char in text if ord(char) in cmap
    )
    return units / upem * size


def fit_size(
    text: str,
    available: float,
    size: float,
    minimum: float,
    weight: int = 400,
) -> float:
    """The largest size up to ``size`` at which ``text`` fits on one line."""
    width = text_width(text, size, weight)
    if width <= available:
        return size
    # Round *down* to a tenth: rounding to nearest can land just over the edge.
    return max(minimum, math.floor(size * available / width * 10) / 10)
