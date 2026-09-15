"""Load the WJP Rule of Law Index workbook and derive everything a profile needs.

All numbers follow the rules reverse-engineered from the reference profile
(``specs/Country Profile-3.pdf``): scores display at two decimals, and percent
changes are computed from scores rounded to *three* decimals first.
"""

from __future__ import annotations

import statistics
from functools import lru_cache
from pathlib import Path

from openpyxl import load_workbook

WORKBOOK = (
    Path(__file__).resolve().parents[2] / "data" / "wjp_rol_index_historical.xlsx"
)

# One sheet holds everything: the full score history plus, per country, its
# region (``Region`` column) and income group (``income_group`` column). Both
# the ``f_*`` score columns and ``income_group`` are located by header name;
# only the overall score is read from a fixed position.
HISTORICAL_SHEET = "Historical Data"
INCOME_CODE = "income_group"

OVERALL = "overall"
WINDOW_YEARS = 6

# Factor titles, colours and short sub-factor labels exactly as the reference
# profile prints them -- the workbook's own labels are the long-form versions.
#
# ``color`` fills the bars and sparklines; ``text_color`` sets the factor name
# wherever it is printed. They differ only for the three light hues the design
# spec flags as low-contrast (factors 2, 3, 8) -- see specs/country profile-specs.pdf,
# "Foundations > Colors > Factors".
FACTORS = [
    {
        "code": "f_1",
        "title": "1. Constraints on Government Powers",
        "color": "#008a20",
        "text_color": "#008a20",
        "subfactors": [
            ("f_1_1", "1.1 Limited by legislature"),
            ("f_1_2", "1.2 Limited by judiciary"),
            ("f_1_3", "1.3 Limited by auditing and review"),
            ("f_1_4", "1.4 Officials sanctioned for misconduct"),
            ("f_1_5", "1.5 Non-governmental checks"),
            ("f_1_6", "1.6 Transition of power"),
        ],
    },
    {
        "code": "f_2",
        "title": "2. Absence of Corruption",
        "color": "#a3b930",
        "text_color": "#57832f",
        "subfactors": [
            ("f_2_1", "2.1 Executive branch"),
            ("f_2_2", "2.2 Judicial branch"),
            ("f_2_3", "2.3 Police and military"),
            ("f_2_4", "2.4 Legislative branch"),
        ],
    },
    {
        "code": "f_3",
        "title": "3. Open Government",
        "color": "#30aea4",
        "text_color": "#007a72",
        "subfactors": [
            ("f_3_1", "3.1 Publicized laws and government data"),
            ("f_3_2", "3.2 Right to information"),
            ("f_3_3", "3.3 Civic participation"),
            ("f_3_4", "3.4 Complaint mechanisms"),
        ],
    },
    {
        "code": "f_4",
        "title": "4. Fundamental Rights",
        "color": "#0066cc",
        "text_color": "#0066cc",
        "subfactors": [
            ("f_4_1", "4.1 Equal treatment and absence of discrimination"),
            ("f_4_2", "4.2 Right to life and security"),
            ("f_4_3", "4.3 Due process and rights of the accused"),
            ("f_4_4", "4.4 Freedom of opinion and expression"),
            ("f_4_5", "4.5 Freedom of belief and religion"),
            ("f_4_6", "4.6 Freedom from interference with privacy"),
            ("f_4_7", "4.7 Freedom of assembly and association"),
            ("f_4_8", "4.8 Fundamental labor rights"),
        ],
    },
    {
        "code": "f_5",
        "title": "5. Order and Security",
        "color": "#413179",
        "text_color": "#413179",
        "subfactors": [
            ("f_5_1", "5.1 Crime is effectively controlled"),
            ("f_5_2", "5.2 Civil conflict is effectively limited"),
            ("f_5_3", "5.3 No violence to redress grievances"),
        ],
    },
    {
        "code": "f_6",
        "title": "6. Regulatory Enforcement",
        "color": "#a13498",
        "text_color": "#a13498",
        "subfactors": [
            ("f_6_1", "6.1 Regulations effectively enforced"),
            ("f_6_2", "6.2 No improper influence"),
            ("f_6_3", "6.3 No unreasonable delay"),
            ("f_6_4", "6.4 Due process in administrative proceedings"),
            ("f_6_5", "6.5 No expropriation without due process"),
        ],
    },
    {
        "code": "f_7",
        "title": "7. Civil Justice",
        "color": "#9a291d",
        "text_color": "#9a291d",
        "subfactors": [
            ("f_7_1", "7.1 Access and afford civil justice"),
            ("f_7_2", "7.2 Free of discrimination"),
            ("f_7_3", "7.3 Free of corruption"),
            ("f_7_4", "7.4 Free of improper government influence"),
            ("f_7_5", "7.5 No unreasonable delay"),
            ("f_7_6", "7.6 Effectively enforced"),
            ("f_7_7", "7.7 Alternative dispute resolution"),
        ],
    },
    {
        "code": "f_8",
        "title": "8. Criminal Justice",
        "color": "#c25300",
        "text_color": "#c25300",
        "subfactors": [
            ("f_8_1", "8.1 Investigation system is effective"),
            ("f_8_2", "8.2 Adjudication is timely and effective"),
            ("f_8_3", "8.3 Correctional system is effective"),
            ("f_8_4", "8.4 Criminal system is impartial"),
            ("f_8_5", "8.5 Free of corruption"),
            ("f_8_6", "8.6 Free of improper government influence"),
            ("f_8_7", "8.7 Due process and rights of the accused"),
        ],
    },
]

