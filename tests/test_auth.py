from sqlalchemy import select

from app.auth import COOKIE, hash_password, make_session, read_session, verify_password
from app.models import User
from tests.conftest import PASSWORD


def test_password_hashing():
    h = hash_password("segreto123")
    assert h != "segreto123" and h.startswith("$argon2")
    assert verify_password(h, "segreto123")
    assert not verify_password(h, "sbagliata")
    assert not verify_password(None, "segreto123")


def test_session_token_round_trip():
    assert read_session(make_session(42)) == 42
    assert read_session("garbage") is None
    assert read_session(None) is None


def test_protected_routes_redirect_anonymous_to_login(anon):
    for url in ["/", "/pasti", "/pasti/nuovo", "/profilo", "/peso", "/attivita"]:
        r = anon.get(url, follow_redirects=False)
        assert r.status_code == 303, url
        assert r.headers["location"].startswith("/accedi?next="), url
    # HTMX requests get a client-side redirect instead of a 303 they cannot follow.
    r = anon.get("/giorno/2026-10-02", headers={"HX-Request": "true"})
    assert r.status_code == 204 and r.headers["HX-Redirect"].startswith("/accedi")


def test_register_login_logout(anon, db):
    r = anon.post(
        "/registrati",
        data={"email": "Nuovo@Example.com", "password": "password-di-prova", "password2": "password-di-prova"},
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"] == "/profilo"
    assert COOKIE in r.cookies
    user = db.scalar(select(User).where(User.email == "nuovo@example.com"))
    assert user is not None and user.password_hash != "password-di-prova"

    # Logged in: the profile page asks to complete the profile.
    assert 'data-test="welcome"' in anon.get("/profilo").text
    # Balance needs the profile: redirected there.
    r = anon.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/profilo"

    r = anon.post("/esci", follow_redirects=False)
    assert r.status_code == 303
    anon.cookies.clear()
    assert anon.get("/profilo", follow_redirects=False).status_code == 303

    r = anon.post("/accedi", data={"email": "nuovo@example.com", "password": "password-di-prova"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert anon.get("/profilo").status_code == 200


def test_login_rejects_wrong_password(anon, user):
    r = anon.post("/accedi", data={"email": user.email, "password": "nope-nope-nope"})
    assert r.status_code == 401
    assert "Email o password non corretti." in r.text
    assert COOKIE not in r.cookies


def test_login_next_only_same_site(anon, user):
    r = anon.post("/accedi", data={"email": user.email, "password": PASSWORD, "next": "https://evil.example"}, follow_redirects=False)
    assert r.headers["location"] == "/"
    r = anon.post("/accedi", data={"email": user.email, "password": PASSWORD, "next": "/pasti"}, follow_redirects=False)
    assert r.headers["location"] == "/pasti"


def test_register_validation(anon, user):
    def post(**data):
        return anon.post("/registrati", data=data)

    r = post(email="non-email", password="corta", password2="diversa")
    assert r.status_code == 422
    assert "email valido" in r.text and "almeno 8 caratteri" in r.text and "non coincidono" in r.text
    r = post(email=user.email, password="password-di-prova", password2="password-di-prova")
    assert r.status_code == 422 and "Esiste già un account" in r.text
