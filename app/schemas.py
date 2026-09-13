from pydantic import BaseModel, Field, computed_field, field_validator
from decimal import Decimal

class ListingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    game: str = Field(min_length=1)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    quantity: int = Field(ge=1)

    @field_validator("title","game")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be empty")
        return value

class ListingOut(BaseModel):
    id: int
    owner_id: str
    title: str
    game: str
    price_cents: int = Field(exclude=True)   
    quantity: int

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def price(self) -> float:
        return self.price_cents / 100

class ListingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    quantity: int | None = Field(default=None, ge=1)

    @field_validator("title")
    @classmethod
    def validate_non_empty(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be empty")
        return value
