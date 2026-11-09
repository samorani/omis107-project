"""Shared pytest setup for the sign-up sheet tests.

The app reads its settings at import time, so before importing it we point
DATABASE_URL at the database named by TEST_DATABASE_URL in .env. The real
DATABASE_URL is never used. Every test starts with empty tables.
"""
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    pytest.exit("TEST_DATABASE_URL is not set in .env. The tests only run against the test database.", returncode=1)
if TEST_DATABASE_URL == os.environ.get("DATABASE_URL"):
    pytest.exit("TEST_DATABASE_URL is the same as DATABASE_URL. Refusing to run tests on the real database.", returncode=1)

ADMIN_USERNAME = "admin"
PASSWORD = "correct-horse-battery"

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ["ADMIN_USERNAME"] = ADMIN_USERNAME

# Start from the schema app.py expects: drop whatever is in the test database
# (it is guaranteed above not to be the real one) and let the app's init_db,
# which runs on import, recreate the tables.
with psycopg.connect(TEST_DATABASE_URL) as _db:
    _db.execute("DROP TABLE IF EXISTS bookings, users CASCADE")

import app as signup  # noqa: E402  (must come after the environment is set)


@pytest.fixture(autouse=True)
def empty_tables():
    """Empty the test database's tables before each test."""
    with psycopg.connect(TEST_DATABASE_URL) as db:
        db.execute("TRUNCATE bookings, users RESTART IDENTITY CASCADE")


@pytest.fixture
def db():
    """A connection to the test database for checking state directly."""
    with psycopg.connect(TEST_DATABASE_URL) as conn:
        yield conn


@pytest.fixture
def client():
    """An anonymous Flask test client with its own cookie jar."""
    signup.app.config["TESTING"] = True
    return signup.app.test_client()


@pytest.fixture
def make_user():
    """Register a user and return a test client logged in as that user.

    Each call returns a separate client, so several users can act in one test.
    """
    def _make_user(username, password=PASSWORD):
        c = signup.app.test_client()
        resp = c.post("/register", data={"username": username, "password": password})
        assert resp.status_code == 302, f"registration of {username} failed"
        resp = c.post("/login", data={"username": username, "password": password})
        assert resp.status_code == 302, f"login of {username} failed"
        return c
    return _make_user


@pytest.fixture
def slot():
    """A bookable slot: next Monday at 2:00 pm. Always in the future, always valid."""
    monday = signup.week_start(date.today()) + timedelta(weeks=1)
    return datetime.combine(monday, time(14, 0)).isoformat()


def booking_owner(db, slot):
    """Username of whoever holds the slot, or None if it is free."""
    row = db.execute(
        "SELECT u.username FROM bookings b JOIN users u ON u.id = b.user_id WHERE b.slot_start = %s",
        (slot,),
    ).fetchone()
    return row[0] if row else None
