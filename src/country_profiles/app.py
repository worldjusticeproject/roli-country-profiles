"""Flask app: browse country profiles and download them as PDFs."""

from __future__ import annotations

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    send_file,
    url_for,
)

from . import jobs
from .data import dataset
from .paths import OUTPUT
from .render import (
    STATIC,
    TEMPLATES,
    all_filename,
    filename,
    render_html,
    render_pdf,
)

DEFAULT_COUNTRY = "Peru"

app = Flask(__name__, static_folder=str(STATIC), template_folder=str(TEMPLATES))


def _combined() -> "Path":
    return OUTPUT / all_filename(dataset().latest)


@app.get("/")
def index():
    return preview(DEFAULT_COUNTRY)


@app.get("/profile/<country>")
def preview(country: str):
    data = dataset()
    try:
        return render_html(
            country,
            css_href=url_for("static", filename="profile.css"),
            chrome=True,
            countries=data.countries,
            build=jobs.status(_combined()),
        )
    except KeyError:
        abort(404, f"No profile for {country!r}")


@app.get("/profile/<country>.pdf")
def download(country: str):
    try:
        pdf = render_pdf(country)
    except KeyError:
        abort(404, f"No profile for {country!r}")
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{filename(country, dataset().latest)}"'
        },
    )


@app.post("/profiles/build")
def build_all():
    """Start building the combined PDF on a worker thread."""
    return jsonify(jobs.start(_combined(), dataset().countries))


@app.get("/profiles/status")
def build_status():
    return jsonify(jobs.status(_combined()))


@app.get("/profiles.pdf")
def download_all():
    """Serve the combined PDF straight off disk.

    If it has not been built yet -- a stale tab, a bookmarked URL -- start the
    build and send them back to the app, where the button reports progress,
    rather than leaving them on a dead-end error page.
    """
    target = _combined()
    if not target.exists():
        jobs.start(target, dataset().countries)
        return redirect(url_for("index"), code=303)
    return send_file(target, as_attachment=True, download_name=target.name)
