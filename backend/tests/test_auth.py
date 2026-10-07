from tests.conftest import new_user_payload


async def test_register_login_me_round_trip(client):
    user = new_user_payload()
    r = await client.post("/api/v1/auth/register", json=user)
    assert r.status_code == 201
    assert "password" not in r.text

    r = await client.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie

    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == user["email"]


async def test_me_requires_login(client):
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_wrong_password_is_401(client):
    user = new_user_payload()
    await client.post("/api/v1/auth/register", json=user)
    r = await client.post("/api/v1/auth/login", json={"email": user["email"], "password": "wrong password!"})
    assert r.status_code == 401


async def test_duplicate_email_is_409(client):
    user = new_user_payload()
    await client.post("/api/v1/auth/register", json=user)
    r = await client.post("/api/v1/auth/register", json=new_user_payload(email=user["email"]))
    assert r.status_code == 409


async def test_phone_is_normalised_to_254_format(client):
    user = new_user_payload()
    local = "0" + user["phone"][3:]  # 2547XXXXXXXX -> 07XXXXXXXX
    r = await client.post("/api/v1/auth/register", json={**user, "phone": local})
    assert r.status_code == 201
    assert r.json()["phone"] == user["phone"]


async def test_invalid_phone_is_422(client):
    r = await client.post("/api/v1/auth/register", json=new_user_payload(phone="12345"))
    assert r.status_code == 422


async def test_logout_clears_session(client, logged_in):
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_repeated_failed_logins_are_throttled(client):
    user = new_user_payload()
    await client.post("/api/v1/auth/register", json=user)
    wrong = {"email": user["email"], "password": "not the password"}
    codes = [(await client.post("/api/v1/auth/login", json=wrong)).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429
    # even the right password is refused until the window passes
    r = await client.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]})
    assert r.status_code == 429
