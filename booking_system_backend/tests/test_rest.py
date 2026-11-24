import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import User, Flight, FlightSeatClass, Booking, SeatClass


def get_seats(db_session, flight_id, seat_class):
    """Return seats_available for a flight's seat class, read fresh from the DB."""
    row = db_session.query(FlightSeatClass).filter(
        FlightSeatClass.flight_id == flight_id,
        FlightSeatClass.seat_class == seat_class
    ).one()
    db_session.refresh(row)
    return row.seats_available


class TestFlightsEndpoint:
    """Test /flights endpoint."""

    def test_get_flights_empty(self, client, db_session):
        """Test getting flights when database is empty."""
        response = client.get("/flights")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_flights_with_data(self, client, db_session, create_flight):
        """Test getting flights with data."""
        create_flight({
            SeatClass.ECONOMY: 5,
            SeatClass.BUSINESS: 2,
            SeatClass.GALAXIUM: 1,
        })

        response = client.get("/flights")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["origin"] == "Earth"
        assert data[0]["destination"] == "Mars"
        assert "price" not in data[0]
        assert "seats_available" not in data[0]

        # Class order is not guaranteed, so look classes up by name
        classes = {sc["seat_class"]: sc for sc in data[0]["seat_classes"]}
        assert set(classes) == {"economy", "business", "galaxium"}
        assert classes["economy"] == {"seat_class": "economy", "price": 1000000, "seats_available": 5}
        assert classes["business"] == {"seat_class": "business", "price": 2000000, "seats_available": 2}
        assert classes["galaxium"] == {"seat_class": "galaxium", "price": 4000000, "seats_available": 1}


