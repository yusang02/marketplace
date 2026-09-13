from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.errors import AppError
from app.database import get_db
from app.helpers import assert_owner, get_current_user, get_listing_or_404

router = APIRouter(prefix="/listings", tags=["listings"])

# --- Endpoints ---
@router.post("", response_model=schemas.ListingOut)
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

@router.get("", response_model=list[schemas.ListingOut])
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

@router.get("/{id}", response_model=schemas.ListingOut)
def read_listing(
    id: int,
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get one listing by id. 404 if missing."""
    return get_listing_or_404(db, id)

@router.patch("/{id}", response_model=schemas.ListingOut)
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

@router.delete("/{id}")
def delete_listing(   
    id: int,
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a listing. Owner only. 409 if it has non-final orders."""
    listing = get_listing_or_404(db, id)
    assert_owner(listing, user)

    active_order = (
        db.query(models.Order)
        .filter(models.Order.listing_id == listing.id)
        .filter(models.Order.status.in_(models.ACTIVE_STATUSES))
        .first()
    )
    if active_order is not None:
        raise AppError(409, "LISTING_HAS_ACTIVE_ORDERS", "Listing has orders that are not final")

    db.delete(listing)
    db.commit()