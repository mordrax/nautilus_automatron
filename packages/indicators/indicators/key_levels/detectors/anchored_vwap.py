"""AnchoredVwapDetector — VWAP-anchored snapshot levels (lifecycle-tracked).

A continuously-moving VWAP doesn't fit a static horizontal level cleanly. This
detector instead emits *snapshot* levels: each confirmed swing point becomes
an anchor, and at anchor time we record the current running VWAP value as a
horizontal level. The level lives until:

- the running VWAP drifts beyond `vwap_drift_atr * ATR` from the snapshot
  price (a replacement level is emitted at the new VWAP value)
- a sustained close beyond the level for `break_consecutive_bars` bars (break)
- aged-out (no touch for `max_idle_bars` bars)

This trades the running-line semantics for a discrete sequence of horizontals
that behave like the rest of the lifecycle-tracked detectors.

`bounce_count` increments on swing-pivot touches; `touch_count` on bar-level
overlaps with the tolerance band around the centroid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import AnchoredVwapMeta, KeyLevel
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import SwingDetector


@dataclass
class _AnchorState:
    """Running VWAP state from a single anchor point."""

    anchor_ts: int
    anchor_type: Literal["swing_high", "swing_low"]
    cum_pv: float
    cum_vol: float
    vwap: float


@dataclass
class _TrackedLevel:
    id: int
    side: Literal["high", "low"]
    centroid: float
    start_ts: int
    end_ts: int | None
    bounce_count: int
    touch_count: int
    last_touch_ts: int
    bars_through: int
    anchor_ts: int
    anchor_type: Literal["swing_high", "swing_low", "gap", "volume_spike"]
    cumulative_volume: float
    atr_at_emit: float


class AnchoredVwapDetector:

    def __init__(
        self,
        swing_period: int = 5,
        max_anchors: int = 5,
        atr_period: int = 14,
        vwap_drift_atr: float = 1.0,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        max_idle_bars: int = 200,
        strength_decay_k: float = 3.0,
        min_touches: int = 1,
    ) -> None:
        self._swing_period = swing_period
        self._max_anchors = max_anchors
        self._vwap_drift_atr = vwap_drift_atr
        self._break_atr_multiple = break_atr_multiple
        self._break_consecutive_bars = break_consecutive_bars
        self._max_idle_bars = max_idle_bars
        self._strength_decay_k = strength_decay_k
        self._min_touches = min_touches

        self._atr = StreamingAtr(period=atr_period)
        self._swing_detector = SwingDetector(period=swing_period)

        self._bar_index: int = 0
        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None
        self._anchors: list[_AnchorState] = []
        # Active level id per anchor (parallel to self._anchors).
        self._active_id_per_anchor: list[int | None] = []

        self._tracked: list[_TrackedLevel] = []
        self._next_id: int = 0

    @property
    def name(self) -> str:
        return "anchored_vwap"

    @property
    def warmup_bars(self) -> int:
        return self._swing_detector.warmup_bars

    # ------------------------------------------------------------------ update

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        volume = float(bar.volume)
        ts = bar.ts_event

        if self._last_bar_ts is not None and self._bar_interval_ns is None:
            delta = ts - self._last_bar_ts
            if delta > 0:
                self._bar_interval_ns = delta
        self._last_bar_ts = ts

        self._atr.update(high, low, close)
        typical_price = (high + low + close) / 3.0

        swing = self._swing_detector.update(
            high=high, low=low, bar_index=self._bar_index, ts=ts,
        )
        self._bar_index += 1

        if swing is not None:
            anchor_type: Literal["swing_high", "swing_low"] = (
                "swing_high" if swing.side == "high" else "swing_low"
            )
            self._anchors.append(_AnchorState(
                anchor_ts=swing.ts,
                anchor_type=anchor_type,
                cum_pv=0.0,
                cum_vol=0.0,
                vwap=typical_price,
            ))
            self._active_id_per_anchor.append(None)
            # Trim oldest anchor; finalize its active level (if any).
            if len(self._anchors) > self._max_anchors:
                self._anchors.pop(0)
                old_id = self._active_id_per_anchor.pop(0)
                if old_id is not None:
                    old_lvl = self._tracked[old_id]
                    if old_lvl.end_ts is None:
                        old_lvl.end_ts = ts

        # Update all active anchors with this bar.
        for anchor in self._anchors:
            anchor.cum_pv += typical_price * volume
            anchor.cum_vol += volume
            if anchor.cum_vol > 0:
                anchor.vwap = anchor.cum_pv / anchor.cum_vol

        if not self._atr.ready:
            return

        atr_value = self._atr.value
        tolerance = 0.25 * atr_value

        # Per-bar lifecycle on existing levels.
        for lvl in self._tracked:
            if lvl.end_ts is None:
                self._apply_bar_to_level(lvl, high, low, close, ts, tolerance)

        # Attach swing to closest active same-side level.
        if swing is not None:
            best: _TrackedLevel | None = None
            best_dist = tolerance
            for lvl in self._tracked:
                if lvl.end_ts is not None or lvl.side != swing.side:
                    continue
                dist = abs(swing.price - lvl.centroid)
                if dist <= best_dist:
                    best = lvl
                    best_dist = dist
            if best is not None:
                best.bounce_count += 1
                best.last_touch_ts = swing.ts

        # Emit fresh levels or replace drifted ones for each anchor.
        for i, anchor in enumerate(self._anchors):
            if anchor.cum_vol <= 0:
                continue
            self._emit_or_replace(i, anchor, close, ts, atr_value)

    def _emit_or_replace(
        self,
        anchor_idx: int,
        anchor: _AnchorState,
        close: float,
        ts: int,
        atr_value: float,
    ) -> None:
        existing_id = self._active_id_per_anchor[anchor_idx]
        if existing_id is not None:
            existing = self._tracked[existing_id]
            if existing.end_ts is None:
                drift = abs(existing.centroid - anchor.vwap)
                if drift <= self._vwap_drift_atr * atr_value:
                    return
                existing.end_ts = ts

        side: Literal["high", "low"] = "high" if anchor.vwap >= close else "low"
        new_idx = len(self._tracked)
        self._tracked.append(_TrackedLevel(
            id=self._next_id,
            side=side,
            centroid=anchor.vwap,
            start_ts=ts,
            end_ts=None,
            bounce_count=0,
            touch_count=0,
            last_touch_ts=ts,
            bars_through=0,
            anchor_ts=anchor.anchor_ts,
            anchor_type=anchor.anchor_type,
            cumulative_volume=anchor.cum_vol,
            atr_at_emit=atr_value,
        ))
        self._next_id += 1
        self._active_id_per_anchor[anchor_idx] = new_idx

    def _apply_bar_to_level(
        self,
        lvl: _TrackedLevel,
        high: float,
        low: float,
        close: float,
        ts: int,
        tolerance: float,
    ) -> None:
        atr_value = self._atr.value
        if lvl.side == "high":
            beyond = close > lvl.centroid + self._break_atr_multiple * atr_value
        else:
            beyond = close < lvl.centroid - self._break_atr_multiple * atr_value

        if beyond:
            lvl.bars_through += 1
        else:
            lvl.bars_through = 0

        if lvl.bars_through >= self._break_consecutive_bars:
            lvl.end_ts = ts
            return

        band_upper = lvl.centroid + tolerance
        band_lower = lvl.centroid - tolerance
        if low <= band_upper and high >= band_lower:
            lvl.touch_count += 1
            lvl.last_touch_ts = ts

        bar_interval = self._bar_interval_ns or 1
        idle_ns = self._max_idle_bars * bar_interval
        if ts - lvl.last_touch_ts > idle_ns:
            lvl.end_ts = lvl.last_touch_ts

    # ------------------------------------------------------------------ levels

    def levels(self) -> list[KeyLevel]:
        out: list[KeyLevel] = []
        for lvl in self._tracked:
            decay = math.exp(
                -(lvl.bounce_count - self._min_touches) / self._strength_decay_k
            )
            decay = max(0.0, min(1.0, decay))
            # Stronger with more accumulated volume — capped.
            vol_scale = min(1.0, lvl.cumulative_volume / 10_000.0)
            strength = max(0.0, min(1.0, vol_scale * decay))

            zone_half = 0.25 * lvl.atr_at_emit

            out.append(KeyLevel(
                price=lvl.centroid,
                strength=strength,
                start_ts=lvl.start_ts,
                end_ts=lvl.end_ts,
                source="anchored_vwap",
                bounce_count=lvl.bounce_count,
                zone_upper=lvl.centroid + zone_half,
                zone_lower=lvl.centroid - zone_half,
                meta=AnchoredVwapMeta(
                    anchor_ts=lvl.anchor_ts,
                    anchor_type=lvl.anchor_type,
                    cumulative_volume=lvl.cumulative_volume,
                    side=lvl.side,
                    touch_count=lvl.touch_count,
                ),
            ))
        return out

    def reset(self) -> None:
        self._atr.reset()
        self._swing_detector.reset()
        self._bar_index = 0
        self._last_bar_ts = None
        self._bar_interval_ns = None
        self._anchors.clear()
        self._active_id_per_anchor.clear()
        self._tracked.clear()
        self._next_id = 0
