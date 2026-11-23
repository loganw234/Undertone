"""The stream interface: what a source hands a detector.

A stream is an iterable of frames. A frame is a tuple of Python ints, one per
channel, each inside the profile's signed sample range. The sample index is a
frame's position in the stream, counted from 0.

A profile is named, never assumed: row D1 of the design is not fixed, so the
same code must run under more than one sample format.
"""
from spec import constants as C
from model.refusal import Refusal


def profile(name):
    """The profile's facts, or a refusal by name."""
    if name not in C.PROFILES:
        raise Refusal("PROFILE_UNKNOWN", repr(name))
    return C.PROFILES[name]


def check_frame(prof, frame):
    """Return the frame unchanged, or refuse it by name.

    `prof` is what `profile()` returned. A bool is refused: it is an int in
    Python, and a True in a sample stream is a bug upstream.
    """
    if not isinstance(frame, tuple) or len(frame) != prof["channels"]:
        raise Refusal("CHANNELS", "frame %r, profile has %d channel(s)" % (frame, prof["channels"]))
    for v in frame:
        if type(v) is not int or not prof["sample_min"] <= v <= prof["sample_max"]:
            raise Refusal("SAMPLE_RANGE", "sample %r outside %d..%d"
                          % (v, prof["sample_min"], prof["sample_max"]))
    return frame
