"""Routes for technical indicator data."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.routes.dependencies import _catalog
from server.schemas import IndicatorInstance
from server.store.indicators import (
    INDICATOR_TYPES,
    IndicatorResult,
    ParamValidationError,
    compute_indicator_instance,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ParamSchemaOut(BaseModel):
    name: str
    type: Literal["int", "float"]
    default: int | float
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    label: str | None = None


class IndicatorTypeOut(BaseModel):
    type: str
    label_template: str
    display: Literal["overlay", "panel"]
    outputs: list[str]
    params: list[ParamSchemaOut]


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class IndicatorInstancesBody(BaseModel):
    instances: list[IndicatorInstance]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/indicators")
def get_available_indicators() -> list[IndicatorTypeOut]:
    """Return all available indicator types with their parameter schemas."""
    result = []
    for ind_type in INDICATOR_TYPES.values():
        result.append(
            IndicatorTypeOut(
                type=ind_type.type,
                label_template=ind_type.label_template,
                display=ind_type.display,
                outputs=list(ind_type.outputs),
                params=[
                    ParamSchemaOut(
                        name=p.name,
                        type=p.type,
                        default=p.default,
                        min=p.min,
                        max=p.max,
                        step=p.step,
                        label=p.label,
                    )
                    for p in ind_type.params
                ],
            )
        )
    return result


@router.post("/bars/{bar_type:path}/indicators")
def compute_indicators_for_bar_type(
    bar_type: str,
    body: IndicatorInstancesBody,
    catalog: ParquetDataCatalog = Depends(_catalog),
) -> list[IndicatorResult]:
    """Compute indicators from catalog bars by bar type.

    Accepts a list of indicator instances (each with a UUID, type, and params).
    Returns a list of IndicatorResult, one per instance.

    Bar type identifies instrument + timeframe (e.g. XAUUSD.IBCFD-5-MINUTE-MID-EXTERNAL).
    Indicators are pure functions on bars — they don't need a run ID.
    """
    bars = catalog.bars(bar_types=[bar_type])
    if not bars:
        raise HTTPException(status_code=404, detail=f"No bar data for {bar_type}")

    results = []
    for instance in body.instances:
        try:
            results.append(
                compute_indicator_instance(
                    instance_id=instance.id,
                    type_name=instance.type,
                    params=instance.params,
                    bars=bars,
                )
            )
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown indicator type: {instance.type}",
            )
        except ParamValidationError as e:
            raise HTTPException(
                status_code=400,
                detail=str(e),
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error computing {instance.type}: {str(e)}",
            )

    return results
