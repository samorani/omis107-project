"""Rules of the office-hours sign-up sheet, tested through Flask's test client."""
from conftest import ADMIN_USERNAME, booking_owner


def test_visitor_not_logged_in_is_sent_to_login_page(client):
    resp = client.get("/")
    assert resp.status_code in (301, 302, 303, 307, 308), "the sheet was shown instead of a redirect"
    assert resp.headers["Location"].split("?")[0].endswith("/login")


def test_short_password_is_refused_at_registration(client, db):
    resp = client.post("/register", data={"username": "alice", "password": "1234567"})
    assert resp.status_code == 200, "registration should re-show the form, not redirect to login"
    assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 0


def test_logged_in_user_can_book_a_free_slot(make_user, db, slot):
    alice = make_user("alice")
    resp = alice.post("/book", data={"slot": slot}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Booked" in resp.get_data(as_text=True)
    assert booking_owner(db, slot) == "alice"


def test_slot_booked_by_another_user_cannot_be_booked_again(make_user, db, slot):
    alice = make_user("alice")
    bob = make_user("bob")
    alice.post("/book", data={"slot": slot})

    resp = bob.post("/book", data={"slot": slot}, follow_redirects=True)
    assert "just taken" in resp.get_data(as_text=True)
    assert booking_owner(db, slot) == "alice"
    assert db.execute("SELECT count(*) FROM bookings").fetchone()[0] == 1


def test_user_can_cancel_own_booking(make_user, db, slot):
    alice = make_user("alice")
    alice.post("/book", data={"slot": slot})

    resp = alice.post("/cancel", data={"slot": slot}, follow_redirects=True)
    assert "cancelled" in resp.get_data(as_text=True)
    assert booking_owner(db, slot) is None


def test_user_cannot_cancel_another_users_booking(make_user, db, slot):
    alice = make_user("alice")
    bob = make_user("bob")
    alice.post("/book", data={"slot": slot})

    resp = bob.post("/cancel", data={"slot": slot}, follow_redirects=True)
    assert "cancelled" not in resp.get_data(as_text=True).replace("don't have", "")
    assert booking_owner(db, slot) == "alice"


def test_administrator_can_cancel_anyones_booking(make_user, db, slot):
    alice = make_user("alice")
    admin = make_user(ADMIN_USERNAME)
    alice.post("/book", data={"slot": slot})

    resp = admin.post("/cancel", data={"slot": slot}, follow_redirects=True)
    assert resp.status_code == 200
    assert booking_owner(db, slot) is None
