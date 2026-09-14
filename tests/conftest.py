import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def client(tmp_path):
    """A TestClient wired to an empty database, rebuilt for every test.

    Three steps: 
    1. build a throwaway database
    3. point the app at it
    2. hand back a client that talks to the app without running a server.
    """
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    TestingSession = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    # Point the app at the test database without touching any router code.
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def alice():
    """Headers for alice, the seller in most tests."""
    return {"X-User-Id": "alice"}


@pytest.fixture
def bob():
    """Headers for bob, the buyer in most tests."""
    return {"X-User-Id": "bob"}


@pytest.fixture
def listing(client, alice):
    """A listing owned by alice: 5 units at 10.50."""
    r = client.post(
        "/listings",
        json={"title": "LOL Unranked Smurf Account", "game": "LOL", "price": "300.50", "quantity": 5},
        headers=alice,
    )
    assert r.status_code == 200
    return r.json()