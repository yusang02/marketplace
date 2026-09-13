from fastapi import Depends, FastAPI, Header
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.database import Base, engine, get_db
from app import models, schemas
from sqlalchemy.orm import Session

# --- App setup ---
Base.metadata.create_all(bind=engine)
app = FastAPI(title="Marketplace API")

# --- Error handling ---
class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message

@app.exception_handler(AppError)
def app_error_handler(request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )

@app.exception_handler(RequestValidationError)
def validation_error_handler(request, exc: RequestValidationError):
    """Convert Pydantic validation errors into the API's single error shape."""
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first["loc"][1:])
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": f"{field}: {first['msg']}",
            }
        },
    )

# --- Dependencies ---
def get_current_user(x_user_id: str | None = Header(default=None)) -> str:
    if not x_user_id or not x_user_id.strip():
        raise AppError(401, "UNAUTHORIZED", "X-User-Id header is required")
    return x_user_id.strip()    


# --- Endpoints ---
@app.post("/listings", response_model=schemas.ListingOut)
def create_listing(
    data: schemas.ListingCreate,
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a listing owned by the caller."""
    listing = models.Listing(
        owner_id=user,
        title=data.title,
        game=data.game,
        price_cents=int(data.price * 100),
        quantity=data.quantity,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing

@app.get("/listings", response_model=list[schemas.ListingOut])
def read_listings(
    game: str | None = None,
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List in-stock listings, optional ?game= filter."""
    query = db.query(models.Listing).filter(models.Listing.quantity > 0)
    if game:
        query = query.filter(models.Listing.game == game)
    return query.all()

@app.get("/listings/{id}", response_model=schemas.ListingOut)
def read_listing(
    id: int,
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get one listing by id. 404 if missing."""
    return get_listing_or_404(db, id)

@app.patch("/listings/{id}", response_model=schemas.ListingOut)
def update_listing(
    id: int,
    data: schemas.ListingUpdate,
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update title / price / quantity. Owner only."""
    listing = get_listing_or_404(db, id)
    assert_owner(listing, user)

    if data.title is not None:
        listing.title = data.title

    if data.price is not None:
        listing.price_cents = int(data.price * 100)

    if data.quantity is not None:
        listing.quantity = data.quantity

    db.commit()
    db.refresh(listing)
    return listing
""
@app.delete("/listings/{id}")
def delete_listing(   
    id: int,
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a listing. Owner only. 409 if it has non-final orders."""
    listing = get_listing_or_404(db, id)
    assert_owner(listing, user)

    # Need to come back here for non-final orders, so far just skipped
    db.delete(listing)
    db.commit()
    


# --- Helpers ---
def get_listing_or_404(db: Session, id: int) -> models.Listing:
    """Fetch a listing or raise 404."""
    listing = db.get(models.Listing, id)
    if listing is None:
        raise AppError(404, "LISTING_NOT_FOUND", "Listing not found")
    return listing

def assert_owner(listing: models.Listing, user: str) -> None:
    """Raise 403 unless the caller owns the listing."""
    if listing.owner_id != user:
        raise AppError(403, "FORBIDDEN", "You do not own this listing")