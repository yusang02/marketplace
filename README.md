# Marketplace

![tests](https://github.com/yusang02/marketplace/actions/workflows/tests.yml/badge.svg)

A small marketplace for game accounts and in-game items. Sellers post listings, buyers
place orders, and orders move through a fixed lifecycle. There is no login. Every
request identifies its caller with an `X-User-Id` header.

**Stack:** Python 3.10+ (developed on 3.14, CI runs 3.12), FastAPI, SQLAlchemy 2.0,
SQLite, pytest. Frontend is Vue 3 with Vite.

## Running it

The API and the frontend run in two terminals.

**API**

```bash
python -m venv .venv
source .venv/Scripts/activate      # macOS and Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Serves `http://localhost:8000`, with interactive docs at `/docs`. The SQLite file is
created on first run, so a fresh checkout needs no setup step.

**Tests.** Run these from the project root, not from `tests/`.

```bash
python -m pytest
python -m pytest --cov=app --cov-report=term-missing
```

**Frontend.** Start the API first.

```bash
cd frontend
npm install
npm run dev
```

Serves `http://localhost:5173`.

## API

Every endpoint needs `X-User-Id`. A missing or blank value returns 401.

| Method | Path | Behaviour |
| --- | --- | --- |
| POST | `/listings` | Create a listing owned by the caller. |
| GET | `/listings` | List everything still in stock. Optional `?game=`. |
| GET | `/listings/{id}` | Fetch one listing. |
| PATCH | `/listings/{id}` | Update title, price or quantity. Owner only. |
| DELETE | `/listings/{id}` | Delete. Owner only. 409 if any order is still open. |
| POST | `/orders` | Place an order. Creates it as `PENDING` and takes the stock. |
| GET | `/orders` | Orders where the caller is buyer or seller. Optional `?role=buyer\|seller`. |
| POST | `/orders/{id}/pay` | `PENDING` to `PAID`. Buyer only. |
| POST | `/orders/{id}/deliver` | `PAID` to `DELIVERED`. Seller only. |
| POST | `/orders/{id}/cancel` | `PENDING` or `PAID` to `CANCELLED`. Buyer or seller. Returns the stock. |

Validation: `title` is trimmed, non-empty and at most 100 characters. `game` is
non-empty. `price` is above 0 with at most 2 decimal places. `quantity` is an integer of
1 or more.

Failures share one shape:

```json
{ "error": { "code": "INSUFFICIENT_STOCK", "message": "Not enough stock" } }
```

Codes: `UNAUTHORIZED`, `FORBIDDEN`, `LISTING_NOT_FOUND`, `ORDER_NOT_FOUND`,
`SELF_PURCHASE`, `INSUFFICIENT_STOCK`, `INVALID_TRANSITION`,
`LISTING_HAS_ACTIVE_ORDERS`, `VALIDATION_ERROR`.

## Design notes

**Schema.** Two tables, `listings` and `orders`. Money is stored as an integer count of
cents and divided only when the response is built, which keeps rounding out of the
database. An order copies `seller_id`, `unit_price_cents` and `listing_title` from the
listing at the moment it is placed, so a paid order still shows the agreed price after
the seller edits the listing, and it stays readable after the listing is gone. There is
no users table, so `seller_id` is a plain string with no foreign key.

**Status machine.** `OrderStatus` is an enum and the legal moves live in one dictionary,
`ALLOWED_TRANSITIONS`, rather than being spread across the three endpoints. Each one
calls `assert_transition`, which looks the move up and raises 409 `INVALID_TRANSITION`
if it is not listed. Who may act is a separate check, so delivering a `PENDING` order
and paying for someone else's order fail for different reasons.

**Overselling.** The check and the decrement are a single statement, a conditional
`UPDATE` that subtracts the quantity only `WHERE quantity >= n`. Reading the stock,
deciding in Python and writing it back would leave a gap between the read and the write
for another request to slip into. Here the database tests the condition and applies the
change together, under the lock it already takes for the update, so the second request
to reach the last unit matches no row, comes back with a `rowcount` of 0 and gets a 409.
A test fires two orders from two threads and asserts the results are exactly
`[200, 409]`. Cancelling adds the quantity back the same way.

**Errors.** One envelope for everything. `AppError` carries a status, a code and a
message, and a handler turns it into the JSON above. A second handler reshapes
Pydantic's validation errors into the same envelope, so a client never parses two
formats and no stack trace reaches it.

**Tests.** 40 tests at 98% coverage. The uncovered lines are the database session
factory, which the tests replace with their own. They are grouped by domain rule rather
than by file and all go through `TestClient`, so one call exercises the header auth, the
validation, the status machine, the database work and the serialisation together. Each
test gets its own SQLite file rather than `:memory:`, which would give the two
concurrency threads separate copies of the data. The frontend is a single Vue component
that refetches both lists after every action, so the screen shows what the database
holds. It hides buttons the current user cannot use, but the API enforces that itself.

## Decisions

Things the brief left open, decided here rather than asked about.

- CORS is open to any origin because the API and the dev server sit on different ports
  locally. A deployed version would list the frontend origin instead.
- Prices are shown in ringgit. The API returns a plain number, so the currency is a
  frontend assumption.
- `GET /listings` hides anything sold out, as specified, so a listing disappears when
  its last unit sells and returns if that order is cancelled.
- Sorting happens in the browser over the rows already fetched, which is correct only
  because the whole list is fetched at once.
- `game` is free text, so the frontend suggests values it has already seen instead of
  offering a fixed list.

## With more time

- Stop deleting listings outright and mark them with a `deleted_at` timestamp. The row
  would stay, so the foreign key from `orders` stays valid and history stays intact.
  SQLite does not enforce foreign keys by default, which is why deleting works today.
  Postgres would reject it.
- Record each status change in an `order_events` table, with who made it and when. An
  order currently only knows when it was created, so there is no way to tell when it
  was paid or delivered.
- Add a users table and real authentication. Identity is a bare string today, so
  `owner_id` and `buyer_id` accept anything and nothing checks that the account exists.
- Move sorting and pagination to the server, since sorting one page in the browser
  would order that page rather than the whole list.

## Stretch

**OpenAPI docs.** Generated at `/docs`, and checked against the real responses so the
documented shape matches what clients receive.

**Deploying on AWS.** On Lambda behind API Gateway the app itself would run mostly
unchanged with an adapter like Mangum. The part that needs thought is the stock check.
With Aurora the SQL stays exactly as it is, since the conditional update and the
rowcount check are plain SQL. But Aurora enforces foreign keys, so deleting a listing
that still has orders would fail, which is why the soft delete listed above would stop
being optional. DynamoDB has no `UPDATE ... WHERE`, so the same check would be written
as a condition on the write, and it fails with an error rather than a rowcount of zero.
Orders and stock would also be separate items there, so both writes would need to go
together to avoid taking stock without creating the order. The idea doesn't change. Let
the database check and change in one step instead of reading first.