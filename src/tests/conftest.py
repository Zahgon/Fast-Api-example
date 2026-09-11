"""Test configuration for the Flask application.

The FastAPI suite mocked every ``crud`` call and injected an ``AsyncMock``
session through ``app.dependency_overrides``. Flask has no dependency-override
mechanism, so the same scenarios are exercised against a real (throwaway)
SQLite database instead; the intent of each test is unchanged.
"""

import os
import tempfile

import pytest

# The engine is built at import time from Settings, so the database URL has to
# be in the environment before anything under ``app`` is imported.
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app.db import engine, metadata  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    metadata.create_all(engine)
    yield
    metadata.drop_all(engine)
    engine.dispose()
    try:
        os.unlink(_DB_PATH)
    except OSError:
        pass


@pytest.fixture()
def flask_app():
    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def test_app(flask_app):
    # Deliberately not used as a context manager: `with test_client()` keeps the
    # request context alive after each call, which would stop
    # teardown_appcontext from closing the session and leave SQLite mid-transaction.
    return flask_app.test_client()


@pytest.fixture(autouse=True)
def _clean_tables(_schema):
    """Truncate between tests so ids and listings stay predictable."""
    from app.db import notes, users

    with engine.begin() as conn:
        conn.execute(notes.delete())
        conn.execute(users.delete())
    yield


def _register_and_login(client, username, email, password="password123"):
    client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    response = client.post(
        "/auth/token",
        data={"username": username, "password": password},
        content_type="application/x-www-form-urlencoded",
    )
    return response.get_json()["access_token"]


@pytest.fixture()
def token(test_app):
    return _register_and_login(test_app, "testuser", "test@example.com")


@pytest.fixture()
def token_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def second_token_headers(test_app):
    other = _register_and_login(test_app, "otheruser", "other@example.com")
    return {"Authorization": f"Bearer {other}"}
