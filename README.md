# WJP country profiles

Renders the one-page WJP Rule of Law Index country profile — matching the design
in `specs/` — from a single historical-data workbook
(`data/wjp_rol_index_historical.xlsx`), for any of the 143 countries in the
Index.

```
uv sync
uv run flask --app country_profiles.app run     # http://127.0.0.1:5000
uv run country-profiles Peru                    # one profile  -> output/
uv run country-profiles --all                   # all 143, one PDF, one page each
uv run pytest
```

Generated PDFs land in `output/` (git-ignored); `data/` holds only the input.

Opening the app shows a profile straight away (Peru by default). Picking a
country from the toolbar switches to it; **Download this profile** gives that
one page, **Download all 143** gives a single PDF with one country per page.

| Route | |
| --- | --- |
| `/` | the default profile, with the picker |
| `/profile/<country>` | that country's profile, with the picker |
| `/profile/<country>.pdf` | one profile as a one-page PDF |
| `POST /profiles/build` | start the combined build in the background |
| `/profiles/status` | JSON progress: `{state, done, total, bytes}` |
| `/profiles.pdf` | the combined PDF, served off disk |

The browser view and the PDF render the same Jinja template, so the layout can
be iterated on in a browser and comes out identical in print. The toolbar and
the paper-sheet framing live in an `@media screen` block and are never emitted
for a PDF.

### Building all 143

The combined PDF takes about 80 seconds, which is far too long to hold an HTTP
request open -- the browser sees no bytes and gives up. So the button starts a
worker thread instead (`jobs.py`), which writes

    output/WJP_country_profiles_2025.pdf

The page polls `/profiles/status` and shows `Building 57/143...`, then turns into
a link to the finished file. The rest of the app stays responsive while it runs,
nothing times out, and the result persists across restarts -- reopen the app and
the button is already a download. It writes to a `.part` file and renames on
success, so a half-built file is never served.

`country-profiles --all` does the same thing from the command line.

## How the numbers are derived

Everything comes from the single **Historical Data** sheet in
`data/wjp_rol_index_historical.xlsx`: the full score history, each country's
region (`Region` column), and its income group (`income_group` column). The
`f_*` score columns and `income_group` are located by header name, so their
position in the sheet doesn't matter.

That file is the WJP Index's published historical-data sheet with one column
added — `income_group`, copied in from the per-edition "WJP ROL Index &lt;year&gt;
Scores" tab, which is the only place the Index publishes it.

| Quantity | Rule |
| --- | --- |
| Displayed score | `round(x, 2)` |
| Percent change | scores rounded to **three** decimals first, then `(b - a) / a` |
| Global rank | descending rank among all 143 countries in the latest year |
| Regional / income rank | same, within the country's region or income group |
| Global / regional average | mean over that group in the latest year |
| Change window | six index years (2020–2025), falling back to the country's earliest year in that window |

The three-decimal rounding is not cosmetic: it is what reproduces the reference
profile exactly. Computing the percent change from raw values gives Peru
-4.51% where the reference prints -4.4%. `tests/test_metrics.py` pins every
figure read off that PDF.

## Relationship to the reference PDF

The design is specified by `specs/country profile-specs.pdf` (grid, colour
tokens, type scale, per-component geometry) with `specs/Country Profile-3.pdf`
as the reference render. Both are drawn for a **2026** mockup whose figures come
from the **2025** data with the year labels shifted forward one year; the
generated profiles use the real labels — 2020–2025, "WJP RULE OF LAW INDEX
2025".

The factor palette and semantic colours are taken from the written spec sheet
(`Foundations > Colors`), not from the SVG export, which had a few stale hues.
`data.py` carries two colours per factor: `color` for bars and sparklines, and
`text_color` for the factor name — they differ only for the three light hues the
spec flags as low-contrast (factors 2, 3, 8).

Three cells in the mockup are Illustrator artifacts and are deliberately not
reproduced: factor 4's regional rank (shows 21, correct is 16) and displayed
score (shows 0.57, correct is 0.58), and the hand-jittered Score Over Time line.

## Layout

`src/country_profiles/`

| File | Role |
| --- | --- |
| `data.py` | parses the workbook once, precomputes ranks and means, builds a profile dict |
| `charts.py` | geometry for the sparklines and the Score Over Time chart |
| `metrics.py` | text measurement, so long names can be fitted before layout |
| `render.py` | Jinja → HTML → PDF (WeasyPrint) |
| `jobs.py` | background build of the combined PDF, with progress |
| `paths.py` | where generated files go |
| `app.py` | Flask routes |
| `templates/profile.html` | the profile; inline SVG for both charts |
| `static/profile.css` | every length in points, measured off the reference PDF |
| `static/fonts/` | Inter Tight (OFL) — Regular/Medium/SemiBold/Bold/ExtraBold static instances cut from the variable font |

### Long country names

A print page cannot reflow, so anything that might not fit is measured against
the real font (`metrics.py`) and fitted before layout rather than allowed to
overflow:

* **The title** is set at 24pt Bold and shrinks only as far as it must to stay
  on one line in the 306pt column. Exactly one country needs this --
  *St. Vincent and the Grenadines*, at ~21pt. Left to wrap it would spill out
  of the fixed-height masthead and collide with the factor table.
* **The chart legend** has to hold the country name beside both averages in a
  195pt panel. Most fit on one row at the spec's 8pt (about 57 shrink a little
  further); the 7 longest wrap onto two rows, and the chart below them loses one
  row of height so the panel stays the same size.

`tests/test_layout.py` runs both checks over every country, and walks the
laid-out boxes to assert nothing crosses the page edge.

Factor colours, panel geometry and type sizes come from
`specs/country profile-specs.pdf`; the sparklines share one vertical scale
(~50pt per score unit) and are centred per factor, which is why a factor that
barely moved reads flat next to one that fell sharply.
