"""Scales: recipes, spelling, degrees and MIDI numbers."""

import pytest

from fl_mcp.theory import (
    SCALE_TYPES,
    NoteName,
    OutOfMidiRangeError,
    ScaleType,
    UnknownNoteError,
    UnknownScaleError,
    build_scale,
    describe_scale_names,
    find_scale_type,
)
from fl_mcp.theory.notes import LETTERS


def spelled(root: str, scale: str) -> str:
    """The notes of a scale as one space-separated string, for easy comparison."""
    return " ".join(str(note) for note in build_scale(root, scale).notes)


@pytest.mark.parametrize(
    ("root", "scale", "notes"),
    [
        ("D", "minor", "D E F G A Bb C"),  # Bb, never A#
        ("C", "major", "C D E F G A B"),
        ("F#", "major", "F# G# A# B C# D# E#"),  # E#, not F
        ("Gb", "major", "Gb Ab Bb Cb Db Eb F"),  # Cb, not B
        ("D", "harmonic_minor", "D E F G A Bb C#"),
        ("G#", "harmonic_minor", "G# A# B C# D# E F##"),
        ("A", "melodic_minor", "A B C D E F# G#"),
        ("D", "dorian", "D E F G A B C"),
        ("E", "phrygian", "E F G A B C D"),
        ("F", "lydian", "F G A B C D E"),
        ("G", "mixolydian", "G A B C D E F"),
        ("B", "locrian", "B C D E F G A"),
        ("C", "major_pentatonic", "C D E G A"),
        ("A", "minor_pentatonic", "A C D E G"),
        ("C", "blues", "C Eb F Gb G Bb"),
    ],
)
def test_scales_are_spelled_correctly(root: str, scale: str, notes: str) -> None:
    assert spelled(root, scale) == notes


@pytest.mark.parametrize(
    ("scale", "degrees"),
    [
        ("major", ("1", "2", "3", "4", "5", "6", "7")),
        ("natural_minor", ("1", "2", "b3", "4", "5", "b6", "b7")),
        ("lydian", ("1", "2", "3", "#4", "5", "6", "7")),
        ("locrian", ("1", "b2", "b3", "4", "b5", "b6", "b7")),
        ("blues", ("1", "b3", "4", "b5", "5", "b7")),
    ],
)
def test_degrees_compare_with_the_major_scale(scale: str, degrees: tuple[str, ...]) -> None:
    assert find_scale_type(scale).degree_labels == degrees


def test_midi_numbers_rise_from_the_root_in_fl_octaves() -> None:
    assert build_scale("D", "minor").midi_numbers == (62, 64, 65, 67, 69, 70, 72)
    assert build_scale("D", "minor", octave=3).midi_numbers == (38, 40, 41, 43, 45, 46, 48)


def test_scale_knows_its_title_and_octave() -> None:
    scale = build_scale("Bb", "dorian", octave=4)
    assert scale.title == "Bb dorian"
    assert scale.octave == 4
    assert scale.root == NoteName("B", -1)


@pytest.mark.parametrize(
    "name", ["minor", "Natural Minor", "natural-minor", "AEOLIAN", "  natural_minor  "]
)
def test_scale_names_ignore_case_spaces_and_hyphens(name: str) -> None:
    assert find_scale_type(name).name == "natural_minor"


def test_unknown_scale_lists_what_is_supported() -> None:
    with pytest.raises(UnknownScaleError) as raised:
        find_scale_type("sad")
    for scale_type in SCALE_TYPES:
        assert scale_type.name in str(raised.value)


def test_roots_may_have_only_one_sharp_or_flat() -> None:
    with pytest.raises(UnknownNoteError, match="more than one sharp or flat"):
        build_scale("C##", "major")


@pytest.mark.parametrize(("root", "octave"), [("C", 10), ("C", -1)])
def test_scales_must_fit_on_the_midi_keyboard(root: str, octave: int) -> None:
    with pytest.raises(OutOfMidiRangeError):
        build_scale(root, "major", octave)


#: Every root a person might reasonably ask for: each letter plain, sharp and flat.
ALL_ROOTS = [letter + symbol for letter in LETTERS for symbol in ("", "#", "b")]


@pytest.mark.parametrize("root", ALL_ROOTS)
@pytest.mark.parametrize("scale_type", SCALE_TYPES, ids=lambda scale_type: scale_type.name)
def test_every_root_and_scale_is_spelled_consistently(root: str, scale_type: ScaleType) -> None:
    scale = build_scale(root, scale_type)
    root_note = scale.root
    for note, step, interval in zip(
        scale.notes, scale_type.letter_steps, scale_type.intervals, strict=True
    ):
        # Each note uses the letter its step points to...
        assert note.letter == LETTERS[(root_note.letter_index + step) % len(LETTERS)]
        # ...and sounds the pitch its interval points to.
        assert note.pitch_class == (root_note.pitch_class + interval) % 12
    assert list(scale.midi_numbers) == sorted(scale.midi_numbers)


@pytest.mark.parametrize(
    ("intervals", "letter_steps"),
    [
        ((0, 2, 4), (0, 1)),  # different lengths
        ((2, 4), (0, 1)),  # doesn't start on the root
        ((0, 4, 2), (0, 1, 2)),  # intervals go down
        ((0, 2, 12), (0, 1, 2)),  # leaves the octave
        ((0, 2, 4), (0, 2, 1)),  # letters go backwards
    ],
)
def test_broken_recipes_are_refused(
    intervals: tuple[int, ...], letter_steps: tuple[int, ...]
) -> None:
    with pytest.raises(ValueError):
        ScaleType("broken", intervals, letter_steps, "A recipe that can't work.")


def test_description_names_every_scale_and_alias() -> None:
    description = describe_scale_names()
    for scale_type in SCALE_TYPES:
        for name in (scale_type.name, *scale_type.aliases):
            assert name in description
