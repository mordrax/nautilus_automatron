import pytest

from indicators.spike import SpikeIndicator
from indicators.spike.model import Spike, MoveMethod, Statistic, VolumeMode


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
