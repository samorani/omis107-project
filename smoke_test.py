"""Smoke test: register, log in, book, re-book, and cancel against a PostgreSQL database.

Reads TEST_DATABASE_URL (never DATABASE_URL) so it cannot run against the real database.
Run with:  python smoke_test.py
"""
import os
import sys
from datetime import date, datetime, time, timedelta

from dotenv import load_dotenv

load_dotenv()

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    sys.exit("TEST_DATABASE_URL is not set. The smoke test only runs against the database "
             "named by TEST_DATABASE_URL, e.g. postgresql://user:password@host/dbname")

# The app reads its settings at import time. Point it at the test database, give it a
# throwaway secret if none is set, and make the throwaway user the administrator so the
# admin rule is exercised too.
TEST_USERNAME = "smoke_" + datetime.now().strftime("%Y%m%d%H%M%S%f")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SECRET_KEY", "smoke-test-secret")
os.environ["ADMIN_USERNAME"] = TEST_USERNAME

import psycopg  # noqa: E402

import app as signup  # noqa: E402


def check(label, ok):
    print(f"{'ok  ' if ok else 'FAIL'} {label}")
    if not ok:
        sys.exit(1)


def main():
    client = signup.app.test_client()
    username = TEST_USERNAME
    password = "test-password"

    # A slot next Monday at 2:00 pm: always in the future and always a valid slot.
    monday = signup.week_start(date.today()) + timedelta(weeks=1)
    slot = datetime.combine(monday, time(14, 0)).isoformat()

    try:
        resp = client.post("/register", data={"username": username, "password": password})
        check("register redirects to login", resp.status_code == 302)

        page = client.post("/register", data={"username": username, "password": password}).get_data(as_text=True)
        check("duplicate username is rejected", "already taken" in page)

        resp = client.post("/login", data={"username": username, "password": password})
        check("login redirects to calendar", resp.status_code == 302)

        page = client.get("/?week=" + monday.isoformat()).get_data(as_text=True)
        check("calendar page renders", monday.strftime("%B") in page)
        check("ADMIN_USERNAME user sees the admin view", "Admin view" in page)

        page = client.post("/book", data={"slot": slot}, follow_redirects=True).get_data(as_text=True)
        check("booking a free slot succeeds", "Booked" in page)

        page = client.post("/book", data={"slot": slot}, follow_redirects=True).get_data(as_text=True)
        check("booking a taken slot is refused", "just taken" in page)

        page = client.post("/cancel", data={"slot": slot}, follow_redirects=True).get_data(as_text=True)
        check("cancelling own booking succeeds", "cancelled" in page)

        page = client.post("/cancel", data={"slot": slot}, follow_redirects=True).get_data(as_text=True)
        check("cancelling an empty slot is refused", "don't have a booking" in page)

        resp = client.post("/logout")
        check("logout redirects home", resp.status_code == 302)
    finally:
        with psycopg.connect(TEST_DATABASE_URL) as db:
            db.execute("DELETE FROM bookings WHERE user_id IN (SELECT id FROM users WHERE username = %s)", (username,))
            db.execute("DELETE FROM users WHERE username = %s", (username,))

    print("All smoke checks passed.")


if __name__ == "__main__":
    main()
