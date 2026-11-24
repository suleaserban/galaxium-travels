# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Commands
- Two independent apps: `booking_system_backend/` (FastAPI + SQLAlchemy/SQLite + FastMCP, :8080) and `booking_system_frontend/` (React + Vite, :5173). Run commands from inside each directory.
- Backend: use the local venv and flat imports (`from models import ...`). Single test: `.venv/bin/python -m pytest tests/test_services.py::TestBookingService::test_book_flight_success`
- Frontend: no test runner. Check with `npm run lint`, `npx tsc --noEmit -p tsconfig.app.json` and `npm run build`.

## Gotchas
- `seed()` runs on every server startup and **wipes and recreates all data**, so importing or running `server.py` reseeds `booking.db`. There are no migrations: after a schema change, delete `booking.db` (`create_all` won't alter existing tables).
- Errors are **returned, not raised**: services return `ErrorResponse` (with `error_code`, e.g. `NO_SEATS_AVAILABLE`) and REST answers HTTP 200. Only Pydantic validation failures give 422. The frontend must check bodies with `isErrorResponse()` (`src/services/api.ts`). MCP tools in `server.py` re-raise `ErrorResponse` as `Exception`.
- Seat classes: price and inventory live per flight per class in `FlightSeatClass`. `Flight` has no `price` or `seats_available`. `seat_class` is required on `POST /book` and MCP `book_flight`. `GET /flights` class order is not guaranteed, so look classes up by name (`getSeatClass`, `getLowestPrice`, `SEAT_CLASS_LABELS` in `src/utils/formatters.ts`).
- Prices are plain integers shown as-is by `formatCurrency` (no division by 100).

Mode-specific rules are in `.bob/rules-agent/`, `.bob/rules-plan/` and `.bob/rules-ask/`. The agent rules hold the test fixtures and the frontend conventions.
