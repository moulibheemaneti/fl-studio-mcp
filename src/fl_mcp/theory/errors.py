"""Everything that can go wrong in music theory, each with its own name.

Every error here is a ``ValueError``: the caller asked for something that
doesn't exist in music (an "H" note, a "sadness" scale) or doesn't fit on a
MIDI keyboard. The messages are written to be read by a person *or* by Claude,
so they always say what would have been accepted.
"""


class MusicTheoryError(ValueError):
    """The request made no musical sense. Catch this to catch every error below."""


class UnknownNoteError(MusicTheoryError):
    """A note name couldn't be read, e.g. ``"H"`` or ``"C#b"``."""


class UnknownScaleError(MusicTheoryError):
    """A scale name isn't in the catalogue, e.g. ``"sad"``."""


class OutOfMidiRangeError(MusicTheoryError):
    """A note would fall outside MIDI's 0-127 range."""
