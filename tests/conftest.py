"""Shared pytest fixtures for the pastebin app.

app.py runs init_db() at import time, which opens a database connection, so we
must point DATABASE_URL at a throwaway SQLite database *before* importing the
module. A temp file (rather than :memory:) is used so the schema survives across
the separate connections Flask-SQLAlchemy's pool may hand out during a request.
"""

import importlib
import os
import sys
import tempfile

import pytest

# Make the project root importable (app.py lives one level up from tests/).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture()
def app_module():
    """Import app.py freshly against an isolated SQLite database per test."""
    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite")
    os.close(db_fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    # Ensure a clean import so init_db() runs against the temp database.
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    module.app.config.update(TESTING=True)

    # Start each test from an empty table.
    with module.app.app_context():
        module.db.drop_all()
        module.db.create_all()

    try:
        yield module
    finally:
        with module.app.app_context():
            module.db.session.remove()
        sys.modules.pop("app", None)
        os.unlink(db_path)


@pytest.fixture()
def client(app_module):
    return app_module.app.test_client()
