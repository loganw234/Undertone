"""STAT: the test streams. They are scaffolding for the statistics, and scaffolding is tested too.

`stats.synth` is not the instrument's generator or injector. What is held here: a seed gives one
stream; nothing is clipped; a pulse lands where its truth index says and nowhere else.
"""
import numpy as np
import pytest

from spec import constants as C
from stats import synth
from stats.errors import StatRefusal


def refused(name, fn, *args, **kwargs):
    with pytest.raises(StatRefusal) as e:
        fn(*args, **kwargs)
    assert e.value.name == name


@pytest.mark.parametrize("profile_name", sorted(C.PROFILES))
def test_stat_one_seed_gives_one_stream_and_another_seed_another(profile_name):
    channels = C.PROFILES[profile_name]["channels"]
    a = synth.noise(profile_name, 5000, 300.0, 42)
    assert a.shape == (5000, channels) and a.dtype.kind == "i"
    assert np.array_equal(a, synth.noise(profile_name, 5000, 300.0, 42))
    assert not np.array_equal(a, synth.noise(profile_name, 5000, 300.0, 43))
    # a longer stream from the same seed begins with the shorter one
    assert np.array_equal(a, synth.noise(profile_name, 6000, 300.0, 42)[:5000])
    for c in range(channels):
        assert float(a[:, c].std()) == pytest.approx(300.0, rel=0.05)
        assert abs(float(a[:, c].mean())) < 5 * 300.0 / 5000 ** 0.5


def test_stat_noise_is_refused_not_clipped_when_it_leaves_the_range():
    # sigma 20,000 against a 16-bit range of +/-32,767: one sample in ten is outside.
    refused("SAMPLE_RANGE", synth.noise, "s16x1", 1000, 20_000.0, 1)
    # the same sigma fits 24 bits
    assert synth.noise("s24x3", 1000, 20_000.0, 1).shape == (1000, 3)
    refused("SIGMA", synth.noise, "s16x1", 10, 0.0, 1)
    refused("PROFILE_UNKNOWN", synth.noise, "s8x1", 10, 1.0, 1)
    refused("VALUE_TYPE", synth.noise, "s16x1", 10, 1.0, -1)
    refused("SHAPE", synth.noise, "s16x1", -1, 1.0, 1)


def test_stat_a_pulse_lands_at_its_truth_index_and_nowhere_else():
    quiet = np.zeros((20, 3), dtype=np.int32)
    pulse = [[1, 2, 3], [-4, -5, -6], [7, 0, 9]]          # a different row on each channel
    out = synth.inject(quiet, "s24x3", pulse, [2, 10])
    want = np.zeros((20, 3), dtype=np.int64)
    for j in (2, 10):
        for c in range(3):
            for k in range(3):
                want[j + k, c] = pulse[c][k]
    assert out.tolist() == want.tolist()
    assert not quiet.any(), "the stream handed in was changed"
    assert out.dtype == quiet.dtype


def test_stat_pulses_add_to_what_is_there_and_to_each_other():
    base = np.arange(10, dtype=np.int64).reshape(10, 1)
    # two pulses one frame apart overlap on frame 4: 3 + 10 + 20... worked: frames 3,4 get 10,20; frames 4,5 get 10,20
    out = synth.inject(base, "s16x1", [10, 20], [3, 4])
    assert out[:, 0].tolist() == [0, 1, 2, 13, 34, 25, 6, 7, 8, 9]


def test_stat_schedule_by_hand():
    assert synth.schedule(4, 64).tolist() == [0, 64, 128, 192]
    assert synth.schedule(3, 128, first=64).tolist() == [64, 192, 320]
    refused("SHAPE", synth.schedule, 0, 64)
    refused("SHAPE", synth.schedule, 3, 0)


def test_stat_an_injection_that_cannot_be_made_is_refused_by_name():
    quiet = np.zeros((10, 1), dtype=np.int32)
    # the last frame is 9: a 2-sample pulse fits at 8 and not at 9
    assert synth.inject(quiet, "s16x1", [1, 1], [8])[8:, 0].tolist() == [1, 1]
    refused("INDEX_RANGE", synth.inject, quiet, "s16x1", [1, 1], [9])
    refused("INDEX_RANGE", synth.inject, quiet, "s16x1", [1, 1], [-1])
    refused("INJECTIONS_OVERLAP", synth.inject, quiet, "s16x1", [1, 1], [3, 3])
    # one count past the top of the range is refused, not wrapped: 32767 fits, 32768 does not
    assert synth.inject(quiet, "s16x1", [32767], [0])[0, 0] == 32767
    refused("SAMPLE_RANGE", synth.inject, quiet, "s16x1", [32768], [0])
    refused("SAMPLE_RANGE", synth.inject, quiet, "s16x1", [-32769], [0])
    refused("SAMPLE_RANGE", synth.inject, quiet, "s16x1", [0.5], [0])
    refused("CHANNELS", synth.inject, quiet, "s16x1", [[1], [1]], [0])
    refused("CHANNELS", synth.inject, np.zeros((10, 2), dtype=np.int32), "s16x1", [1], [0])
    refused("CHANNELS", synth.inject, np.zeros((10, 1)), "s16x1", [1], [0])
    refused("SHAPE", synth.inject, quiet, "s16x1", [1], [0.0])
