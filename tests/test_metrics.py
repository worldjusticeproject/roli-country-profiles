"""Reference figures, pinned to the 2026 edition of the workbook.

The layout rules come from specs/Country Profile-3.pdf; its printed numbers
were computed from the 2025 data, so the values below are the 2026 workbook's
own and are refreshed whenever data/wjp_rol_index_historical.xlsx is updated.
"""

import pytest

from country_profiles.charts import timechart
from country_profiles.data import build_profile, dataset, pct_change


@pytest.fixture(scope="module")
def peru():
    return build_profile("Peru")


def test_edition_and_window():
    data = dataset()
    assert data.latest == "2026"
    assert data.window == ["2021", "2022", "2023", "2024", "2025", "2026"]
    assert len(data.countries) == 143


def test_income_group_comes_from_the_one_sheet():
    """Region and income group both ride along in Historical Data now -- every
    country in the latest year must resolve an income group."""
    data = dataset()
    assert set(data.income.values()) == {
        "High", "Upper-Middle", "Lower-Middle", "Low",
    }
    assert all(c in data.income for c in data.countries)


def test_overall(peru):
    assert peru["region"] == "Latin America and Caribbean"
    assert peru["income"] == "Upper-middle"
    assert peru["overall"]["display"] == "0.47"
    assert peru["overall"]["global_mean"] == "0.55"
    assert peru["overall"]["comparison"] == "Below"
    assert peru["overall"]["change"]["text"] == "-3.1%"
    assert peru["overall"]["global_rank"] == (93, 143)
    assert peru["overall"]["regional_rank"] == (21, 32)
    assert peru["overall"]["income_rank"] == (32, 44)
    assert peru["baseline_label"] == "2021 vs. 2026"


def test_factor_scores(peru):
    scores = [f["display"] for f in peru["factors"]]
    assert scores == ["0.56", "0.32", "0.53", "0.58",
                      "0.62", "0.47", "0.41", "0.31"]


def test_factor_changes(peru):
    changes = [f["change"]["text"] for f in peru["factors"]]
    assert changes == ["-5.9%", "0.1%", "-2.5%", "-6.1%",
                       "1.9%", "-3.4%", "-5.2%", "-1.9%"]
    directions = [f["change"]["direction"] for f in peru["factors"]]
    assert directions == ["down", "up", "down", "down",
                          "up", "down", "down", "down"]


def test_factor_global_ranks(peru):
    ranks = [f["global_rank"][0] for f in peru["factors"]]
    assert ranks == [59, 119, 62, 64, 112, 83, 121, 118]
    assert all(f["global_rank"][1] == 143 for f in peru["factors"])


def test_percent_change_uses_unrounded_scores():
    # The scores go into the division at full precision and only the printed
    # figure is rounded; rounding them to three decimals first would give -4.4%.
    assert round(pct_change(0.499052, 0.476563), 1) == -4.5


def test_subfactor_count(peru):
    assert sum(len(f["subfactors"]) for f in peru["factors"]) == 44


def test_factor_text_colour_override(peru):
    """Bars keep the factor hue; the three low-contrast factors print their
    name in a darker one (specs/country profile-specs.pdf, Foundations > Colors)."""
    by_title = {f["title"]: f for f in peru["factors"]}
    corruption = by_title["2. Absence of Corruption"]
    assert corruption["color"] == "#a3b930"
    assert corruption["text_color"] == "#57832f"
    # factors without an override keep one colour for both
    powers = by_title["1. Constraints on Government Powers"]
    assert powers["color"] == powers["text_color"]


def test_chart_axis(peru):
    chart = timechart(peru["timeseries"])
    assert [t["label"] for t in chart["ticks"]] == ["0.40", "0.50", "0.60"]
    assert [y["label"] for y in chart["years"]] == peru["window"]


@pytest.mark.parametrize(
    "country, baseline",
    [
        ("Qatar", "2025 vs. 2026"),  # joined the Index in 2025
        ("Kuwait", "2023 vs. 2026"),  # joined in 2023
        ("Denmark", "2021 vs. 2026"),  # the full six-year window
    ],
)
def test_baseline_falls_back(country, baseline):
    assert build_profile(country)["baseline_label"] == baseline


@pytest.mark.parametrize(
    "country, spark_start",
    [
        ("Peru", "2021"),
        ("Denmark", "2021"),
        ("Gabon", "2022"),
        ("Kuwait", "2023"),
        ("Qatar", "2025"),
    ],
)
def test_spark_start(country, spark_start):
    assert build_profile(country)["spark_start"] == spark_start


def test_above_average_country():
    assert build_profile("Denmark")["overall"]["comparison"] == "Above"


def test_unknown_country():
    with pytest.raises(KeyError):
        build_profile("Atlantis")


def test_every_country_fits_one_page():
    from country_profiles.render import render_document

    for country in dataset().countries:
        assert len(render_document(country).pages) == 1, country
