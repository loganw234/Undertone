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
    """A copy of the profile's facts, or a refusal by name.

    Anything that is not the name of a declared profile is refused, whatever
    its type. The copy is the caller's: changing it changes nothing shared.
    """
    if type(name) is not str or name not in C.PROFILES:
        raise Refusal("PROFILE_UNKNOWN", repr(name))
    return dict(C.PROFILES[name])


def check_frame(prof, frame):
    """Return the frame unchanged, or refuse it by name.

    `prof` is what `profile()` returned. Every channel is checked. A bool is
    refused: it is an int in Python, and a True in a sample stream is a bug
    upstream.

    A frame is EXACTLY a tuple, and a sample exactly an int. An object of a
    subclass of either can carry more than its samples, and what a detector
    is handed must carry nothing else: so a subclass of tuple is refused as
    not a frame (CHANNELS), as a subclass of int is refused as not a sample.
    """
    if type(frame) is not tuple or len(frame) != prof["channels"]:
        raise Refusal("CHANNELS", "frame %r, profile has %d channel(s)" % (frame, prof["channels"]))
    for v in frame:
        if type(v) is not int or not prof["sample_min"] <= v <= prof["sample_max"]:
            raise Refusal("SAMPLE_RANGE", "sample %r outside %d..%d"
                          % (v, prof["sample_min"], prof["sample_max"]))
    return frame