# The three columns of factor blocks in the lower half of the page.
FACTOR_COLUMNS = [[0, 1, 2], [3, 4, 5], [6, 7]]


def fmt(value: float | None) -> str:
    """Two-decimal display string, or an em dash when there is no value."""
    return "--" if value is None else f"{value:.2f}"


def pct_change(before: float, after: float) -> float:
    """Percent change between two scores, rounded to three decimals first.

    This is what reproduces the reference profile's figures exactly; using the
    raw values gives numbers that are off by up to a tenth of a point.
    """
    base = round(before, 3)
    return (round(after, 3) - base) / base * 100


def _sort_year(year: str) -> int:
    """Sort key for index years, which include ranges like ``2012-2013``."""
    return int(year.split("-")[-1])


class Dataset:
    """The workbook, parsed once into plain dicts."""

    def __init__(self, path: Path = WORKBOOK):
        book = load_workbook(path, read_only=True, data_only=True)
        self._read_historical(book[HISTORICAL_SHEET])
        book.close()
        self._index()

    def _read_historical(self, sheet) -> None:
        rows = sheet.iter_rows(values_only=True)
        codes = next(rows)
        next(rows)  # long labels, unused -- FACTORS carries the printed ones

        # Column F (index 5) is the overall score; the ``f_*`` factor columns
        # and the ``income_group`` column are found by header name, wherever
        # they sit.
        self.columns = {OVERALL: 5}
        income_at = None
        for position, code in enumerate(codes):
            if isinstance(code, str) and code.startswith("f_"):
                self.columns[code] = position
            elif code == INCOME_CODE:
                income_at = position

        self.scores: dict[tuple[str, str], dict[str, float]] = {}
        self.region: dict[str, str] = {}
        self.income: dict[str, str] = {}
        for row in rows:
            country, year = row[0], row[1]
            if not country or year is None:
                continue
            year = str(year)
            self.region[country] = row[4]
            if income_at is not None and row[income_at]:
                self.income[country] = row[income_at]
            self.scores[(country, year)] = {
                code: row[position]
                for code, position in self.columns.items()
                if isinstance(row[position], (int, float))
            }

    def _index(self) -> None:
        years = {year for _, year in self.scores}
        self.years = sorted(years, key=_sort_year)
        self.latest = self.years[-1]
        self.window = self.years[-WINDOW_YEARS:]

        self.countries = sorted(
            country for (country, year) in self.scores if year == self.latest
        )

        # Per year, per code: every country's value, plus the descending sort
        # used for ranks. Precomputed so a profile costs only lookups.
        self._values: dict[tuple[str, str], dict[str, float]] = {}
        for (country, year), row in self.scores.items():
            for code, value in row.items():
                self._values.setdefault((year, code), {})[country] = value

        self._ranked: dict[tuple, list[float]] = {}
        self._means: dict[tuple, float] = {}
        for (year, code), values in self._values.items():
            for group, members in self._groups(year, values).items():
                pool = sorted(members, reverse=True)
                self._ranked[(year, code, group)] = pool
                self._means[(year, code, group)] = statistics.fmean(pool)

    def _groups(self, year: str, values: dict[str, float]) -> dict[tuple | None, list[float]]:
        """Bucket a year's values globally, by region and by income group.

        Keys are tagged so a region and an income group can never share one.
        """
        groups: dict[tuple | None, list[float]] = {None: list(values.values())}
        for country, value in values.items():
            for kind, name in (("region", self.region.get(country)),
                               ("income", self.income.get(country))):
                if name:
                    groups.setdefault((kind, name), []).append(value)
        return groups

    def rank(self, value: float, year: str, code: str, group: tuple | None = None):
        """Descending rank of ``value`` and the size of the pool it sits in."""
        pool = self._ranked[(year, code, group)]
        return pool.index(value) + 1, len(pool)

    def mean(self, year: str, code: str, group: tuple | None = None) -> float:
        return self._means[(year, code, group)]


