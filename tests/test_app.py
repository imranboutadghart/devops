"""Tests for the pastebin Flask app (app.py)."""

import html


# --- index ---------------------------------------------------------------

def test_index_renders_form(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "<title>pastebin</title>" in body
    assert 'name="content"' in body
    assert 'name="title"' in body
    # No "paste saved" banner without a ?created param.
    assert "paste saved" not in body


def test_index_shows_link_when_created(client):
    resp = client.get("/?created=abc123")
    body = resp.get_data(as_text=True)
    assert "paste saved" in body
    assert "/abc123" in body


# --- create_paste --------------------------------------------------------

def test_create_paste_redirects_to_index_with_created(client):
    resp = client.post("/paste", data={"content": "hello world"})
    assert resp.status_code == 302
    assert "/?created=" in resp.headers["Location"]


def test_create_paste_persists_content(client, app_module):
    resp = client.post("/paste", data={"title": "my title", "content": "the body"})
    paste_id = resp.headers["Location"].split("created=")[1]

    with app_module.app.app_context():
        paste = app_module.db.session.get(app_module.Paste, paste_id)
        assert paste is not None
        assert paste.title == "my title"
        assert paste.content == "the body"


def test_create_paste_empty_content_redirects_without_saving(client, app_module):
    resp = client.post("/paste", data={"content": "   "})
    assert resp.status_code == 302
    assert "created=" not in resp.headers["Location"]

    with app_module.app.app_context():
        assert app_module.Paste.query.count() == 0


def test_create_paste_missing_content_redirects(client):
    resp = client.post("/paste", data={})
    assert resp.status_code == 302
    assert "created=" not in resp.headers["Location"]


def test_create_paste_blank_title_stored_as_none(client, app_module):
    resp = client.post("/paste", data={"title": "   ", "content": "body"})
    paste_id = resp.headers["Location"].split("created=")[1]

    with app_module.app.app_context():
        paste = app_module.db.session.get(app_module.Paste, paste_id)
        assert paste.title is None


def test_create_paste_truncates_title_to_200(client, app_module):
    long_title = "x" * 500
    resp = client.post("/paste", data={"title": long_title, "content": "body"})
    paste_id = resp.headers["Location"].split("created=")[1]

    with app_module.app.app_context():
        paste = app_module.db.session.get(app_module.Paste, paste_id)
        assert len(paste.title) == 200


def test_create_paste_generates_unique_ids(client):
    locations = set()
    for _ in range(5):
        resp = client.post("/paste", data={"content": "dup content"})
        locations.add(resp.headers["Location"])
    assert len(locations) == 5


# --- view_paste ----------------------------------------------------------

def test_view_paste_renders_content(client):
    resp = client.post("/paste", data={"title": "Greeting", "content": "hi there"})
    paste_id = resp.headers["Location"].split("created=")[1]

    resp = client.get(f"/{paste_id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "hi there" in body
    assert "Greeting" in body


def test_view_paste_404_for_unknown_id(client):
    resp = client.get("/doesnotexist")
    assert resp.status_code == 404


def test_view_paste_raw_returns_plain_text(client):
    content = "raw\ncontent\nlines"
    resp = client.post("/paste", data={"content": content})
    paste_id = resp.headers["Location"].split("created=")[1]

    resp = client.get(f"/{paste_id}?raw=1")
    assert resp.status_code == 200
    assert resp.mimetype == "text/plain"
    assert resp.get_data(as_text=True) == content


def test_view_paste_escapes_html_in_content(client):
    payload = "<script>alert('xss')</script>"
    resp = client.post("/paste", data={"content": payload})
    paste_id = resp.headers["Location"].split("created=")[1]

    resp = client.get(f"/{paste_id}")
    body = resp.get_data(as_text=True)
    assert payload not in body
    assert html.escape(payload) in body


def test_view_paste_escapes_html_in_title(client):
    payload = "<b>title</b>"
    resp = client.post("/paste", data={"title": payload, "content": "body"})
    paste_id = resp.headers["Location"].split("created=")[1]

    resp = client.get(f"/{paste_id}")
    body = resp.get_data(as_text=True)
    assert html.escape(payload) in body


def test_view_paste_raw_is_not_escaped(client):
    payload = "<script>alert(1)</script>"
    resp = client.post("/paste", data={"content": payload})
    paste_id = resp.headers["Location"].split("created=")[1]

    resp = client.get(f"/{paste_id}?raw")
    assert resp.get_data(as_text=True) == payload


# --- model ---------------------------------------------------------------

def test_paste_to_dict(app_module):
    paste = app_module.Paste(id="id1", title="t", content="c")
    assert paste.to_dict() == {"id": "id1", "title": "t", "content": "c"}
