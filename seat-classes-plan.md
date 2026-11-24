# Seat Classes Plan (Economy, Business, Galaxium)

## Top-Level Overview

**Goal:** Let travellers book a specific seat class (Economy, Business, Galaxium) on each flight. Each flight has its own price and seat inventory for each class.

**Confirmed design decisions**
- A new `FlightSeatClass` table holds one row per flight per class (`flight_id`, `seat_class`, `price`, `seats_available`). It replaces the flat `Flight.price` and `Flight.seats_available`, which are removed.
- `Booking` gets a `seat_class` column. Booking decrements the chosen class's inventory. Cancelling restores the seat to the booking's class.
- `POST /book` and the MCP `book_flight` tool **require** `seat_class`. There is no default.
- No DB migration. `seed()` clears and recreates all data on every startup ([`seed.py`](booking_system_backend/seed.py:6)). `Base.metadata.create_all` only creates missing tables, so a stale `booking.db` file must be deleted once.
- The scope is full-stack: backend (model, schemas, services, REST, MCP, seed, tests) and frontend (types, API client, flight card, booking modal, booking card).
- Seed pricing uses roughly 1x / 2x / 4x multipliers of the current flight price for Economy / Business / Galaxium. Seat counts are split per class from the current `seats_available`. Business and Galaxium get fewer seats.

**Proposed API shape** (details are set during implementation)
- `FlightOut` gains `seat_classes: list[{seat_class, price, seats_available}]`. The flat `price` and `seats_available` fields are removed.
- `BookingRequest` and `BookingOut` gain `seat_class`.
- `seat_class` is a shared enum with the values `economy`, `business` and `galaxium`.
- Existing error pattern is reused: `ErrorResponse` with `error_code`. A class that is sold out or not offered on a flight returns `NO_SEATS_AVAILABLE`. REST rejects an invalid enum value through Pydantic validation (422). The MCP tool does the same through its typed parameter.

**Key risk:** Removing `Flight.price` and `Flight.seats_available` breaks every consumer: schemas, `book_flight`, `cancel_booking`, seed, test fixtures, `FlightCard`, `BookingModal`, `BookingCard` and the `FlightFilters` price filter. Sub-tasks are ordered to keep each step reviewable.

---

## Sub-Tasks

### 1. Backend data model and schemas
**Intent:** Introduce the seat-class concept in the persistence and API contract layers.

**Expected Outcomes**
- `SeatClass` enum exists with Economy, Business and Galaxium.
- `FlightSeatClass` model exists with a relationship from `Flight`.
- `Booking` has a `seat_class` column.
- `Flight` no longer has `price` or `seats_available`.
- Pydantic schemas expose the new shape.

**Todo List**
1. Add the `SeatClass` enum (a shared location, e.g. `models.py` or a small module imported by `schemas.py`).
2. Add the `FlightSeatClass` model with a unique constraint on (`flight_id`, `seat_class`) and a relationship to `Flight`.
3. Remove `price` and `seats_available` from `Flight`.
4. Add `seat_class` to `Booking`.
5. Add a `SeatClassOut` schema. Update `FlightOut` to carry `seat_classes`. Add `seat_class` to `BookingRequest` and `BookingOut`.

**Relevant Context**
- [`models.py`](booking_system_backend/models.py) (`Flight` L12, `Booking` L22)
- [`schemas.py`](booking_system_backend/schemas.py) (`FlightOut` L5, `BookingRequest` L18, `BookingOut` L24)

**Status:** [x] done

**Implementation notes (context for Sub-Task 2 and later)**
- `SeatClass` lives in [`models.py`](booking_system_backend/models.py) as `class SeatClass(str, enum.Enum)` with `ECONOMY='economy'`, `BUSINESS='business'`, `GALAXIUM='galaxium'`. `schemas.py` imports it from `models`.
- New `FlightSeatClass` model (table `flight_seat_classes`) in `models.py`: columns `id`, `flight_id` (FK), `seat_class` (SQLAlchemy `Enum(SeatClass)` storing values), `price`, `seats_available`. It has `UniqueConstraint('flight_id', 'seat_class')` and `flight = relationship('Flight', back_populates='seat_classes')`.
- `Flight.seat_classes` is a relationship (list of `FlightSeatClass`). `Flight.price` and `Flight.seats_available` are removed.
- `Booking.seat_class` is a new non-null column, using the same `SeatClass` enum.
- `models.py` has a small helper `_seat_class_column()` that builds the enum column type, so both tables share the same definition.
- Schemas in [`schemas.py`](booking_system_backend/schemas.py):
  - `SeatClassOut(seat_class: SeatClass, price: int, seats_available: int)` with `from_attributes`.
  - `FlightOut` now has `seat_classes: List[SeatClassOut]`. It has no `price` or `seats_available`.
  - `BookingRequest.seat_class: SeatClass` is required, with no default.
  - `BookingOut.seat_class: SeatClass`.