@lru_cache(maxsize=1)
def dataset() -> Dataset:
    return Dataset()


def _direction(change: float | None) -> str:
    """Arrow key for a percent change, matching the header legend."""
    if change is None or round(change, 1) == 0:
        return "flat"
    return "up" if change > 0 else "down"


def _change(data: Dataset, country: str, baseline: str | None, code: str):
    """Percent change for one code between the baseline year and the latest."""
    if baseline is None:
        return {"value": None, "number": "", "text": "", "direction": "flat"}
    before = data.scores[(country, baseline)].get(code)
    after = data.scores[(country, data.latest)].get(code)
    if before is None or after is None:
        return {"value": None, "number": "", "text": "", "direction": "flat"}
    change = pct_change(before, after)
    return {
        "value": change,
        "number": f"{change:.1f}",
        "text": f"{change:.1f}%",
        "direction": _direction(change),
    }


def build_profile(country: str) -> dict:
    """Everything the profile template renders, for one country."""
    data = dataset()
    if (country, data.latest) not in data.scores:
        raise KeyError(country)

    latest = data.latest
    region = data.region[country]
    in_region = ("region", region)
    income = data.income.get(country)
    current = data.scores[(country, latest)]

    # The change window is six index years, but 15 countries joined the Index
    # partway through; fall back to their earliest year inside that window.
    available = [y for y in data.window if (country, y) in data.scores]
    baseline = available[0] if len(available) > 1 else None

    overall_score = current[OVERALL]
    global_mean = data.mean(latest, OVERALL)
    comparison = (
        "Above" if round(overall_score, 2) > round(global_mean, 2)
        else "Below" if round(overall_score, 2) < round(global_mean, 2)
        else "At"
    )

    factors = []
    for spec in FACTORS:
        score = current[spec["code"]]
        history = [
            data.scores.get((country, y), {}).get(spec["code"])
            for y in data.window
        ]
        factors.append({
            **spec,
            "score": score,
            "display": fmt(score),
            "change": _change(data, country, baseline, spec["code"]),
            "history": history,
            "global_rank": data.rank(score, latest, spec["code"]),
            "regional_rank": data.rank(score, latest, spec["code"], in_region),
            "subfactors": [
                {
                    "label": label,
                    "score": current[code],
                    "display": fmt(current[code]),
                    "global_mean": data.mean(latest, code),
                    "regional_mean": data.mean(latest, code, in_region),
                }
                for code, label in spec["subfactors"]
            ],
        })

    return {
        "name": country,
        "region": region,
        "income": income.capitalize() if income else None,
        "edition": latest,
        "window": data.window,
        "baseline": baseline,
        "baseline_label": f"{baseline} vs. {latest}" if baseline else "",
        "overall": {
            "score": overall_score,
            "display": fmt(overall_score),
            "comparison": comparison,
            "global_mean": fmt(global_mean),
            "change": _change(data, country, baseline, OVERALL),
            "global_rank": data.rank(overall_score, latest, OVERALL),
            "regional_rank": data.rank(overall_score, latest, OVERALL, in_region),
            "income_rank": (
                data.rank(overall_score, latest, OVERALL, ("income", income)) if income else None
            ),
        },
        "factors": factors,
        "columns": [[factors[i] for i in column] for column in FACTOR_COLUMNS],
        "timeseries": [
            {
                "year": year,
                "country": data.scores.get((country, year), {}).get(OVERALL),
                "global": data.mean(year, OVERALL),
                "regional": data.mean(year, OVERALL, in_region),
            }
            for year in data.window
        ],
    }
