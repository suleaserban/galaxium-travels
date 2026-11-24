import enum

from sqlalchemy import Column, Integer, String, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class SeatClass(str, enum.Enum):
    ECONOMY = 'economy'
    BUSINESS = 'business'
    GALAXIUM = 'galaxium'


def _seat_class_column():
    # Store the enum values ('economy', ...) rather than the member names.
    return Enum(SeatClass, values_callable=lambda e: [m.value for m in e])


class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)

class Flight(Base):
    __tablename__ = 'flights'
    flight_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    departure_time = Column(String, nullable=False)
    arrival_time = Column(String, nullable=False)
    seat_classes = relationship('FlightSeatClass', back_populates='flight')

class FlightSeatClass(Base):
    __tablename__ = 'flight_seat_classes'
    __table_args__ = (UniqueConstraint('flight_id', 'seat_class'),)
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    flight_id = Column(Integer, ForeignKey('flights.flight_id'), nullable=False)
    seat_class = Column(_seat_class_column(), nullable=False)
    price = Column(Integer, nullable=False)
    seats_available = Column(Integer, nullable=False)
    flight = relationship('Flight', back_populates='seat_classes')

class Booking(Base):
    __tablename__ = 'bookings'
    booking_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    flight_id = Column(Integer, ForeignKey('flights.flight_id'), nullable=False)
    seat_class = Column(_seat_class_column(), nullable=False)
    status = Column(String, nullable=False)
    booking_time = Column(String, nullable=False) 