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
