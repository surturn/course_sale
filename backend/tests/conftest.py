"""Tests run against the invonics_test database on the dev Postgres
(create once: CREATE DATABASE invonics_test; then DATABASE_URL=<test url> alembic upgrade head).
Each test uses unique emails/phones so runs never collide."""
import os
import random
import uuid

# Point at the throwaway test database before the app (and its engine) is imported.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://invonics:invonics_dev_pass@localhost:5433/invonics_test")

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


def new_user_payload(**overrides):
    payload = {
        "email": f"{uuid.uuid4().hex[:10]}@example.com",
        "phone": f"2547{random.randint(10_000_000, 99_999_999)}",
        "full_name": "Test Buyer",
        "password": "correct horse battery",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
async def logged_in(client):
    """A client with a freshly registered, logged-in user. Returns the user payload."""
    user = new_user_payload()
    assert (await client.post("/api/v1/auth/register", json=user)).status_code == 201
    assert (await client.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]})).status_code == 200
    return user


@pytest.fixture(autouse=True)
def mock_daraja(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "DARAJA_ENV", "mock")
    monkeypatch.setattr(settings, "DARAJA_CALLBACK_SECRET", "test-secret")


@pytest.fixture
async def make_resource():
    """Factory: insert a resource straight into the DB, return its id."""
    from app.core.database import AsyncSessionLocal
    from app.models import Resource, ResourceType

    async def _make(price=150, published=True, title="Test Notes"):
        async with AsyncSessionLocal() as db:
            r = Resource(title=title, type=ResourceType.pdf, price=price, published=published)
            db.add(r)
            await db.commit()
            return r.id
    return _make


@pytest.fixture(autouse=True)
def temp_storage(monkeypatch, tmp_path):
    from app.core.config import settings
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    return tmp_path


def make_pdf(pages=3) -> bytes:
    import io
    from pypdf import PdfWriter
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
async def admin(client, logged_in):
    """Promote the logged-in user to admin."""
    from sqlalchemy import update
    from app.core.database import AsyncSessionLocal
    from app.models import User
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.email == logged_in["email"]).values(is_admin=True))
        await db.commit()
    return logged_in


@pytest.fixture(autouse=True)
def reset_throttle():
    from app.security import _failures
    _failures.clear()