- Because `SeatClass` is a `str` enum, `.value` gives `'economy'` etc. Query a class row with `FlightSeatClass.flight_id == flight_id, FlightSeatClass.seat_class == seat_class`.
- Known inconsistencies, to be fixed in later sub-tasks: `services/flight.py`, `services/booking.py`, `server.py`, `seed.py` and the tests still use `Flight.price`/`seats_available` and do not pass `seat_class`.
- Verification: `import models, schemas` succeeds with `booking_system_backend/.venv`. There is no `python` on PATH, so use `.venv/bin/python`.

---

### 2. Backend services (flight listing, booking, cancellation)
**Intent:** Make business logic operate on per-class inventory.

**Expected Outcomes**
- `list_flights` returns each flight with its per-class price and availability.
- `book_flight` takes `seat_class`, validates that the class exists on the flight and has seats, and decrements only that class.
- `cancel_booking` restores the seat to the booking's class.
- Existing error codes and the `Success | ErrorResponse` return pattern are preserved.

**Todo List**
1. Update `list_flights` to build `FlightOut` including `seat_classes`.
2. Update `book_flight(db, user_id, name, flight_id, seat_class)`. Replace the `seats_available` check and decrement with the class-row check and decrement. Persist `seat_class` on the booking.
3. Update `cancel_booking` to increment the matching class row.
4. Make sure `BookingOut` includes `seat_class` in `book_flight`, `cancel_booking` and `get_bookings`.

**Relevant Context**
- [`services/flight.py`](booking_system_backend/services/flight.py)
- [`services/booking.py`](booking_system_backend/services/booking.py) (checks around L18-24, decrement L44, restore L74-77)

**Status:** [x] done

**Implementation notes (context for Sub-Task 3 and later)**
- [`services/flight.py`](booking_system_backend/services/flight.py) needed no code change. `FlightOut.model_validate(f)` already serialises the `Flight.seat_classes` relationship, so `list_flights` returns per-class `price` and `seats_available`. Class order is whatever the DB returns, with no explicit sort.
- New signature in [`services/booking.py`](booking_system_backend/services/booking.py): `book_flight(db, user_id, name, flight_id, seat_class: SeatClass) -> BookingOut | ErrorResponse`. `seat_class` is required and is the 5th positional parameter. Callers (`server.py` MCP tool and REST endpoint) must pass a `SeatClass` enum member. `BookingRequest.seat_class` already is one. `SeatClass` is imported from `models`.
- Check order in `book_flight`: flight exists (`FLIGHT_NOT_FOUND`), then class row exists with seats (`NO_SEATS_AVAILABLE`), then user (`USER_NOT_FOUND`/`NAME_MISMATCH`). A class that is not offered on the flight and a sold-out class both return `NO_SEATS_AVAILABLE`. The details message names the class (`seat_class.value`).
- `cancel_booking` increments the `FlightSeatClass` row that matches `booking.flight_id` and `booking.seat_class`. If the row is missing it skips the restore silently, as the old code did when the flight was missing.
- `get_bookings` and the other `BookingOut` paths needed no change, since `BookingOut.seat_class` is read from the `Booking` column.
- Error codes and the `Success | ErrorResponse` pattern are unchanged.
- Verified with `.venv/bin/python`: the services modules import cleanly. An in-memory SQLite smoke test covered list, book, sold-out class, class not offered, cancel restore and `get_bookings`. This is not a pytest test. The existing tests still fail until Sub-Task 4.
- Still inconsistent until later sub-tasks: `server.py` (calls `book_flight` without `seat_class`), `seed.py` (uses `Flight.price`/`seats_available`) and the tests.

