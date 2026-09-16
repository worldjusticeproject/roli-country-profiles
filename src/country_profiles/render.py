"""Render country profiles to HTML, and from that HTML to PDF."""

from __future__ import annotations

import math
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import charts
from .data import build_profile, dataset
from .metrics import fit_size, text_width

PACKAGE = Path(__file__).resolve().parent
TEMPLATES = PACKAGE / "templates"
STATIC = PACKAGE / "static"

_env = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=select_autoescape(["html"]),
)
# The masthead sits in the 306pt left column, and the chart legend in the
# 195pt panel. Both are fixed, so long names are fitted rather than wrapped.
# The legend numbers mirror .chart-legend in profile.css -- keep them in step.
TITLE_WIDTH = 306.0
TITLE_SIZE = 24.0
TITLE_WEIGHT = 700          # spec: masthead title is Inter Tight Bold
TITLE_MIN_SIZE = 15.0
LEGEND_WIDTH = 193.0         # 195pt panel inner width, less a safety margin
LEGEND_SIZE = 8.0           # spec: chart legend / key text is 8pt
LEGEND_MIN_SIZE = 6.4        # below this, wrap instead of shrinking further
LEGEND_SWATCH = 12.0 + 2.4   # swatch plus the gap to its label (mirrors profile.html)
LEGEND_GAP = 8.0             # between legend items
LEGEND_ROW = 10.0            # height of a wrapped second row

_env.globals.update(
    sparkline=charts.sparkline,
    path=charts.path,
    spark_w=charts.SPARK_WIDTH,
    spark_h=charts.SPARK_HEIGHT,
    spark_stroke=charts.SPARK_STROKE,
)


def render_html(
    country: str,
    css_href: str = "",
    chrome: bool = False,
    countries: Iterable[str] | None = None,
    build: dict | None = None,
) -> str:
    """The profile as standalone HTML.

    An empty ``css_href`` omits the stylesheet link, which is what the PDF path
    wants -- it hands WeasyPrint an already-parsed stylesheet instead.
    ``chrome`` adds the country picker and download buttons; that markup is
    screen-only and is never emitted for a PDF.
    """
    profile = build_profile(country)
    legend_size, legend_rows = legend_fit(country)
    chart_height = charts.CHART_HEIGHT - (legend_rows - 1) * LEGEND_ROW
    return _env.get_template("profile.html").render(
        p=profile,
        chart=charts.timechart(profile["timeseries"], height=chart_height),
        title_size=fit_size(
            country, TITLE_WIDTH, TITLE_SIZE, TITLE_MIN_SIZE, weight=TITLE_WEIGHT
        ),
        legend_size=legend_size,
        css_href=css_href,
        chrome=chrome,
        countries=list(countries) if countries is not None else [],
        build=build or {"state": "idle", "done": 0, "total": 0},
    )


def legend_fit(country: str) -> tuple[float, int]:
    """Type size and row count for the chart legend.

    The panel is only 195pt wide and has to hold the country name beside both
    averages. Most names fit at the full size; a few need a point or so shaved
    off; the longest handful cannot fit on one row at any readable size, and
    wrap instead -- the chart below them shrinks by a row to compensate.
    """
    labels = (country, "Global Average", "Regional Average")
    chrome = len(labels) * LEGEND_SWATCH + (len(labels) - 1) * LEGEND_GAP
    text = sum(text_width(label, LEGEND_SIZE) for label in labels)
    if text + chrome <= LEGEND_WIDTH:
        return LEGEND_SIZE, 1
    size = math.floor(LEGEND_SIZE * (LEGEND_WIDTH - chrome) / text * 10) / 10
    if size >= LEGEND_MIN_SIZE:
        return size, 1
    return LEGEND_SIZE, 2


@lru_cache(maxsize=1)
def _print_style():
    """Parse the stylesheet once and reuse it for every document.

    Re-parsing it per profile costs about 20% of the total render time, which
    is worth avoiding when building all 143 in one go.
    """
    from weasyprint import CSS
    from weasyprint.text.fonts import FontConfiguration

    fonts = FontConfiguration()
    return CSS(filename=str(STATIC / "profile.css"), font_config=fonts), fonts


def render_document(country: str):
    """A laid-out WeasyPrint document for one country -- always one page."""
    from weasyprint import HTML

    stylesheet, fonts = _print_style()
    return HTML(string=render_html(country), base_url=f"{STATIC}/").render(
        stylesheets=[stylesheet], font_config=fonts
    )


def render_pdf(country: str) -> bytes:
    """The profile as a single-page Letter PDF."""
    return render_document(country).write_pdf()


def render_all_pdf(
    countries: Iterable[str] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> bytes:
    """Every country's profile in one PDF, one page each, in listing order.

    ``on_progress(done, total)`` is called after each country. This takes about
    80 seconds for the full Index, so callers generally want to report it.
    """
    names = list(countries) if countries is not None else dataset().countries
    documents = []
    for done, name in enumerate(names, start=1):
        documents.append(render_document(name))
        if on_progress:
            on_progress(done, len(names))
    pages = [page for document in documents for page in document.pages]
    return documents[0].copy(pages).write_pdf()


def filename(country: str, edition: str) -> str:
    """A download name for one country's profile.

    Folded to ASCII because this ends up in a Content-Disposition header.
    """
    folded = unicodedata.normalize("NFKD", country).encode("ascii", "ignore").decode()
    slug = "".join(c if c.isalnum() else "_" for c in folded)
    return f"{'_'.join(filter(None, slug.split('_')))}_{edition}_country_profile.pdf"


def all_filename(edition: str) -> str:
    return f"WJP_country_profiles_{edition}.pdf"
