from fastapi import APIRouter, Depends
from sqlalchemy import update, or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.errors import AppError
from app.helpers import get_current_user, get_listing_or_404, get_order_or_404, assert_transition, apply_transition

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
        seller_id=listing.owner_id,
        listing_title=listing.title,
        quantity=data.quantity,
        unit_price_cents=listing.price_cents,
        status=models.OrderStatus.PENDING,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

@router.get("", response_model=list[schemas.OrderOut])
def read_orders(
    role: str | None = None,
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Orders where the caller is the buyer or the seller. Optional ?role= filter."""
    query = db.query(models.Order)

    if role == "buyer":
        query = query.filter(models.Order.buyer_id == user)
    elif role == "seller":
        query = query.filter(models.Order.seller_id == user)
    else:
        query = query.filter(
            or_(models.Order.buyer_id == user, models.Order.seller_id == user)
        )
    return query.all()

@router.post("/{id}/pay", response_model=schemas.OrderOut)
def pay_order(
    id: int,
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PENDING -> PAID. Buyer only."""
    order = get_order_or_404(db, id)
    if order.buyer_id != user:
        raise AppError(403, "FORBIDDEN", "Only the buyer can pay")

    assert_transition(order, models.OrderStatus.PAID)
    apply_transition(db, order, models.OrderStatus.PAID)

    db.commit()
    db.refresh(order)
    return order

@router.post("/{id}/deliver", response_model=schemas.OrderOut)
def deliver_order(
    id: int,
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PAID -> DELIVERED. Seller only."""
    order = get_order_or_404(db, id)
    if order.seller_id != user:
        raise AppError(403, "FORBIDDEN", "Only the seller can deliver")

    assert_transition(order, models.OrderStatus.DELIVERED)
    apply_transition(db, order, models.OrderStatus.DELIVERED)

    db.commit()
    db.refresh(order)
    return order

@router.post("/{id}/cancel", response_model=schemas.OrderOut)
def cancel_order(
    id: int,
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PENDING or PAID -> CANCELLED. Buyer or seller. Restores listing stock."""
    order = get_order_or_404(db, id)

    if user not in (order.buyer_id, order.seller_id):
        raise AppError(403, "FORBIDDEN", "Only the buyer or seller can cancel")

    assert_transition(order, models.OrderStatus.CANCELLED)
    apply_transition(db, order, models.OrderStatus.CANCELLED)
    
    # Restore stock
    db.execute(
        update(models.Listing)
        .where(models.Listing.id == order.listing_id)
        .values(quantity=models.Listing.quantity + order.quantity)
    )

    db.commit()
    db.refresh(order)
    return order