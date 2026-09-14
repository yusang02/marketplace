from app.database import Base
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum
from datetime import datetime

# --- Listing ---

class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str]
    title: Mapped[str]
    game: Mapped[str]
    price_cents: Mapped[int] # Store price in cents to avoid floating point issues
    quantity: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

# --- Order ---

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

ALLOWED_TRANSITIONS = {
    OrderStatus.PENDING: (OrderStatus.PAID, OrderStatus.CANCELLED),
    OrderStatus.PAID: (OrderStatus.DELIVERED, OrderStatus.CANCELLED),
    OrderStatus.DELIVERED: (),
    OrderStatus.CANCELLED: (),
}

ACTIVE_STATUSES = (OrderStatus.PENDING, OrderStatus.PAID)

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    buyer_id: Mapped[str] = mapped_column(index=True)
    # Snapshot: the listing row can be deleted later, but an order must stay
    seller_id: Mapped[str] = mapped_column(index=True)
    quantity: Mapped[int]
    unit_price_cents: Mapped[int]   # snapshot: listing price may change later
    status: Mapped[OrderStatus]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())