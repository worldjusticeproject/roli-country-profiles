"""The Flask routes and the background build."""

import time

import pytest

from country_profiles import jobs
from country_profiles.app import app
from country_profiles.render import render_all_pdf

TWO = ["Denmark", "Peru"]


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_default_profile_is_served_at_root(client):
    body = client.get("/").data.decode()
    assert "<title>Peru" in body
    assert 'id="pick"' in body           # the picker is on the profile itself
    assert body.count("<option") == 143


def test_picker_marks_the_current_country(client):
    body = client.get("/profile/Denmark").data.decode()
    assert '<option value="Denmark" selected>' in body


def test_toolbar_never_reaches_the_pdf():
    from country_profiles.render import render_html

    assert "toolbar" not in render_html("Peru")


def test_unknown_country_is_404(client):
    assert client.get("/profile/Atlantis").status_code == 404
    assert client.get("/profile/Atlantis.pdf").status_code == 404


def test_single_pdf(client):
    response = client.get("/profile/Peru.pdf")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert "Peru_2026_country_profile.pdf" in response.headers["Content-Disposition"]


def test_combined_pdf_starts_a_build_when_missing(client, monkeypatch, tmp_path):
    """A stale tab or bookmarked URL should not hit a dead end."""
    started = []
    monkeypatch.setattr("country_profiles.app.OUTPUT", tmp_path)
    monkeypatch.setattr("country_profiles.app.jobs.start",
                        lambda target, countries: started.append(target))

    response = client.get("/profiles.pdf")
    assert response.status_code == 303
    assert response.headers["Location"].endswith("/")
    assert started


def test_progress_is_reported():
    seen = []
    render_all_pdf(TWO, on_progress=lambda done, total: seen.append((done, total)))
    assert seen == [(1, 2), (2, 2)]


def test_background_build_writes_the_file(tmp_path):
    target = tmp_path / "combined.pdf"

    assert jobs.status(target)["state"] == "idle"
    assert jobs.start(target, TWO)["state"] == "running"
    # A second request while running must not start a rival build.
    assert jobs.start(target, TWO)["state"] == "running"

    deadline = time.time() + 60
    while jobs.status(target)["state"] == "running" and time.time() < deadline:
        time.sleep(0.2)

    status = jobs.status(target)
    assert status["state"] == "ready", status
    assert status["done"] == 2
    assert target.exists()
    assert not target.with_name(target.name + ".part").exists()
    assert target.read_bytes().startswith(b"%PDF")