---

### 3. Backend API surface (REST and MCP) and seed data
**Intent:** Expose the feature through both interfaces and provide realistic demo data.

**Expected Outcomes**
- `POST /book` requires `seat_class`.
- MCP `book_flight` takes `seat_class`, and its docstring describes the classes.
- `GET /flights` and MCP `list_flights` return per-class data.
- Seed creates 3 class rows for each of the 10 flights, with 1x / 2x / 4x pricing and a per-class seat split.
- Seeded bookings have a random valid `seat_class`.

**Todo List**
1. Update `book_flight_endpoint` to pass `request.seat_class`, and update its docstring.
2. Update the MCP `book_flight` signature and docstring. Update the `list_flights` docstrings (REST and MCP).
3. Update `seed()` to create `FlightSeatClass` rows. Clear that table too, before `Flight`, to respect the foreign key.
4. Assign a random `seat_class` to seeded bookings.
5. Delete the stale local `booking.db`, or note that it must be deleted once. Check [`README.md`](README.md) and the backend docs for API descriptions to update.

**Relevant Context**
- [`server.py`](booking_system_backend/server.py) (MCP tools L19-97, REST routes L139-166)
- [`seed.py`](booking_system_backend/seed.py) (flights L30-41, bookings L44-56)

**Status:** [x] done

**Implementation notes (context for Sub-Task 4 and later)**
- [`server.py`](booking_system_backend/server.py): REST `book_flight_endpoint` passes `request.seat_class` as the 5th argument to `booking.book_flight`. MCP `book_flight(user_id, name, flight_id, seat_class: SeatClass)` takes the enum (JSON schema: required, `enum: [economy, business, galaxium]`). Docstrings for REST/MCP `list_flights`, `book_flight`, `cancel_booking` now describe per-class data. `SeatClass` is imported from `models` in `server.py`.
- [`seed.py`](booking_system_backend/seed.py): clears `Booking`, `User`, `FlightSeatClass`, then `Flight`. Each of the 10 flights gets 3 `FlightSeatClass` rows (economy = old price, business = 2x, galaxium = 4x). Seats (economy, business, galaxium), flights 1 to 10 in order: (3,1,1), (1,1,1), (4,2,1), (1,1,0), (1,0,0), (2,1,1), (3,2,1), (1,1,0), (1,1,1), (1,0,0). Each flight's total equals its old `seats_available`. Flights 4, 5, 8 and 10 have sold-out higher classes (0 seats), because the original totals were too small (1 to 2 seats). Flight 1 (Earth to Mars) has 3 economy, 1 business, 1 galaxium. Seeded bookings get a random `seat_class`. Seeded bookings do NOT adjust class inventory, as before.
- Class order in `GET /flights` is DB order, which was observed as business, economy, galaxium (not economy first). Tests and the frontend should not rely on order. Look up classes by `seat_class`.
- Error behaviour verified over REST: invalid or missing `seat_class` gives 422. A sold-out class returns HTTP 200 with an `ErrorResponse` body (`error_code` `NO_SEATS_AVAILABLE`). This matches the existing pattern, where `/book` returns errors in a 200 body.
- README: [`booking_system_backend/README.md`](booking_system_backend/README.md) API tables and examples were updated to show `seat_class`. [`booking_system_frontend/README.md`](booking_system_frontend/README.md) only lists `POST /book - Book a flight`, so it was left unchanged.
- The stale `booking_system_backend/booking.db` was deleted (it is gitignored). A smoke test then regenerated it, so the file now exists again with the new schema.
- Verified with `.venv/bin/python` (run with `PYTHONPATH=.` from `booking_system_backend`): `import server` works, and the app lifespan seeds successfully. Via FastAPI `TestClient`: `GET /flights` returns 10 flights with 3 classes each. `POST /book` with `galaxium` decrements only that class. A second galaxium booking returns `NO_SEATS_AVAILABLE`. A bogus or missing `seat_class` returns 422. The MCP `book_flight` input schema requires `seat_class`. Tests were not run or touched, and they still fail until Sub-Task 4.
- Note for tests: the `tests/` conftest uses its own DB or fixtures. Check whether it overrides `get_db` or patches `SessionLocal` before relying on seed data. It likely does not use `seed()`.

