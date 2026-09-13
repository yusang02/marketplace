from fastapi import APIRouter, Depends
from sqlalchemy import update
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.errors import AppError
from app.helpers import get_current_user, get_listing_or_404

router = APIRouter(prefix="/orders", tags=["orders"])

# --- Endpoints ---
@router.post("", response_model=schemas.OrderOut)
def create_order(
    data: schemas.OrderCreate,
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Place an order"""
    listing = get_listing_or_404(db, data.listing_id)

    if listing.owner_id == user:
        raise AppError(400, "SELF_PURCHASE", "You cannot order your own listing")

    # Check and decrement in one statement so two buyers cannot both take the last unit.
    result = db.execute(
        update(models.Listing)
        .where(models.Listing.id == listing.id)
        .where(models.Listing.quantity >= data.quantity)
        .values(quantity=models.Listing.quantity - data.quantity)
    )

    if result.rowcount == 0:
        raise AppError(409, "INSUFFICIENT_STOCK", "Not enough stock")

    order = models.Order(
        listing_id=listing.id,
        buyer_id=user,
        quantity=data.quantity,
        unit_price_cents=listing.price_cents,
        status=models.OrderStatus.PENDING,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order