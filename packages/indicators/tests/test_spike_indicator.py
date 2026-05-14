import pytest

from indicators.spike import SpikeIndicator
from indicators.spike.model import Spike, MoveMethod, Statistic, VolumeMode
from tests.helpers.bar_factory import make_bar


def test_spike_dataclass_is_frozen_and_typed():
    s = Spike(
        direction=1,
        magnitude=2.5,
        price_at_fire=100.0,
        start_ts=1,
        end_ts=10,
        start_bar_index=0,
        end_bar_index=4,
        volume_ratio=1.7,
        move_method=MoveMethod.EXCURSION,
        statistic=Statistic.ZSCORE,
    )
    assert s.direction == 1
    assert s.volume_ratio == 1.7
    try:
        s.direction = -1  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("Spike must be frozen")


def test_volume_mode_runtime_states():
    assert VolumeMode.PRICE_AND_VOLUME in VolumeMode
    assert VolumeMode.PRICE_ONLY in VolumeMode
    assert VolumeMode.AUTO in VolumeMode


def test_constructs_with_defaults():
    ind = SpikeIndicator()
    assert ind.move_method is MoveMethod.EXCURSION
    assert ind.statistic is Statistic.ZSCORE
    assert ind.measurement_window == 5
    assert ind.baseline_window == 20
    assert ind.price_threshold == 2.5
    assert ind.volume_threshold == 2.0
    assert ind.cooldown_bars == 20
    assert ind.has_inputs is False
    assert ind.initialized is False
    assert ind.spike_count == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"measurement_window": 0},
        {"measurement_window": -1},
        {"baseline_window": 5, "measurement_window": 5},  # M must be > N
        {"price_threshold": -0.1},
        {"volume_threshold": -1.0},
        {"cooldown_bars": -1},
        {"max_spikes": -1},
    ],
)
def test_parameter_validation_rejects_invalid(kwargs):
    with pytest.raises((ValueError, Exception)):
        SpikeIndicator(**kwargs)


def _bars(closes, highs=None, lows=None, volumes=None, start_ns=1_000_000_000):
    highs = highs if highs is not None else [c + 0.5 for c in closes]
    lows = lows if lows is not None else [c - 0.5 for c in closes]
    volumes = volumes if volumes is not None else [100.0] * len(closes)
    out = []
    for i, c in enumerate(closes):
        out.append(
            make_bar(
                open_=c,
                high=highs[i],
                low=lows[i],
                close=c,
                volume=volumes[i],
                ts_ns=start_ns + i * 60_000_000_000,
            )
        )
    return out


def test_no_spike_on_flat_series():
    ind = SpikeIndicator(measurement_window=3, baseline_window=10)
    for bar in _bars([100.0] * 30):
        ind.handle_bar(bar)
    assert ind.spike_count == 0
    # Constant non-zero volume is NOT "usable" per spec (non-zero AND not all
    # identical), so AUTO latches to PRICE_ONLY.
    assert ind.volume_mode is VolumeMode.PRICE_ONLY


def test_up_spike_with_volume_fires():
    # Warmup has small price/volume noise so baseline sigma > 0 AND
    # AUTO latches to PRICE_AND_VOLUME (volumes vary, are non-zero).
    noise = [0.0, 0.05, -0.03, 0.02, -0.04, 0.01, 0.06, -0.02, 0.03, -0.05,
             0.04, 0.0, -0.01, 0.05, -0.03, 0.02, -0.04, 0.01, 0.06, -0.02,
             0.03, -0.05, 0.04, 0.0, -0.01]
    vol_noise = [0, 5, -3, 2, -4, 1, 6, -2, 3, -5,
                 4, 0, -1, 5, -3, 2, -4, 1, 6, -2,
                 3, -5, 4, 0, -1]
    warm_closes = [100.0 + n for n in noise]
    warm_vols = [100.0 + n for n in vol_noise]
    closes = warm_closes + [100.5, 101.0, 110.0]  # spike in last 3 bars
    volumes = warm_vols + [300.0, 350.0, 400.0]  # volume also abnormal
    ind = SpikeIndicator(
        move_method=MoveMethod.NET,
        statistic=Statistic.ZSCORE,
        measurement_window=3,
        baseline_window=20,
        price_threshold=2.0,
        volume_threshold=2.0,
    )
    for bar in _bars(closes, volumes=volumes):
        ind.handle_bar(bar)
    assert ind.spike_count >= 1
    assert ind.current_spike is not None
    assert ind.current_spike.direction == 1
    assert ind.volume_mode is VolumeMode.PRICE_AND_VOLUME


