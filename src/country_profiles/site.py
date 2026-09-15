"""Build the whole thing as a static site, for GitHub Pages.

Every country gets a page and a one-page PDF; there is one combined PDF and an
``index.html`` that is the default profile. All links are relative, so the site
works from any base path (a project Pages URL includes the repo name).

    uv run country-profiles --site            # -> site/
    uv run country-profiles --site public     # -> public/
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .data import dataset
from .render import STATIC, render_document, render_html, slug

DEFAULT_COUNTRY = "Peru"


def combined_name(edition: str) -> str:
    return f"wjp-country-profiles-{edition}.pdf"


def _copy_assets(dest: Path) -> None:
    (dest / "profile.css").write_bytes((STATIC / "profile.css").read_bytes())
    fonts = dest / "fonts"
    fonts.mkdir(exist_ok=True)
    for face in (STATIC / "fonts").glob("*"):
        (fonts / face.name).write_bytes(face.read_bytes())


def build_site(
    dest: Path,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Render the static site into ``dest`` and return the directory."""
    data = dataset()
    countries = data.countries
    all_pdf = combined_name(data.latest)

    dest.mkdir(parents=True, exist_ok=True)
    _copy_assets(dest)

    def page(country: str) -> str:
        return render_html(
            country,
            css_href="profile.css",
            chrome=True,
            site=True,
            countries=countries,
            all_href=all_pdf,
        )

    # Render each WeasyPrint document once: its own PDF now, and a page for the
    # combined PDF at the end.
    documents = []
    for done, country in enumerate(countries, start=1):
        document = render_document(country)
        documents.append(document)
        (dest / f"{slug(country)}.pdf").write_bytes(document.write_pdf())
        (dest / f"{slug(country)}.html").write_text(page(country), encoding="utf-8")
        if on_progress:
            on_progress(done, len(countries))

    (dest / "index.html").write_text(page(DEFAULT_COUNTRY), encoding="utf-8")

    pages = [p for document in documents for p in document.pages]
    (dest / all_pdf).write_bytes(documents[0].copy(pages).write_pdf())

    return dest
