import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import Base, Flight, FlightSeatClass, SeatClass
from db import SessionLocal

PRICES = {
    SeatClass.ECONOMY: 1000000,
    SeatClass.BUSINESS: 2000000,
    SeatClass.GALAXIUM: 4000000,
}

# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session, monkeypatch):
    """Create a test client with a fresh database."""
    # Import server module and patch SessionLocal
    import server
    import db as db_module

    # Patch SessionLocal to use test session factory
    def get_test_session():
        return db_session

    monkeypatch.setattr(db_module, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(server, "SessionLocal", lambda: db_session)

    # Don't run seed during tests
    monkeypatch.setattr(server, "seed", lambda: None)

    # Override get_db dependency to use test session
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    server.app.dependency_overrides[db_module.get_db] = override_get_db

    with TestClient(server.app) as test_client:
        yield test_client

    server.app.dependency_overrides.clear()


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "name": "Test User",
        "email": "test@example.com"
    }


@pytest.fixture
def sample_flight_data():
    """Sample flight data for testing (seat classes are added via create_flight)."""
    return {
        "origin": "Earth",
        "destination": "Mars",
        "departure_time": "2099-01-01T09:00:00Z",
        "arrival_time": "2099-01-01T17:00:00Z"
    }


@pytest.fixture
def sample_booking_data():
    """Sample booking data for testing."""
    return {
        "user_id": 1,
        "name": "Test User",
        "flight_id": 1,
        "seat_class": "economy"
    }


@pytest.fixture
def create_flight(db_session, sample_flight_data):
    """Factory that creates a flight with its seat class rows.

    `seats` maps SeatClass -> seats_available. Only the given classes are created,
    so omitted classes are "not offered" on the flight. Defaults to 5 seats in every class.
    """
    def _create_flight(seats=None):
        if seats is None:
            seats = {sc: 5 for sc in SeatClass}
        flight = Flight(**sample_flight_data)
        flight.seat_classes = [
            FlightSeatClass(seat_class=sc, price=PRICES[sc], seats_available=n)
            for sc, n in seats.items()
        ]
        db_session.add(flight)
        db_session.commit()
        return flight

    return _create_flight
