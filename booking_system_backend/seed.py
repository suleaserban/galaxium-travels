from models import Base, User, Flight, FlightSeatClass, Booking, SeatClass
from db import engine, SessionLocal
from datetime import datetime, timedelta
import random

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Clear existing data
    db.query(Booking).delete()
    db.query(User).delete()
    db.query(FlightSeatClass).delete()
    db.query(Flight).delete()
    db.commit()
    # Add demo users
    users = [
        User(name="Alice", email="alice@example.com"),
        User(name="Bob", email="bob@example.com"),
        User(name="Charlie", email="charlie@galaxium.com"),
        User(name="Diana", email="diana@moonmail.com"),
        User(name="Eve", email="eve@marsmail.com"),
        User(name="Frank", email="frank@venusmail.com"),
        User(name="Grace", email="grace@jupiter.com"),
        User(name="Heidi", email="heidi@europa.com"),
        User(name="Ivan", email="ivan@asteroidbelt.com"),
        User(name="Judy", email="judy@pluto.com"),
    ]
    db.add_all(users)
    db.commit()
    # Add demo flights: (flight, economy price, (economy, business, galaxium) seats).
    # Business = 2x and Galaxium = 4x the economy price. Seats per flight keep the original
    # total; higher classes get fewer seats (a class may be sold out on very small flights).
    flight_specs = [
        (Flight(origin="Earth", destination="Mars", departure_time="2099-01-01T09:00:00Z", arrival_time="2099-01-01T17:00:00Z"), 1000000, (3, 1, 1)),
        (Flight(origin="Earth", destination="Moon", departure_time="2099-01-02T10:00:00Z", arrival_time="2099-01-02T14:00:00Z"), 500000, (1, 1, 1)),
        (Flight(origin="Mars", destination="Earth", departure_time="2099-01-03T12:00:00Z", arrival_time="2099-01-03T20:00:00Z"), 950000, (4, 2, 1)),
        (Flight(origin="Venus", destination="Earth", departure_time="2099-01-04T08:00:00Z", arrival_time="2099-01-04T18:00:00Z"), 1200000, (1, 1, 0)),
        (Flight(origin="Jupiter", destination="Europa", departure_time="2099-01-05T15:00:00Z", arrival_time="2099-01-05T19:00:00Z"), 2000000, (1, 0, 0)),
        (Flight(origin="Earth", destination="Venus", departure_time="2099-01-06T07:00:00Z", arrival_time="2099-01-06T15:00:00Z"), 1100000, (2, 1, 1)),
        (Flight(origin="Moon", destination="Mars", departure_time="2099-01-07T11:00:00Z", arrival_time="2099-01-07T19:00:00Z"), 800000, (3, 2, 1)),
        (Flight(origin="Mars", destination="Jupiter", departure_time="2099-01-08T13:00:00Z", arrival_time="2099-01-08T23:00:00Z"), 2500000, (1, 1, 0)),
        (Flight(origin="Europa", destination="Earth", departure_time="2099-01-09T09:00:00Z", arrival_time="2099-01-09T21:00:00Z"), 3000000, (1, 1, 1)),
        (Flight(origin="Earth", destination="Pluto", departure_time="2099-01-10T06:00:00Z", arrival_time="2099-01-11T06:00:00Z"), 5000000, (1, 0, 0)),
    ]
    multipliers = {SeatClass.ECONOMY: 1, SeatClass.BUSINESS: 2, SeatClass.GALAXIUM: 4}
    for flight, base_price, seats in flight_specs:
        flight.seat_classes = [
            FlightSeatClass(seat_class=seat_class, price=base_price * multipliers[seat_class], seats_available=count)
            for seat_class, count in zip(multipliers, seats)
        ]
    db.add_all([spec[0] for spec in flight_specs])
    db.commit()
    # Add demo bookings
    user_ids = [user.user_id for user in db.query(User).all()]
    flight_ids = [flight.flight_id for flight in db.query(Flight).all()]
    statuses = ["booked", "cancelled", "completed"]
    bookings = []
    now = datetime.utcnow()
    for i in range(20):
        user_id = random.choice(user_ids)
        flight_id = random.choice(flight_ids)
        status = random.choice(statuses)
        booking_time = (now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))).isoformat() + "Z"
        seat_class = random.choice(list(SeatClass))
        bookings.append(Booking(user_id=user_id, flight_id=flight_id, seat_class=seat_class, status=status, booking_time=booking_time))
    db.add_all(bookings)
    db.commit()
    db.close()
    print("Database seeded with elaborate demo data!")

if __name__ == "__main__":
    seed() 