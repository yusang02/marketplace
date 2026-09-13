from fastapi import Header
from sqlalchemy.orm import Session

from app import models
from app.errors import AppError


def get_current_user(x_user_id: str | None = Header(default=None)) -> str:
    """Read the caller from X-User-Id. 401 if missing or blank."""  
    if not x_user_id or not x_user_id.strip():
        raise AppError(401, "UNAUTHORIZED", "X-User-Id header is required")
    return x_user_id.strip()    

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

def get_order_or_404(db: Session, id: int) -> models.Order:
    """Fetch an order or raise 404."""
    order = db.get(models.Order, id)
    if order is None:
        raise AppError(404, "ORDER_NOT_FOUND", "Order not found")
    return order

def assert_transition(order: models.Order, to_status: models.OrderStatus) -> None:
    """Raise 409 unless the order's current status allows moving to to_status."""
    if to_status not in models.ALLOWED_TRANSITIONS[order.status]:
        raise AppError(
            409,
            "INVALID_TRANSITION",
            f"Cannot go from {order.status.value} to {to_status.value}",
        )