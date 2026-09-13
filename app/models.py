from app.database import Base
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum
from datetime import datetime

class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str]
    title: Mapped[str]
    game: Mapped[str]
    price_cents: Mapped[int] # Store price in cents to avoid floating point issues
    quantity: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    buyer_id: Mapped[str]
    quantity: Mapped[int]
    unit_price_cents: Mapped[int]   # snapshot: listing price may change later
    status: Mapped[OrderStatus]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    listing: Mapped["Listing"] = relationship()