"""Spike indicator data model — enums and Spike frozen dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MoveMethod(str, Enum):
    NET = "NET"
    EXCURSION = "EXCURSION"
    RANGE = "RANGE"


class Statistic(str, Enum):
    MEAN = "MEAN"
    MEDIAN = "MEDIAN"
    ZSCORE = "ZSCORE"


class VolumeMode(str, Enum):
    AUTO = "AUTO"
    ALWAYS = "ALWAYS"
    NEVER = "NEVER"
    PRICE_AND_VOLUME = "PRICE_AND_VOLUME"
    PRICE_ONLY = "PRICE_ONLY"


@dataclass(frozen=True)
class Spike:
    direction: int
    magnitude: float
    price_at_fire: float
    start_ts: int
    end_ts: int
    volume_ratio: float | None
    start_bar_index: int
    end_bar_index: int
    move_method: MoveMethod
    statistic: Statistic
