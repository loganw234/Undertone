"""The injector: adds known pulses to a stream, and says exactly what it added.

A schedule is a sequence of truth records (`spec.constants.RECORDS["truth"]`):
`index`, `pulse_id`, `amplitude_num`, `amplitude_den`. One record means: the
pulse of that id, scaled by amplitude_num / amplitude_den, is added to EVERY
channel, its first sample at stream index `index`. Sample j of the pulse lands
at stream index `index + j`, and what is added there is

    delta[j] = pulse[j] * amplitude_num / amplitude_den,
               rounded to the nearest integer, a tie to the even one

worked in integers (`scaled_pulse`). The output sample is the input sample
plus delta[j]. If that sum is outside the profile's sample range the run is
REFUSED at that frame: a sample is never clipped.

The truth goes around the stream, never through it: `inject` returns the
stream and the truth as two separate things, and the stream is plain tuples of
plain ints and nothing else.

Two outcomes only: the answer, or a `Refusal` by name. A refusal part-way
through a stream comes after some frames were handed out: a refused run is no
run, and its truth describes nothing.
"""
from spec import constants as C
from model import records, stream
from model.refusal import Refusal


def pulse(pulse_id):
    """The samples of the pulse the definition gives this id, or a refusal by name.

    The definition maps a pulse's name to its id, one to one (`PULSE_IDS`),
    and its name to its samples (`PULSES`). It is read at each call.
    """
    names = [name for name in sorted(C.PULSE_IDS) if C.PULSE_IDS[name] == pulse_id]
    if type(pulse_id) is not int or len(names) != 1:
        raise Refusal("PULSE_UNKNOWN", "pulse_id %r names no declared pulse" % (pulse_id,))
    return C.PULSES[names[0]]


def _round_half_even(num, den):
    """num / den rounded to the nearest integer, a tie to the even one. den > 0."""
    q, r = divmod(num, den)             # floor: num = q * den + r, 0 <= r < den
    if 2 * r > den or (2 * r == den and q & 1):
        q += 1
    return q


def scaled_pulse(pulse_id, amplitude_num, amplitude_den):
    """The samples one truth record adds, in order: a tuple of ints."""
    record = records.check("truth", {"index": 0, "pulse_id": pulse_id,
                                     "amplitude_num": amplitude_num, "amplitude_den": amplitude_den})
    return _deltas(record)


def _deltas(record):
    return tuple(_round_half_even(p * record["amplitude_num"], record["amplitude_den"])
                 for p in pulse(record["pulse_id"]))


def _check_length(length):
    if type(length) is not int or length < 0:
        raise Refusal("STREAM_LENGTH", "a stream's length is an int of at least 0, not %r" % (length,))


def schedule(schedule_records, length):
    """The schedule, checked, as a tuple of copies of its records.

    `length` is how many frames the stream has. Each record in turn is checked
    for, in this order:
      its fields (`model.records.check`)                            RECORD_FIELD
      a pulse_id that names a declared pulse                        PULSE_UNKNOWN
      starting at or after the end of the record before it          INJECT_OVERLAP
      ending at or before `length`                                  INJECT_PAST_END
    So two injections never share a sample, and a schedule out of order is
    refused under the same name as one that overlaps: it breaks the same rule.
    """
    _check_length(length)
    out, free_from = [], 0
    for record in schedule_records:
        record = dict(records.check("truth", record))
        last = record["index"] + len(_deltas(record))
        if record["index"] < free_from:
            raise Refusal("INJECT_OVERLAP", "the injection at %d starts before %d, where the one before it ends"
                          % (record["index"], free_from))
        if last > length:
            raise Refusal("INJECT_PAST_END", "the injection at %d ends at %d, past a stream of %d frames"
                          % (record["index"], last, length))
        out.append(record)
        free_from = last
    return tuple(out)


def inject(profile_name, frames, schedule_records, length):
    """Returns (stream, truth).

    `stream` is an iterator of frames: the input's frames with the schedule's
    pulses added. `truth` is the schedule as `schedule` returns it. Everything
    about the schedule is checked here, before a frame is read. While the
    stream runs, each input frame is checked (CHANNELS, SAMPLE_RANGE), each
    sum is checked (INJECT_RANGE), and a stream that is not exactly `length`
    frames long is refused (STREAM_LENGTH): at frame `length` if it is longer,
    at its end if it is shorter.
    """
    prof = stream.profile(profile_name)
    truth = schedule(schedule_records, length)
    delta_at = {}
    for record in truth:
        for j, d in enumerate(_deltas(record)):
            delta_at[record["index"] + j] = d
    return _run(prof, frames, delta_at, length), tuple(dict(record) for record in truth)


def _run(prof, frames, delta_at, length):
    lo, hi = prof["sample_min"], prof["sample_max"]
    n = 0
    for frame in frames:
        if n == length:
            raise Refusal("STREAM_LENGTH", "the stream runs past its declared %d frames" % length)
        stream.check_frame(prof, frame)
        d = delta_at.get(n, 0)
        out = tuple([v + d for v in frame])
        for v in out:
            if not lo <= v <= hi:
                raise Refusal("INJECT_RANGE", "frame %d: a sample plus %d is %d, outside %d..%d"
                              % (n, d, v, lo, hi))
        yield out
        n += 1
    if n != length:
        raise Refusal("STREAM_LENGTH", "the stream ended after %d frames; %d were declared" % (n, length))
