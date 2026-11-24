import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import User, Flight, FlightSeatClass, Booking, SeatClass
from schemas import ErrorResponse
from services import flight, user, booking


def get_seats(db_session, flight_id, seat_class):
    """Return seats_available for a flight's seat class, read fresh from the DB."""
    row = db_session.query(FlightSeatClass).filter(
        FlightSeatClass.flight_id == flight_id,
        FlightSeatClass.seat_class == seat_class
    ).one()
    db_session.refresh(row)
    return row.seats_available


class TestFlightService:
    """Test flight service functions."""

    def test_list_flights_empty(self, db_session):
        """Test listing flights when database is empty."""
        result = flight.list_flights(db_session)
        assert result == []

    def test_list_flights_with_data(self, db_session, create_flight):
        """Test listing flights with data in database."""
        create_flight()

        result = flight.list_flights(db_session)
        assert len(result) == 1
        assert result[0].origin == "Earth"
        assert result[0].destination == "Mars"

    def test_list_flights_includes_seat_classes(self, db_session, create_flight):
        """Test each flight is returned with per-class price and availability."""
        create_flight({
            SeatClass.ECONOMY: 5,
            SeatClass.BUSINESS: 2,
            SeatClass.GALAXIUM: 1,
        })

        result = flight.list_flights(db_session)
        classes = {sc.seat_class: sc for sc in result[0].seat_classes}
        assert set(classes) == {SeatClass.ECONOMY, SeatClass.BUSINESS, SeatClass.GALAXIUM}
        assert classes[SeatClass.ECONOMY].seats_available == 5
        assert classes[SeatClass.ECONOMY].price == 1000000
        assert classes[SeatClass.BUSINESS].seats_available == 2
        assert classes[SeatClass.BUSINESS].price == 2000000
        assert classes[SeatClass.GALAXIUM].seats_available == 1
        assert classes[SeatClass.GALAXIUM].price == 4000000


