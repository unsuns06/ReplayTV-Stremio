"""The programs.json editor served at /: local-only, and it writes the file
back in the layout the repo keeps it in."""

import json
import os
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.routers import editor

SHOWS = [
    {"provider": "cbc", "slug": "dragons-den", "name": "Dragon's Den"},
    {"provider": "francetv", "slug": "envoye-special", "name": "Envoyé spécial"},
]


def _request(host):
    """Enough of a Request for _is_local; TestClient cannot set the peer."""
    return SimpleNamespace(client=SimpleNamespace(host=host) if host else None)


@pytest.fixture
def local(monkeypatch):
    """A client the editor accepts — same machine as the addon."""
    monkeypatch.setattr(editor, "_is_local", lambda request: True)
    return TestClient(app)


@pytest.fixture
def remote():
    """Anything else: TestClient's default peer is the host 'testclient'."""
    return TestClient(app)


# --- the guard ------------------------------------------------------------

@pytest.mark.parametrize("host, expected", [
    ("127.0.0.1", True), ("::1", True), ("localhost", True),
    ("10.0.0.5", False), ("203.0.113.7", False), (None, False),
])
def test_only_the_local_machine_is_trusted(host, expected):
    assert editor._is_local(_request(host)) is expected


def test_the_env_override_opens_it_up(monkeypatch):
    monkeypatch.setenv("ENABLE_REMOTE_EDITOR", "1")
    assert editor._is_local(_request("203.0.113.7")) is True


def test_homepage_is_the_editor_locally(local):
    response = local.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>Catch-up TV &amp; More — Shows</title>" in response.text


def test_homepage_is_the_plain_api_greeting_from_anywhere_else(remote):
    assert remote.get("/").json() == {"message": "Catch-up TV & More for Stremio API"}


def test_a_remote_client_can_neither_read_nor_write(remote):
    assert remote.get("/api/programs").status_code == 403
    assert remote.post("/api/programs", json={"shows": []}).status_code == 403
    assert remote.get("/api/catalogue/cbc").status_code == 403


def test_the_manifest_is_still_served(local):
    assert local.get("/manifest.json").status_code == 200


# --- writing --------------------------------------------------------------

def test_the_file_layout_survives_a_round_trip():
    """One show per line, 2-space indent, spaces inside the braces — a save
    must not reflow every line of the file."""
    dumped = editor.dump_programs({"version": "1.0", "shows": SHOWS})
    assert dumped == (
        '{\n'
        '  "version": "1.0",\n'
        '  "shows": [\n'
        '    { "provider": "cbc", "slug": "dragons-den", "name": "Dragon\'s Den" },\n'
        '    { "provider": "francetv", "slug": "envoye-special", "name": "Envoyé spécial" }\n'
        '  ]\n'
        '}\n'
    )
    assert json.loads(dumped)["shows"] == SHOWS


def test_pinned_fields_are_carried_through_untouched():
    kept = {"provider": "cbc", "slug": "x", "name": "X", "poster": "http://pin/p.jpg"}
    assert editor.validate({"shows": [kept]})[0]["poster"] == "http://pin/p.jpg"


def test_a_disabled_show_stays_disabled():
    shows = editor.validate({"shows": [{"provider": "cbc", "slug": "x", "name": "X",
                                        "enabled": False}]})
    assert shows[0]["enabled"] is False


@pytest.mark.parametrize("payload, message", [
    ({"shows": "nope"}, "expected an object with a 'shows' list"),
    ({}, "expected an object with a 'shows' list"),
    ({"shows": [[1, 2]]}, "show 0 is not an object"),
    ({"shows": [{"provider": "cbc", "slug": "x"}]}, "show 0: 'name' is required"),
    ({"shows": [{"provider": "cbc", "slug": " ", "name": "X"}]}, "show 0: 'slug' is required"),
    ({"shows": [{"provider": "netflix", "slug": "x", "name": "X"}]}, "unknown provider 'netflix'"),
    ({"shows": [{"provider": "cbc", "slug": "x", "name": "X"},
                {"provider": "cbc", "slug": "x", "name": "Y"}]}, "duplicate show: cbc/x"),
])
def test_bad_input_never_reaches_the_file(payload, message):
    with pytest.raises(ValueError, match=message):
        editor.validate(payload)


def test_the_same_slug_on_two_providers_is_fine():
    assert len(editor.validate({"shows": [{"provider": "cbc", "slug": "x", "name": "X"},
                                          {"provider": "mytf1", "slug": "x", "name": "X"}]})) == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