---

### 4. Backend tests
**Intent:** Keep the suite green and cover the new behaviour.

**Expected Outcomes**
- Fixtures and existing tests are adapted to the per-class model.
- New tests cover class-specific booking, sold-out class, missing class on a flight, class-specific cancel restore, and an invalid class value over REST.

**Todo List**
1. Update `sample_flight_data` and `sample_booking_data` in `conftest.py`. Add a helper or fixture that creates a flight with its class rows.
2. Update the `TestFlightService`, `TestBookingService`, `TestFlightsEndpoint`, `TestBookEndpoint` and `TestCancelEndpoint` tests for the new shape.
3. Add tests for:
   - booking decrements only the chosen class
   - sold-out Galaxium while Economy is still available
   - cancel restores the correct class
   - an invalid `seat_class` returns 422
4. Run `pytest` in `booking_system_backend` and confirm everything passes.

**Relevant Context**
- [`tests/conftest.py`](booking_system_backend/tests/conftest.py)
- [`tests/test_services.py`](booking_system_backend/tests/test_services.py)
- [`tests/test_rest.py`](booking_system_backend/tests/test_rest.py)

**Status:** [x] done

**Implementation notes (context for Sub-Task 5 and later)**
- Result: `booking_system_backend/.venv/bin/python -m pytest` (run from `booking_system_backend`) gives **40 passed** (29 before: 16 in `test_services.py`, 13 in `test_rest.py`; +11 new). The only warnings are existing Pydantic class-based `config` and `datetime.utcnow` deprecations.
- [`tests/conftest.py`](booking_system_backend/tests/conftest.py): `sample_flight_data` no longer has `price`/`seats_available`. `sample_booking_data` gained `"seat_class": "economy"`. New `create_flight` factory fixture: `create_flight({SeatClass.ECONOMY: 5, ...})` builds a flight with only the listed classes (omitted classes are "not offered"). With no argument it creates all 3 classes with 5 seats each. Prices are 1,000,000 / 2,000,000 / 4,000,000 (economy / business / galaxium). The tests use the same in-memory DB fixtures as before and do not call `seed()`.
- `test_services.py` and `test_rest.py` each have a small `get_seats(db_session, flight_id, seat_class)` helper that reads a class row's inventory.
- New tests, in both files unless noted: booking decrements only the chosen class, sold-out Galaxium while Economy stays bookable, class not offered on the flight (`NO_SEATS_AVAILABLE`, no booking created), and cancel restores the correct class. Other new tests: `list_flights` includes per-class data (services), `GET /flights` returns `seat_classes` with no flat `price`/`seats_available` (REST), invalid `seat_class` returns 422 and missing `seat_class` returns 422 (REST only).
- Contract facts confirmed by the tests, relevant to the frontend:
  - `GET /flights` items have `seat_classes: [{seat_class, price, seats_available}]`, with no top-level `price` or `seats_available`. Class order is not guaranteed, so the frontend should look classes up by `seat_class` or sort them itself.
  - `POST /book` body is `{user_id, name, flight_id, seat_class}`. `seat_class` is one of `"economy" | "business" | "galaxium"`. The response (and `/bookings/{user_id}`, `/cancel/{id}`) includes `seat_class`.
  - A sold-out or non-offered class returns HTTP 200 with `{success: false, error_code: "NO_SEATS_AVAILABLE", ...}`. The frontend must check the response body, not the HTTP status. An invalid or missing `seat_class` returns HTTP 422 (FastAPI validation error body).
- Seed data for manual frontend checks: see Sub-Task 3 notes. Flights 4, 5, 8 and 10 have sold-out higher classes, and flights 5 and 10 have no business seats either, so they are good cases for disabled class options.
- Not changed: `tests/` has no MCP tool tests, and none were added (out of scope for this sub-task).

---

### 5. Frontend types and API client
**Intent:** Align the TypeScript contract with the new backend.

**Expected Outcomes**
- Types reflect `SeatClass`, per-class flight data, and `seat_class` on bookings and booking requests.
- `bookFlight` sends `seat_class`.

