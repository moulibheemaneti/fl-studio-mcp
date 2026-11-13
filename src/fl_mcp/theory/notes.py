"""Notes: the cast every scale, chord and melody is built from.

A note has two sides, like an actor and their role:

- its **name** ("B flat"): a letter plus an accidental, which tells a musician
  how to read it, and
- its **pitch**: a pitch class (0-11) or a MIDI number, which tells FL Studio
  which key to press.

The same pitch can have two names (A# and Bb), and music theory cares which one
you use: D minor contains Bb, never A#. So this module keeps the name and the
pitch together in one value, :class:`NoteName`, instead of passing bare
numbers around.

Octaves follow FL Studio's naming, where middle C (MIDI 60) is **C5**.
"""

from __future__ import annotations

from dataclasses import dataclass

from fl_mcp.theory.errors import OutOfMidiRangeError, UnknownNoteError

#: The seven note letters, in order. Spelling a scale walks along this list.
LETTERS: tuple[str, ...] = ("C", "D", "E", "F", "G", "A", "B")

#: Semitones above C for each letter when it has no sharp or flat.
NATURAL_PITCH_CLASSES: dict[str, int] = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

#: Semitones in one octave.
SEMITONES_PER_OCTAVE = 12

#: Letters in one octave.
LETTERS_PER_OCTAVE = len(LETTERS)

#: The most sharps or flats a note may carry: a double sharp (##) or double flat (bb).
MAX_ACCIDENTAL = 2

#: The lowest and highest MIDI note numbers.
MIDI_LOWEST, MIDI_HIGHEST = 0, 127

#: Symbols accepted when reading a note name, and how far each moves the pitch.
_ACCIDENTAL_SYMBOLS: dict[str, int] = {"#": 1, "♯": 1, "b": -1, "♭": -1}

#: One sentence on how to write a note, reused by every "can't read that" message.
_NOTE_NAME_HINT = "Use a letter A-G, optionally followed by '#' or 'b', e.g. 'D', 'F#', 'Bb'."


@dataclass(frozen=True, slots=True)
class NoteName:
    """A note as a musician writes it: a letter plus a number of sharps or flats.

    Cast:
        letter: One of :data:`LETTERS`, e.g. ``"B"``.
        accidental: Semitones away from the plain letter: ``-1`` flat,
            ``+1`` sharp, ``-2``/``+2`` double flat/sharp, ``0`` natural.
    """

    letter: str
    accidental: int = 0

    def __post_init__(self) -> None:
        """Refuse to exist in an impossible state, such as the letter "H"."""
        if self.letter not in NATURAL_PITCH_CLASSES:
            raise UnknownNoteError(f"{self.letter!r} is not a note letter. {_NOTE_NAME_HINT}")
        if abs(self.accidental) > MAX_ACCIDENTAL:
            raise UnknownNoteError(
                f"{self.letter} with {self.accidental:+d} semitones needs more than a double "
                "sharp or flat. Use its simpler name instead."
            )

    @classmethod
    def parse(cls, text: str) -> NoteName:
        """Read a note name typed by a person or by Claude.

        Accepts any letter case and both ASCII and music symbols, so ``"bb"``,
        ``"Bb"`` and ``"B♭"`` all mean B flat.
        """
        cleaned = text.strip()  # the name without surrounding spaces
        if not cleaned:
            raise UnknownNoteError(f"The note name is empty. {_NOTE_NAME_HINT}")

        letter = cleaned[0].upper()  # the first character is always the letter
        symbols = cleaned[1:]  # everything after it must be sharps or flats
        if letter not in NATURAL_PITCH_CLASSES or any(
            s not in _ACCIDENTAL_SYMBOLS for s in symbols
        ):
            raise UnknownNoteError(f"Can't read the note name {text!r}. {_NOTE_NAME_HINT}")

        steps = [_ACCIDENTAL_SYMBOLS[symbol] for symbol in symbols]  # +1 per sharp, -1 per flat
        if len(set(steps)) > 1:
            raise UnknownNoteError(f"{text!r} mixes sharps and flats. {_NOTE_NAME_HINT}")
        return cls(letter, sum(steps))

    @property
    def pitch_class(self) -> int:
        """Where the note sits within any octave: 0 = C, 1 = C#/Db, ... 11 = B."""
        return (NATURAL_PITCH_CLASSES[self.letter] + self.accidental) % SEMITONES_PER_OCTAVE

    @property
    def letter_index(self) -> int:
        """The letter's position in :data:`LETTERS`: 0 = C ... 6 = B."""
        return LETTERS.index(self.letter)

    def midi_number(self, octave: int) -> int:
        """The MIDI key this note presses in an FL Studio octave (C5 = 60).

        The octave belongs to the letter, as in standard notation: B#4 is the
        same key as C5 (60), and Cb5 is the same key as B4 (59).
        """
        number = (
            octave * SEMITONES_PER_OCTAVE + NATURAL_PITCH_CLASSES[self.letter] + self.accidental
        )
        check_midi_number(number, f"{self}{octave}")
        return number

    def __str__(self) -> str:
        """Spell the note in plain ASCII: ``"Bb"``, ``"F#"``, ``"Cbb"``, ``"E"``."""
        symbol = "#" if self.accidental > 0 else "b"  # which sign to repeat
        return self.letter + symbol * abs(self.accidental)


def spell_with_letter(letter: str, pitch_class: int) -> NoteName:
    """Name a pitch using a chosen letter, adding whatever sharps or flats it needs.

    Pitch class 10 is ``Bb`` when spelled with the letter B, and ``A#`` with the
    letter A. Scales use this to make sure every letter appears in order.
    """
    natural = NATURAL_PITCH_CLASSES[letter]  # where the plain letter sits
    distance = (pitch_class - natural) % SEMITONES_PER_OCTAVE  # semitones up from the letter, 0-11
    if distance > SEMITONES_PER_OCTAVE // 2:
        distance -= SEMITONES_PER_OCTAVE  # going down is shorter, so use flats
    return NoteName(letter, distance)


def check_midi_number(number: int, label: str) -> None:
    """Stop a note that would fall off the MIDI keyboard (0-127)."""
    if not MIDI_LOWEST <= number <= MIDI_HIGHEST:
        raise OutOfMidiRangeError(
            f"{label} would be MIDI note {number}, outside {MIDI_LOWEST}-{MIDI_HIGHEST}. "
            "Choose a different octave."
        )
