"""Geometry for the two charts, in points, matching the reference profile.

Both charts are emitted as inline SVG by the template; this module only works
out where the marks go.
"""

from __future__ import annotations

import math

# The sparklines in the reference profile all share one vertical scale --
# roughly 50pt per score unit -- and each is centred on its own series rather
# than stretched to fill its cell. That is what keeps a factor that barely
# moved looking flat next to one that fell sharply.
SPARK_SCALE = 50.0
SPARK_WIDTH = 44.0
SPARK_HEIGHT = 13.0

CHART_WIDTH = 195.0
CHART_HEIGHT = 112.0
CHART_YEAR_BAND = 12.0  # room under the axis for the year labels
CHART_GUTTER = 11.5  # room for the y-axis labels
CHART_INSET_LEFT = 15.5  # first point, in from the y-axis gutter
CHART_INSET_RIGHT = 13.0  # last point, in from the right edge (room for its label)
CHART_TOP = 11.0
CHART_LABEL_DROP = 13.0  # value label baseline, below its point


def sparkline(values: list[float | None]) -> list[tuple[float, float]]:
    """Points for one factor's sparkline, stretched across its known years.

    A country that joined the Index partway through the window has ``None``
    for its earlier years; those are skipped entirely rather than left as
    empty space, so the known points always span the full cell.
    """
    known = [v for v in values if v is not None]
    if not known:
        return []
    center = (max(known) + min(known)) / 2
    mid = SPARK_HEIGHT / 2
    if len(known) == 1:
        return [(SPARK_WIDTH, mid - (known[0] - center) * SPARK_SCALE)]
    step = SPARK_WIDTH / (len(known) - 1)
    return [
        (i * step, mid - (v - center) * SPARK_SCALE)
        for i, v in enumerate(known)
    ]


def _ticks(low: float, high: float) -> list[float]:
    """Axis ticks every 0.1, rounded outwards, spanning at least 0.2."""
    bottom = math.floor((low - 0.02) * 10) / 10
    top = math.ceil((high + 0.02) * 10) / 10
    while round(top - bottom, 10) < 0.2:
        top = round(top + 0.1, 10)
    return [round(bottom + i * 0.1, 10) for i in range(round((top - bottom) * 10) + 1)]


def timechart(series: list[dict], height: float = CHART_HEIGHT) -> dict:
    """Layout for the Score Over Time chart.

    ``series`` is one dict per year with ``year``, ``country``, ``global`` and
    ``regional`` keys. Returns tick positions plus point lists for each line.
    ``height`` shrinks when the legend above needs a second row, so the panel
    around it stays the same size.
    """
    bottom = height - CHART_YEAR_BAND
    values = [
        v
        for row in series
        for v in (row["country"], row["global"], row["regional"])
        if v is not None
    ]
    ticks = _ticks(min(values), max(values))
    low, high = ticks[0], ticks[-1]

    def y(value: float) -> float:
        share = (value - low) / (high - low)
        return bottom - share * (bottom - CHART_TOP)

    left = CHART_GUTTER + CHART_INSET_LEFT
    right = CHART_WIDTH - CHART_INSET_RIGHT
    step = (right - left) / (len(series) - 1) if len(series) > 1 else 0

    def line(key: str) -> list[tuple[float, float]]:
        return [
            (left + i * step, y(row[key]))
            for i, row in enumerate(series)
            if row[key] is not None
        ]

    return {
        "width": CHART_WIDTH,
        "height": height,
        "plot_left": CHART_GUTTER,
        "plot_right": CHART_WIDTH,
        "label_drop": CHART_LABEL_DROP,
        "ticks": [{"value": t, "label": f"{t:.1f}", "y": y(t)} for t in ticks],
        "axis_y": y(low),
        "years": [
            {"label": row["year"], "x": left + i * step}
            for i, row in enumerate(series)
        ],
        "country": line("country"),
        "global": line("global"),
        "regional": line("regional"),
        "country_labels": [
            {"x": left + i * step, "y": y(row["country"]) + CHART_LABEL_DROP,
             "text": f"{row['country']:.2f}"}
            for i, row in enumerate(series)
            if row["country"] is not None
        ],
    }


def path(points: list[tuple[float, float]]) -> str:
    """SVG polyline point list."""
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
