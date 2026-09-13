from app.database import Base
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum

class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str]
    title: Mapped[str]
    game: Mapped[str]
    price_cents: Mapped[int] # Store price in cents to avoid floating point issues
    quantity: Mapped[int]

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
    unit_price_cents: Mapped[int]
    status: Mapped[OrderStatus]