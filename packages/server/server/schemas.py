"""Shared Pydantic models used across multiple route modules."""

from typing import Any

from pydantic import BaseModel


class IndicatorInstance(BaseModel):
    id: str
    type: str
    params: dict[str, Any]