**Todo List**
1. Add a `SeatClass` union type (`'economy' | 'business' | 'galaxium'`) and a `FlightSeatClass` interface in `types/index.ts`.
2. Update `Flight` (remove `price` and `seats_available`, add `seat_classes`), `Booking` and `BookingRequest`.
3. Revisit `FlightFilters.minPrice` and `maxPrice`, and any code that uses them. Decide whether they apply to the lowest class price.
4. Check that `api.ts` needs no change beyond the types.
5. Add small helpers in `utils/formatters.ts` if needed: a display label per class, and a lowest-price lookup.

**Relevant Context**
- [`src/types/index.ts`](booking_system_frontend/src/types/index.ts)
- [`src/services/api.ts`](booking_system_frontend/src/services/api.ts)
- [`src/utils/formatters.ts`](booking_system_frontend/src/utils/formatters.ts)

**Status:** [x] done

**Implementation notes (context for Sub-Task 6)**
- [`types/index.ts`](booking_system_frontend/src/types/index.ts): added `SeatClass = 'economy' | 'business' | 'galaxium'` and `FlightSeatClass { seat_class; price; seats_available }`. `Flight` lost `price`/`seats_available` and has `seat_classes: FlightSeatClass[]`. `Booking.seat_class: SeatClass` and `BookingRequest.seat_class: SeatClass` (both required).
- [`services/api.ts`](booking_system_frontend/src/services/api.ts): no change needed. `bookFlight(data: BookingRequest)` posts the whole object, so `seat_class` is sent once the caller supplies it. Callers must check `isErrorResponse` on the 200 body (`NO_SEATS_AVAILABLE`). A 422 is rejected by the interceptor with FastAPI's validation body, not an `ErrorResponse` shape.
- `FlightFilters.minPrice`/`maxPrice`: grep shows they are only declared in `types/index.ts` and used nowhere (no filter UI or code). Left unchanged. If a price filter is added later, apply it to `getLowestPrice(flight)`.
- New helpers in [`utils/formatters.ts`](booking_system_frontend/src/utils/formatters.ts) (they import types from `../types`):
  - `SEAT_CLASS_LABELS: Record<SeatClass, string>` (`Economy`, `Business`, `Galaxium`). Key order is the display order. Use `Object.keys` or a fixed array to render classes in that order, since the API order is not guaranteed.
  - `getSeatClassLabel(seatClass: SeatClass): string`
  - `getSeatClass(flight: Flight, seatClass: SeatClass): FlightSeatClass | undefined` (undefined = class not offered)
  - `getLowestPrice(flight: Flight): number | undefined`
- Verification: `npx tsc --noEmit -p tsconfig.app.json` from `booking_system_frontend` reports 8 errors, all in the Sub-Task 6 files:
  - [`BookingCard.tsx`](booking_system_frontend/src/components/bookings/BookingCard.tsx): L97 `flight.price`.
  - [`BookingModal.tsx`](booking_system_frontend/src/components/bookings/BookingModal.tsx): L32 `bookFlight` call lacks `seat_class`. L131 `flight.price`.
  - [`FlightCard.tsx`](booking_system_frontend/src/components/flights/FlightCard.tsx): L13 and L14 `seats_available`. L77 `price`. L86 `seats_available`.
- `Flights.tsx` and `MyBookings.tsx` produce no type errors. They still need a check for runtime behaviour in Sub-Task 6.

---

### 6. Frontend UI (flight card, booking modal, booking card)
**Intent:** Let users see class options and choose one, and show the class on their bookings.

**Expected Outcomes**
- `FlightCard` shows per-class price and availability. It keeps the existing low-stock and sold-out styling. "Book Now" is disabled only if all classes are sold out.
- `BookingModal` has a class selector. Sold-out classes are disabled. The total price follows the selected class, and `seat_class` is sent to the API.
- `BookingCard` shows the booked class and the price for that class.
- `Flights.tsx` and `MyBookings.tsx` work with the new data shape. The flight list reloads after booking, as it does now.

**Todo List**
1. Update `FlightCard` to render the three classes, using Tailwind tokens from [`tailwind.config.js`](booking_system_frontend/tailwind.config.js) for class accents.
2. Add class selection state to `BookingModal`, and pass the selected class to `bookFlight`.
3. Update `BookingCard` for the class label and the class price.
4. Fix remaining usages of `flight.price` and `flight.seats_available`. Confirm with grep and `npm run build` (TypeScript check).
5. Run `npm run lint`.
6. Manual smoke test: book Economy, Business and Galaxium. Cancel one. Verify the counts.

