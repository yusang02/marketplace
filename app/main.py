from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.database import Base, engine
from app.errors import AppError
from app.routers import listings, orders

# --- App setup ---
Base.metadata.create_all(bind=engine)
app = FastAPI(title="Marketplace API")

# --- Error handling ---
@app.exception_handler(AppError)
def app_error_handler(request, exc: AppError):
    """Turn any AppError into the API's single error shape."""
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

# --- Routers ---
app.include_router(listings.router)
app.include_router(orders.router)