class TestUserService:
    """Test user service functions."""

    def test_register_user_success(self, db_session):
        """Test successful user registration."""
        result = user.register_user(db_session, "Test User", "test@example.com")
        assert result.name == "Test User"
        assert result.email == "test@example.com"
        assert result.user_id > 0

    def test_register_user_duplicate_email(self, db_session):
        """Test registration with duplicate email."""
        user.register_user(db_session, "User 1", "test@example.com")
        result = user.register_user(db_session, "User 2", "test@example.com")

        assert isinstance(result, ErrorResponse)
        assert result.error_code == "EMAIL_EXISTS"

    def test_get_user_success(self, db_session):
        """Test successful user retrieval."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.commit()

        result = user.get_user(db_session, "Test User", "test@example.com")
        assert result.name == "Test User"
        assert result.email == "test@example.com"

    def test_get_user_not_found(self, db_session):
        """Test user retrieval when not found."""
        result = user.get_user(db_session, "NonExistent", "none@example.com")
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "USER_NOT_FOUND"


class TestBookingService:
    """Test booking service functions."""

    def test_book_flight_success(self, db_session, create_flight):
        """Test successful flight booking."""
        db_session.add(User(name="Test User", email="test@example.com"))
        flight_obj = create_flight({SeatClass.ECONOMY: 5})

        user_obj = db_session.query(User).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id, SeatClass.ECONOMY)
        assert result.status == "booked"
        assert result.user_id == user_obj.user_id
        assert result.flight_id == flight_obj.flight_id
        assert result.seat_class == SeatClass.ECONOMY

        # Verify seat was decremented
        assert get_seats(db_session, flight_obj.flight_id, SeatClass.ECONOMY) == 4

    def test_book_flight_not_found(self, db_session):
        """Test booking non-existent flight."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.commit()
        user_obj = db_session.query(User).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", 999, SeatClass.ECONOMY)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "FLIGHT_NOT_FOUND"

    def test_book_flight_no_seats(self, db_session, create_flight):
        """Test booking when no seats available."""
        db_session.add(User(name="Test User", email="test@example.com"))
        flight_obj = create_flight({SeatClass.ECONOMY: 0})

        user_obj = db_session.query(User).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id, SeatClass.ECONOMY)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "NO_SEATS_AVAILABLE"

    def test_book_flight_user_not_found(self, db_session, create_flight):
        """Test booking with non-existent user."""
        flight_obj = create_flight()

        result = booking.book_flight(db_session, 999, "Fake User", flight_obj.flight_id, SeatClass.ECONOMY)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "USER_NOT_FOUND"

    def test_book_flight_name_mismatch(self, db_session, create_flight):
        """Test booking with wrong name for user ID."""
        db_session.add(User(name="Real Name", email="test@example.com"))
        flight_obj = create_flight()

        user_obj = db_session.query(User).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Wrong Name", flight_obj.flight_id, SeatClass.ECONOMY)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "NAME_MISMATCH"

    def test_book_flight_decrements_only_chosen_class(self, db_session, create_flight):
        """Test booking one class leaves the other classes' inventory untouched."""
        db_session.add(User(name="Test User", email="test@example.com"))
        flight_obj = create_flight({
            SeatClass.ECONOMY: 5,
            SeatClass.BUSINESS: 3,
            SeatClass.GALAXIUM: 2,
        })
        user_obj = db_session.query(User).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id, SeatClass.BUSINESS)

        assert result.seat_class == SeatClass.BUSINESS
        assert get_seats(db_session, flight_obj.flight_id, SeatClass.BUSINESS) == 2
        assert get_seats(db_session, flight_obj.flight_id, SeatClass.ECONOMY) == 5
        assert get_seats(db_session, flight_obj.flight_id, SeatClass.GALAXIUM) == 2

    def test_book_flight_galaxium_sold_out_economy_available(self, db_session, create_flight):
        """Test a sold-out Galaxium class is rejected while Economy can still be booked."""
        db_session.add(User(name="Test User", email="test@example.com"))
        flight_obj = create_flight({
            SeatClass.ECONOMY: 3,
            SeatClass.GALAXIUM: 0,
        })
        user_obj = db_session.query(User).first()

        galaxium = booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id, SeatClass.GALAXIUM)
        assert isinstance(galaxium, ErrorResponse)
        assert galaxium.error_code == "NO_SEATS_AVAILABLE"
        assert get_seats(db_session, flight_obj.flight_id, SeatClass.GALAXIUM) == 0
        assert get_seats(db_session, flight_obj.flight_id, SeatClass.ECONOMY) == 3

        economy = booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id, SeatClass.ECONOMY)
        assert economy.status == "booked"
        assert get_seats(db_session, flight_obj.flight_id, SeatClass.ECONOMY) == 2

    def test_book_flight_class_not_offered(self, db_session, create_flight):
        """Test booking a class that the flight does not offer."""
        db_session.add(User(name="Test User", email="test@example.com"))
        flight_obj = create_flight({SeatClass.ECONOMY: 5})
        user_obj = db_session.query(User).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id, SeatClass.GALAXIUM)

        assert isinstance(result, ErrorResponse)
        assert result.error_code == "NO_SEATS_AVAILABLE"
        assert db_session.query(Booking).count() == 0
        assert get_seats(db_session, flight_obj.flight_id, SeatClass.ECONOMY) == 5

    def test_cancel_booking_success(self, db_session, create_flight):
        """Test successful booking cancellation."""
        db_session.add(User(name="Test User", email="test@example.com"))
        flight_obj = create_flight({SeatClass.ECONOMY: 4})

        user_obj = db_session.query(User).first()

        db_session.add(Booking(
            user_id=user_obj.user_id,
            flight_id=flight_obj.flight_id,
            seat_class=SeatClass.ECONOMY,
            status="booked",
            booking_time="2099-01-01T10:00:00Z"
        ))
        db_session.commit()

        booking_obj = db_session.query(Booking).first()
        result = booking.cancel_booking(db_session, booking_obj.booking_id)

        assert result.status == "cancelled"

        # Verify seat was restored
        assert get_seats(db_session, flight_obj.flight_id, SeatClass.ECONOMY) == 5

    def test_cancel_booking_restores_correct_class(self, db_session, create_flight):
        """Test cancelling restores the seat to the booking's class only."""
        db_session.add(User(name="Test User", email="test@example.com"))
        flight_obj = create_flight({
            SeatClass.ECONOMY: 5,
            SeatClass.BUSINESS: 3,
            SeatClass.GALAXIUM: 2,
        })
        user_obj = db_session.query(User).first()

        booked = booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id, SeatClass.GALAXIUM)
        assert get_seats(db_session, flight_obj.flight_id, SeatClass.GALAXIUM) == 1

        result = booking.cancel_booking(db_session, booked.booking_id)

        assert result.status == "cancelled"
        assert result.seat_class == SeatClass.GALAXIUM
        assert get_seats(db_session, flight_obj.flight_id, SeatClass.GALAXIUM) == 2
        assert get_seats(db_session, flight_obj.flight_id, SeatClass.ECONOMY) == 5
        assert get_seats(db_session, flight_obj.flight_id, SeatClass.BUSINESS) == 3

    def test_cancel_booking_not_found(self, db_session):
        """Test cancelling non-existent booking."""
        result = booking.cancel_booking(db_session, 999)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "BOOKING_NOT_FOUND"

    def test_cancel_booking_already_cancelled(self, db_session, create_flight):
        """Test cancelling already cancelled booking."""
        db_session.add(User(name="Test User", email="test@example.com"))
        flight_obj = create_flight({SeatClass.ECONOMY: 5})

        user_obj = db_session.query(User).first()

        db_session.add(Booking(
            user_id=user_obj.user_id,
            flight_id=flight_obj.flight_id,
            seat_class=SeatClass.ECONOMY,
            status="cancelled",
            booking_time="2099-01-01T10:00:00Z"
        ))
        db_session.commit()

        booking_obj = db_session.query(Booking).first()
        result = booking.cancel_booking(db_session, booking_obj.booking_id)

        assert isinstance(result, ErrorResponse)
        assert result.error_code == "ALREADY_CANCELLED"

    def test_get_bookings_success(self, db_session, create_flight):
        """Test getting user bookings."""
        db_session.add(User(name="Test User", email="test@example.com"))
        flight_obj = create_flight({SeatClass.BUSINESS: 5})

        user_obj = db_session.query(User).first()

        db_session.add(Booking(
            user_id=user_obj.user_id,
            flight_id=flight_obj.flight_id,
            seat_class=SeatClass.BUSINESS,
            status="booked",
            booking_time="2099-01-01T10:00:00Z"
        ))
        db_session.commit()

        result = booking.get_bookings(db_session, user_obj.user_id)
        assert len(result) == 1
        assert result[0].status == "booked"
        assert result[0].seat_class == SeatClass.BUSINESS

    def test_get_bookings_empty(self, db_session):
        """Test getting bookings when user has none."""
        result = booking.get_bookings(db_session, 999)
        assert result == []