**Relevant Context**
- [`FlightCard.tsx`](booking_system_frontend/src/components/flights/FlightCard.tsx)
- [`BookingModal.tsx`](booking_system_frontend/src/components/bookings/BookingModal.tsx)
- [`BookingCard.tsx`](booking_system_frontend/src/components/bookings/BookingCard.tsx)
- [`Flights.tsx`](booking_system_frontend/src/pages/Flights.tsx)
- [`MyBookings.tsx`](booking_system_frontend/src/pages/MyBookings.tsx)
- Note: [`UserIdentification.tsx`](booking_system_frontend/src/components/user/UserIdentification.tsx) has uncommitted changes in git. It is unrelated to this task, so leave it alone.

**Status:** [x] done

**Implementation notes**
- [`FlightCard.tsx`](booking_system_frontend/src/components/flights/FlightCard.tsx): one row per offered class (fixed order from `SEAT_CLASS_LABELS`, looked up with `getSeatClass`) with label, price and seats. Per-class styling: 0 seats is red `text-red-500` "Sold Out", 1 to 2 seats is orange `text-solar-orange`, otherwise muted. "Book Now" is disabled and reads "Sold Out" only when every offered class has 0 seats. The old `DollarSign` and `Users` icons are removed (unused).
- [`BookingModal.tsx`](booking_system_frontend/src/components/bookings/BookingModal.tsx): new "Seat Class" radio-style list of buttons (`role="radiogroup"`, Tailwind `cosmic-purple` accent). Sold-out classes are disabled. State is `chosenClass`. The effective `selectedClass` is derived: the user's choice if still bookable, otherwise the first available class in economy, business, galaxium order. So there is no effect and no reset race when the flight changes. The state is cleared in a `handleClose` wrapper (used by the Cancel button, the modal X and after success). Total price follows the selected class. `seat_class` is sent to `bookFlight`. `NO_SEATS_AVAILABLE` goes through the existing `isErrorResponse` toast path. "Confirm Booking" is disabled when no class is bookable.
- [`BookingCard.tsx`](booking_system_frontend/src/components/bookings/BookingCard.tsx): shows a "Class" row (`getSeatClassLabel`) and the price of that booked class (`getSeatClass(flight, booking.seat_class)?.price`, `—` if missing). The no-flight fallback also shows the class.
- `Flights.tsx` and `MyBookings.tsx`: no change needed. They only pass `Flight`/`Booking` objects and reload via the existing `onSuccess`/`loadData`.
- Verification: `npx tsc --noEmit -p tsconfig.app.json` is clean. `npm run build` passes. `grep` finds no `flight.price` or `flight.seats_available` left in `src`.
- Lint (`npm run lint`): 9 errors and 1 warning, and none are new. Before this sub-task the only lint-relevant change in a touched file is `BookingModal.tsx:74` `catch (error: any)`, which is the original code (was L46), moved down by the new lines. The rest are in files not edited here: `UserIdentification.tsx`, `useUser.tsx`, `Flights.tsx`, `MyBookings.tsx` (2 errors and 1 warning), `api.ts`, `formatters.ts` (2 unused `error`).
- Smoke test (API level, fresh backend with `uvicorn server:app` on a spare port): flight 1 went from business 1, economy 3, galaxium 1 to business 0, economy 2, galaxium 0 after booking one of each. A second galaxium booking returned `NO_SEATS_AVAILABLE` in a 200 body. Cancelling the business booking restored business to 1. The browser UI was not clicked through (no browser automation), so the visual check of the three components is still manual.
- Environment note: a `server.py` process (PID 43956) was already listening on port 8080 with old code (no `seat_classes`). Restart it before checking the UI, because the frontend defaults to `http://localhost:8080`. Also, `TestClient`/server startup reseeds `booking.db`, so seed counts reset each time.

---

## Open Items for Implementation
- Exact seed seat splits per class (propose in sub-task 3, review with the user).
- Whether the price filter (if it is used in the UI) should use the lowest class price (sub-task 5).
