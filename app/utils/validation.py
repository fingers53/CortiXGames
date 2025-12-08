import math
from fastapi import HTTPException


def enforce_range(value: float, minimum: float, maximum: float, label: str):
    if value is None or not math.isfinite(value) or value < minimum or value > maximum:
        raise HTTPException(
            status_code=422,
            detail=f"{label} must be between {minimum} and {maximum}",
        )
