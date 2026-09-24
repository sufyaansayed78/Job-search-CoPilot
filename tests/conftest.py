import os

# Must happen before any `app.*` module is imported anywhere in the test
# session — app/config.py builds its Settings() singleton (and app/database.py
# builds its engine) at import time, so patching os.environ inside a fixture
# body is too late once another test module has already triggered the import.
os.environ["DATABASE_URL"] = "sqlite:///./test_job_copilot.db"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

TEST_DB_URL = os.environ["DATABASE_URL"]


@pytest.fixture(scope="session")
def client():
    from app.main import app
    from app.database import Base, get_db

    test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def auth_headers(client):
    """Registers a fresh user and returns Authorization headers for it."""
    import uuid
    email = f"user-{uuid.uuid4().hex[:8]}@copilot.com"
    client.post("/auth/register", json={
        "username": f"user-{uuid.uuid4().hex[:8]}",
        "email": email,
        "password": "Secure123!",
    })
    token_resp = client.post("/auth/token", data={"username": email, "password": "Secure123!"})
    token = token_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def company_id(client, auth_headers):
    resp = client.post(
        "/companies/",
        json={"name": "Acme Corp", "website": "https://acme.example", "notes": "Referral from a friend"},
        headers=auth_headers,
    )
    return resp.json()["id"]


@pytest.fixture
def posting_id(client, auth_headers, company_id):
    resp = client.post(
        "/job-postings/",
        json={
            "company_id": company_id,
            "title": "Backend Engineer",
            "url": "https://acme.example/jobs/1",
            "source": "manual",
            "raw_description": "We need 5+ years Python, Django, PostgreSQL, AWS.",
        },
        headers=auth_headers,
    )
    return resp.json()["id"]