def test_price_passes_volume_blocks_no_fire():
    closes = [100.0] * 25 + [100.5, 101.0, 110.0]
    volumes = [100.0] * 28  # volume stays flat
    ind = SpikeIndicator(
        move_method=MoveMethod.NET,
        statistic=Statistic.ZSCORE,
        measurement_window=3,
        baseline_window=20,
        price_threshold=2.0,
        volume_threshold=2.0,
        require_volume=VolumeMode.ALWAYS,
    )
    for bar in _bars(closes, volumes=volumes):
        ind.handle_bar(bar)
    assert ind.spike_count == 0


def test_volume_absent_fires_on_price_alone():
    # Warmup has small price noise so baseline sigma > 0. Volumes all zero
    # so AUTO latches to PRICE_ONLY.
    noise = [0.0, 0.05, -0.03, 0.02, -0.04, 0.01, 0.06, -0.02, 0.03, -0.05,
             0.04, 0.0, -0.01, 0.05, -0.03, 0.02, -0.04, 0.01, 0.06, -0.02,
             0.03, -0.05, 0.04, 0.0, -0.01]
    warm_closes = [100.0 + n for n in noise]
    closes = warm_closes + [100.5, 101.0, 110.0]
    volumes = [0.0] * 28
    ind = SpikeIndicator(
        move_method=MoveMethod.NET,
        statistic=Statistic.ZSCORE,
        measurement_window=3,
        baseline_window=20,
        price_threshold=2.0,
    )
    for bar in _bars(closes, volumes=volumes):
        ind.handle_bar(bar)
    assert ind.volume_mode is VolumeMode.PRICE_ONLY
    assert ind.spike_count >= 1


def test_cooldown_suppresses_subsequent_fires():
    # Several large back-to-back moves: without cooldown all would fire.
    closes = [100.0] * 25 + [110.0, 120.0, 130.0, 140.0]
    ind = SpikeIndicator(
        move_method=MoveMethod.NET,
        statistic=Statistic.ZSCORE,
        measurement_window=3,
        baseline_window=20,
        price_threshold=1.0,
        cooldown_bars=10,
        require_volume=VolumeMode.NEVER,
    )
    for bar in _bars(closes):
        ind.handle_bar(bar)
    assert ind.spike_count == 1  # cooldown blocked the rest


def test_reset_clears_state():
    ind = SpikeIndicator(require_volume=VolumeMode.NEVER)
    for bar in _bars([100.0, 101.0] * 20):
        ind.handle_bar(bar)
    ind._reset()
    assert ind.spike_count == 0
    assert ind.volume_mode is None
    assert ind.has_inputs is False
    assert ind.initialized is False


@pytest.mark.parametrize("method", list(MoveMethod))
@pytest.mark.parametrize("stat", list(Statistic))
def test_warmup_no_fire_before_full_buffer(method, stat):
    ind = SpikeIndicator(
        move_method=method, statistic=stat,
        measurement_window=3, baseline_window=10,
        require_volume=VolumeMode.NEVER,
    )
    # Only N+M-1 bars → not enough
    for bar in _bars([100.0, 101.0] * 6):  # 12 bars, need 14 (M+N+1)
        ind.handle_bar(bar)
    assert ind.spike_count == 0


@pytest.mark.parametrize("method", list(MoveMethod))
@pytest.mark.parametrize("stat", list(Statistic))
def test_intra_window_round_trip_distinguishes_methods(method, stat):
    """A tall intra-window spike that round-trips to flat.

    Baseline has non-periodic small noise so the per-method baseline
    distribution has non-zero stdev (required for ZSCORE to fire).
    """
    # 22 non-periodic noise samples; period and magnitude chosen so no
    # baseline window itself triggers a fire.
    noise = [0.0, 0.05, -0.03, 0.02, -0.04, 0.01, 0.06, -0.02, 0.03, -0.05,
             0.04, 0.0, -0.01, 0.05, -0.03, 0.02, -0.04, 0.01, 0.06, -0.02,
             0.03, -0.05]
    baseline_closes = [100.0 + n for n in noise]
    closes = baseline_closes + [100.0, 100.0, 100.0]  # ends flat
    highs  = [c + 0.5 for c in baseline_closes] + [100.5, 120.0, 100.5]
    lows   = [c - 0.5 for c in baseline_closes] + [99.5, 99.5, 99.5]

    ind = SpikeIndicator(
        move_method=method,
        statistic=stat,
        measurement_window=3,
        baseline_window=20,
        price_threshold={
            Statistic.MEAN: 5.0,
            Statistic.MEDIAN: 5.0,
            Statistic.ZSCORE: 3.0,
        }[stat],
        require_volume=VolumeMode.NEVER,
    )
    for bar in _bars(closes, highs=highs, lows=lows):
        ind.handle_bar(bar)

    # NET sees ~0 move on the final flat bars → no fire under any statistic.
    # EXCURSION & RANGE see a ~20-magnitude move → fire under any statistic.
    if method is MoveMethod.NET:
        assert ind.spike_count == 0, f"NET should not fire under {stat}"
    else:
        assert ind.spike_count >= 1, f"{method} should fire under {stat}"
