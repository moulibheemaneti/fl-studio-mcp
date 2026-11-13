"""Scales: the ensembles that notes perform in.

A scale recipe (:class:`ScaleType`) is two lists that move together, one entry
per note:

- ``intervals``: how many **semitones** above the root each note sits, and
- ``letter_steps``: how many **letters** above the root each note is written.

The letter steps are what make the spelling right. D natural minor's sixth note
is 8 semitones and 5 letters above D. Five letters above D is B, and B lowered
to fit 8 semitones is Bb, so the scale gets Bb, never A#.

The plot of :func:`build_scale`:
    1. Read the root ("Bb") and find the recipe ("minor" -> natural_minor).
    2. Spell each note with the letter its step points to.
    3. Find each note's MIDI key, climbing from the root's octave.

Adding a scale means adding one :class:`ScaleType` to :data:`SCALE_TYPES`;
nothing else changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from fl_mcp.theory.errors import UnknownNoteError, UnknownScaleError
from fl_mcp.theory.notes import (
    LETTERS,
    LETTERS_PER_OCTAVE,
    SEMITONES_PER_OCTAVE,
    NoteName,
    check_midi_number,
    spell_with_letter,
)

#: The FL Studio octave a scale starts in unless asked otherwise (C5 = MIDI 60).
DEFAULT_OCTAVE = 5

#: Roots may carry at most one sharp or flat. That keeps every note of every
#: scale within a double sharp/flat (F# harmonic minor needs E#, B# needs C##).
MAX_ROOT_ACCIDENTAL = 1

#: Semitones of the major scale. Degree labels ("b3", "#4") compare against it.
_MAJOR_INTERVALS: tuple[int, ...] = (0, 2, 4, 5, 7, 9, 11)

#: Letter steps for any seven-note scale: one new letter per note.
_SEVEN_LETTERS: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6)


@dataclass(frozen=True, slots=True)
class ScaleType:
    """A recipe for a scale, independent of the note it starts on.

    Cast:
        name: Canonical name, e.g. ``"natural_minor"``.
        intervals: Semitones above the root for each note, starting at 0.
        letter_steps: Letters above the root for each note, starting at 0.
        summary: One factual line about what the scale is.
        aliases: Other names that mean the same scale, e.g. ``("minor", "aeolian")``.
    """

    name: str
    intervals: tuple[int, ...]
    letter_steps: tuple[int, ...]
    summary: str
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Check the recipe once, so every scale built from it is sound."""
        if len(self.intervals) != len(self.letter_steps):
            raise ValueError(
                f"{self.name}: intervals and letter_steps must have one entry per note"
            )
        if self.intervals[0] != 0 or self.letter_steps[0] != 0:
            raise ValueError(f"{self.name}: the first note must be the root (0, 0)")
        if (
            list(self.intervals) != sorted(set(self.intervals))
            or self.intervals[-1] >= SEMITONES_PER_OCTAVE
        ):
            raise ValueError(f"{self.name}: intervals must rise within one octave")
        if (
            list(self.letter_steps) != sorted(self.letter_steps)
            or self.letter_steps[-1] >= LETTERS_PER_OCTAVE
        ):
            raise ValueError(f"{self.name}: letter_steps must not go backwards or past one octave")

    @property
    def display_name(self) -> str:
        """The name as a person would say it: ``"natural minor"``."""
        return self.name.replace("_", " ")

    @property
    def degree_labels(self) -> tuple[str, ...]:
        """Each note's degree compared with the major scale: ``("1", "2", "b3", ...)``."""
        labels: list[str] = []  # one label per note, built in order
        for step, interval in zip(self.letter_steps, self.intervals, strict=True):
            offset = interval - _MAJOR_INTERVALS[step]  # semitones away from the major degree
            symbol = "#" if offset > 0 else "b"  # raised or lowered
            labels.append(symbol * abs(offset) + str(step + 1))
        return tuple(labels)


@dataclass(frozen=True, slots=True)
class Scale:
    """A scale built on a real root: one performance of a :class:`ScaleType`.

    Cast:
        root: The note the scale starts on, e.g. D.
        scale_type: The recipe that was followed.
        notes: Every note, correctly spelled, starting from the root.
        octave: The FL Studio octave of the root (C5 = MIDI 60).
        midi_numbers: Each note's MIDI key, rising from the root.
    """

    root: NoteName
    scale_type: ScaleType
    notes: tuple[NoteName, ...]
    octave: int
    midi_numbers: tuple[int, ...]

    @property
    def title(self) -> str:
        """The scale as a person would name it: ``"D natural minor"``."""
        return f"{self.root} {self.scale_type.display_name}"

    @property
    def degrees(self) -> tuple[str, ...]:
        """Degree labels for each note, e.g. ``("1", "2", "b3", ...)``."""
        return self.scale_type.degree_labels

    @property
    def intervals(self) -> tuple[int, ...]:
        """Semitones above the root for each note."""
        return self.scale_type.intervals


