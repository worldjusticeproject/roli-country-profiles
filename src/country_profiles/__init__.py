"""WJP Rule of Law Index country profiles."""

from __future__ import annotations

import sys

from .paths import OUTPUT


def main() -> None:
    """Write profile PDFs into output/.

    ``country-profiles [COUNTRY]``  one country (default Peru)
    ``country-profiles --all``      every country, one page each, in one PDF
    """
    from .data import dataset
    from .render import all_filename, filename, render_all_pdf, render_pdf

    edition = dataset().latest
    OUTPUT.mkdir(parents=True, exist_ok=True)

    if sys.argv[1:2] == ["--all"]:
        countries = dataset().countries

        def progress(done: int, total: int) -> None:
            print(f"\r  {done}/{total}", end="", flush=True)

        out = OUTPUT / all_filename(edition)
        out.write_bytes(render_all_pdf(countries, on_progress=progress))
        print()
    else:
        country = " ".join(sys.argv[1:]) or "Peru"
        try:
            pdf = render_pdf(country)
        except KeyError:
            print(f"No profile for {country!r}.", file=sys.stderr)
            raise SystemExit(1)
        out = OUTPUT / filename(country, edition)
        out.write_bytes(pdf)

    print(out)