class TestRegisterEndpoint:
    """Test /register endpoint."""

    def test_register_success(self, client, db_session, sample_user_data):
        """Test successful user registration."""
        response = client.post("/register", json=sample_user_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_user_data["name"]
        assert data["email"] == sample_user_data["email"]
        assert "user_id" in data

    def test_register_duplicate_email(self, client, db_session, sample_user_data):
        """Test registration with duplicate email."""
        client.post("/register", json=sample_user_data)
        response = client.post("/register", json=sample_user_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "EMAIL_EXISTS"


class TestUserEndpoint:
    """Test /user endpoint."""

    def test_get_user_success(self, client, db_session, sample_user_data):
        """Test successful user retrieval."""
        client.post("/register", json=sample_user_data)

        response = client.get(
            "/user",
            params={"name": sample_user_data["name"], "email": sample_user_data["email"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_user_data["name"]

    def test_get_user_not_found(self, client, db_session):
        """Test user retrieval when not found."""
        response = client.get(
            "/user",
            params={"name": "NonExistent", "email": "none@example.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "USER_NOT_FOUND"


class TestBookEndpoint:
    """Test /book endpoint."""

    def test_book_flight_success(self, client, db_session, sample_user_data, create_flight):
        """Test successful flight booking."""
        # Register user
        user_response = client.post("/register", json=sample_user_data)
        user_id = user_response.json()["user_id"]

        # Create flight
        flight = create_flight({SeatClass.ECONOMY: 5})

        # Book flight
        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight.flight_id,
            "seat_class": "economy"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "booked"
        assert data["user_id"] == user_id
        assert data["seat_class"] == "economy"
        assert get_seats(db_session, flight.flight_id, SeatClass.ECONOMY) == 4

    def test_book_flight_not_found(self, client, db_session, sample_user_data):
        """Test booking non-existent flight."""
        user_response = client.post("/register", json=sample_user_data)
        user_id = user_response.json()["user_id"]

        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": 999,
            "seat_class": "economy"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "FLIGHT_NOT_FOUND"

    def test_book_flight_decrements_only_chosen_class(self, client, db_session, sample_user_data, create_flight):
        """Test booking Galaxium decrements only the Galaxium inventory."""
        user_id = client.post("/register", json=sample_user_data).json()["user_id"]
        flight = create_flight({
            SeatClass.ECONOMY: 5,
            SeatClass.BUSINESS: 3,
            SeatClass.GALAXIUM: 2,
        })

        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight.flight_id,
            "seat_class": "galaxium"
        })

        assert response.status_code == 200
        assert response.json()["seat_class"] == "galaxium"
        assert get_seats(db_session, flight.flight_id, SeatClass.GALAXIUM) == 1
        assert get_seats(db_session, flight.flight_id, SeatClass.ECONOMY) == 5
        assert get_seats(db_session, flight.flight_id, SeatClass.BUSINESS) == 3

    def test_book_flight_galaxium_sold_out_economy_available(self, client, db_session, sample_user_data, create_flight):
        """Test sold-out Galaxium returns an error while Economy can still be booked."""
        user_id = client.post("/register", json=sample_user_data).json()["user_id"]
        flight = create_flight({SeatClass.ECONOMY: 3, SeatClass.GALAXIUM: 0})
        payload = {
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight.flight_id,
        }

        sold_out = client.post("/book", json={**payload, "seat_class": "galaxium"})
        assert sold_out.status_code == 200
        assert sold_out.json()["success"] == False
        assert sold_out.json()["error_code"] == "NO_SEATS_AVAILABLE"

        economy = client.post("/book", json={**payload, "seat_class": "economy"})
        assert economy.status_code == 200
        assert economy.json()["status"] == "booked"

    def test_book_flight_class_not_offered(self, client, db_session, sample_user_data, create_flight):
        """Test booking a class the flight does not offer."""
        user_id = client.post("/register", json=sample_user_data).json()["user_id"]
        flight = create_flight({SeatClass.ECONOMY: 5})

        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight.flight_id,
            "seat_class": "business"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "NO_SEATS_AVAILABLE"

    def test_book_flight_invalid_seat_class(self, client, db_session, sample_user_data, create_flight):
        """Test an invalid seat_class value is rejected by validation."""
        user_id = client.post("/register", json=sample_user_data).json()["user_id"]
        flight = create_flight()

        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight.flight_id,
            "seat_class": "first_class"
        })

        assert response.status_code == 422
        assert db_session.query(Booking).count() == 0

    def test_book_flight_missing_seat_class(self, client, db_session, sample_user_data, create_flight):
        """Test seat_class is required (no default)."""
        user_id = client.post("/register", json=sample_user_data).json()["user_id"]
        flight = create_flight()

        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight.flight_id
        })

        assert response.status_code == 422
        assert db_session.query(Booking).count() == 0


class TestBookingsEndpoint:
    """Test /bookings/{user_id} endpoint."""

    def test_get_bookings_success(self, client, db_session, sample_user_data, create_flight):
        """Test getting user bookings."""
        # Register user
        user_response = client.post("/register", json=sample_user_data)
        user_id = user_response.json()["user_id"]

        # Create flight and booking
        flight = create_flight({SeatClass.BUSINESS: 5})

        db_session.add(Booking(
            user_id=user_id,
            flight_id=flight.flight_id,
            seat_class=SeatClass.BUSINESS,
            status="booked",
            booking_time="2099-01-01T10:00:00Z"
        ))
        db_session.commit()

        response = client.get(f"/bookings/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "booked"
        assert data[0]["seat_class"] == "business"

    def test_get_bookings_empty(self, client, db_session):
        """Test getting bookings when user has none."""
        response = client.get("/bookings/999")
        assert response.status_code == 200
        assert response.json() == []


class TestCancelEndpoint:
    """Test /cancel/{booking_id} endpoint."""

    def test_cancel_booking_success(self, client, db_session, sample_user_data, create_flight):
        """Test successful booking cancellation."""
        # Register user
        user_response = client.post("/register", json=sample_user_data)
        user_id = user_response.json()["user_id"]

        # Create flight and booking
        flight = create_flight({SeatClass.ECONOMY: 4})

        db_session.add(Booking(
            user_id=user_id,
            flight_id=flight.flight_id,
            seat_class=SeatClass.ECONOMY,
            status="booked",
            booking_time="2099-01-01T10:00:00Z"
        ))
        db_session.commit()
        booking = db_session.query(Booking).first()

        response = client.post(f"/cancel/{booking.booking_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert get_seats(db_session, flight.flight_id, SeatClass.ECONOMY) == 5

    def test_cancel_booking_restores_correct_class(self, client, db_session, sample_user_data, create_flight):
        """Test cancelling a Business booking restores only the Business seat."""
        user_id = client.post("/register", json=sample_user_data).json()["user_id"]
        flight = create_flight({
            SeatClass.ECONOMY: 5,
            SeatClass.BUSINESS: 3,
            SeatClass.GALAXIUM: 2,
        })

        booked = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight.flight_id,
            "seat_class": "business"
        }).json()
        assert get_seats(db_session, flight.flight_id, SeatClass.BUSINESS) == 2

        response = client.post(f"/cancel/{booked['booking_id']}")

        assert response.status_code == 200
        assert response.json()["seat_class"] == "business"
        assert get_seats(db_session, flight.flight_id, SeatClass.BUSINESS) == 3
        assert get_seats(db_session, flight.flight_id, SeatClass.ECONOMY) == 5
        assert get_seats(db_session, flight.flight_id, SeatClass.GALAXIUM) == 2

    def test_cancel_booking_not_found(self, client, db_session):
        """Test cancelling non-existent booking."""
        response = client.post("/cancel/999")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "BOOKING_NOT_FOUND"


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client, db_session):
        """Test health check returns OK."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"status": "OK"}
