import os
import tempfile
import uuid

# Must be set before any `app.*` import so the engine binds to a test DB.
_TEST_DB = os.path.join(tempfile.gettempdir(), "longithread_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["ENVIRONMENT"] = "test"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine, SessionLocal
from app.main import app
from app.models import Patient, Tenant


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    if os.path.exists(_TEST_DB):
        try:
            os.remove(_TEST_DB)
        except OSError:
            pass
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()
    if os.path.exists(_TEST_DB):
        try:
            os.remove(_TEST_DB)
        except OSError:
            pass


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _headers(tenant_id: uuid.UUID | None = None) -> dict:
    tid = tenant_id or uuid.uuid4()
    return {"x-tenant-id": str(tid), "x-user-id": str(uuid.uuid4()), "x-user-role": "clinician"}


@pytest.fixture()
def tenant_a() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def tenant_b() -> uuid.UUID:
    return uuid.uuid4()