#: Every scale this project knows, in the order tools list them.
SCALE_TYPES: tuple[ScaleType, ...] = (
    ScaleType(
        "major", _MAJOR_INTERVALS, _SEVEN_LETTERS, "The major scale (Ionian mode).", ("ionian",)
    ),
    ScaleType(
        "natural_minor",
        (0, 2, 3, 5, 7, 8, 10),
        _SEVEN_LETTERS,
        "The natural minor scale (Aeolian mode).",
        ("minor", "aeolian"),
    ),
    ScaleType(
        "harmonic_minor", (0, 2, 3, 5, 7, 8, 11), _SEVEN_LETTERS, "Natural minor with a raised 7th."
    ),
    ScaleType(
        "melodic_minor",
        (0, 2, 3, 5, 7, 9, 11),
        _SEVEN_LETTERS,
        "Natural minor with a raised 6th and 7th (the ascending form).",
    ),
    ScaleType("dorian", (0, 2, 3, 5, 7, 9, 10), _SEVEN_LETTERS, "Minor with a raised 6th."),
    ScaleType("phrygian", (0, 1, 3, 5, 7, 8, 10), _SEVEN_LETTERS, "Minor with a flat 2nd."),
    ScaleType("lydian", (0, 2, 4, 6, 7, 9, 11), _SEVEN_LETTERS, "Major with a raised 4th."),
    ScaleType("mixolydian", (0, 2, 4, 5, 7, 9, 10), _SEVEN_LETTERS, "Major with a flat 7th."),
    ScaleType(
        "locrian", (0, 1, 3, 5, 6, 8, 10), _SEVEN_LETTERS, "Minor with a flat 2nd and flat 5th."
    ),
    ScaleType(
        "major_pentatonic",
        (0, 2, 4, 7, 9),
        (0, 1, 2, 4, 5),
        "Five notes of the major scale: 1 2 3 5 6.",
        ("pentatonic_major",),
    ),
    ScaleType(
        "minor_pentatonic",
        (0, 3, 5, 7, 10),
        (0, 2, 3, 4, 6),
        "Five notes of the natural minor scale: 1 b3 4 5 b7.",
        ("pentatonic_minor",),
    ),
    ScaleType(
        "blues",
        (0, 3, 5, 6, 7, 10),
        (0, 2, 3, 4, 4, 6),
        "Minor pentatonic plus a flat 5th, the 'blue note'.",
        ("minor_blues",),
    ),
)


def _normalise(name: str) -> str:
    """Make scale names comparable: lower case, words joined by underscores."""
    return "_".join(name.strip().lower().replace("-", " ").replace("_", " ").split())


def _index_by_name(scale_types: tuple[ScaleType, ...]) -> dict[str, ScaleType]:
    """Map every canonical name and alias to its scale, refusing duplicates."""
    index: dict[str, ScaleType] = {}  # normalised name -> scale type
    for scale_type in scale_types:
        for name in (scale_type.name, *scale_type.aliases):
            key = _normalise(name)  # the form lookups will use
            if key in index:
                raise ValueError(f"Scale name {name!r} is used twice")
            index[key] = scale_type
    return index


#: Lookup table built once at import: every accepted name -> its scale type.
_SCALE_TYPES_BY_NAME: dict[str, ScaleType] = _index_by_name(SCALE_TYPES)


def describe_scale_names() -> str:
    """List every supported scale with its aliases, for messages and tool descriptions."""
    entries = (
        f"{scale_type.name} (also: {', '.join(scale_type.aliases)})"
        if scale_type.aliases
        else scale_type.name
        for scale_type in SCALE_TYPES
    )
    return ", ".join(entries)


def find_scale_type(name: str) -> ScaleType:
    """Find a scale by its name or an alias; spaces, hyphens and case don't matter."""
    try:
        return _SCALE_TYPES_BY_NAME[_normalise(name)]
    except KeyError:
        raise UnknownScaleError(
            f"Unknown scale {name!r}. Supported scales: {describe_scale_names()}."
        ) from None


def _spell_degree(root: NoteName, letter_step: int, interval: int) -> NoteName:
    """Spell one note of a scale: the letter comes from the step, the pitch from the interval."""
    # The letter this note must use, counted up from the root's letter.
    letter = LETTERS[(root.letter_index + letter_step) % LETTERS_PER_OCTAVE]
    # The pitch this note must sound, counted up from the root's pitch.
    pitch_class = (root.pitch_class + interval) % SEMITONES_PER_OCTAVE
    return spell_with_letter(letter, pitch_class)


def build_scale(
    root: str | NoteName, scale: str | ScaleType, octave: int = DEFAULT_OCTAVE
) -> Scale:
    """Build a scale: read the root, follow the recipe, spell each note, find its keys.

    Args:
        root: The starting note, as text (``"Bb"``) or a :class:`NoteName`.
        scale: A scale name or alias (``"minor"``) or a :class:`ScaleType`.
        octave: The FL Studio octave of the root (C5 = MIDI 60).

    Raises:
        UnknownNoteError: The root can't be read or has more than one sharp/flat.
        UnknownScaleError: The scale name isn't in :data:`SCALE_TYPES`.
        OutOfMidiRangeError: Part of the scale would fall outside MIDI 0-127.
    """
    # Act 1: meet the root and the recipe.
    root_note = root if isinstance(root, NoteName) else NoteName.parse(root)
    if abs(root_note.accidental) > MAX_ROOT_ACCIDENTAL:
        raise UnknownNoteError(
            f"Root {root_note} has more than one sharp or flat. Use its simpler name, "
            "e.g. 'D' instead of 'C##'."
        )
    scale_type = scale if isinstance(scale, ScaleType) else find_scale_type(scale)

    # Act 2: spell every note with the letter its step points to.
    notes = tuple(
        _spell_degree(root_note, step, interval)
        for step, interval in zip(scale_type.letter_steps, scale_type.intervals, strict=True)
    )

    # Act 3: find each note's MIDI key, rising from the root.
    root_midi = root_note.midi_number(octave)  # also checks the root fits on the keyboard
    midi_numbers = tuple(root_midi + interval for interval in scale_type.intervals)
    check_midi_number(
        midi_numbers[-1],
        f"The top note of {root_note} {scale_type.display_name} in octave {octave}",
    )

    return Scale(
        root=root_note, scale_type=scale_type, notes=notes, octave=octave, midi_numbers=midi_numbers
    )
