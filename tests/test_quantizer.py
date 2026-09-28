"""Tests unitarios de MIDI Quantizer Pro."""

from __future__ import annotations

import random

import pytest

from midi_quantizer.quantizer import (
    GrooveTemplate,
    Note,
    QuantizerError,
    extract_groove,
    grid_to_ticks,
    is_triplet,
    quantize_notes,
    quantize_tick,
)

PPQ = 480


# ---------------------------------------------------------------------------
# Rejillas
# ---------------------------------------------------------------------------

class TestGridToTicks:
    """Rejillas binarias y de tresillos."""

    @pytest.mark.parametrize(
        "grid,expected",
        [("1/4", 480), ("1/8", 240), ("1/16", 120), ("1/32", 60)],
    )
    def test_binary_grids(self, grid: str, expected: int) -> None:
        assert grid_to_ticks(grid, PPQ) == expected

    @pytest.mark.parametrize(
        "grid,expected",
        [("1/4T", 320), ("1/8T", 160), ("1/16T", 80)],
    )
    def test_triplet_grids(self, grid: str, expected: int) -> None:
        assert grid_to_ticks(grid, PPQ) == expected

    def test_triplet_detection(self) -> None:
        assert is_triplet("1/8T")
        assert not is_triplet("1/8")

    def test_invalid_grid_raises(self) -> None:
        with pytest.raises(QuantizerError):
            grid_to_ticks("1/7", PPQ)

    def test_ppq_zero_raises(self) -> None:
        with pytest.raises(QuantizerError):
            grid_to_ticks("1/16", 0)

    def test_ppq_negative_raises(self) -> None:
        with pytest.raises(QuantizerError):
            grid_to_ticks("1/16", -480)


# ---------------------------------------------------------------------------
# quantize_tick
# ---------------------------------------------------------------------------

class TestQuantizeTick:
    """Cuantización de ticks individuales."""

    def test_perfect_quantization_snaps_to_grid(self) -> None:
        grid = grid_to_ticks("1/16", PPQ)  # 120
        assert quantize_tick(130, grid, strength=100) == 120
        assert quantize_tick(190, grid, strength=100) == 240

    def test_strength_zero_leaves_tick_unchanged(self) -> None:
        grid = grid_to_ticks("1/16", PPQ)
        assert quantize_tick(137, grid, strength=0) == 137

    def test_strength_fifty_moves_halfway(self) -> None:
        grid = grid_to_ticks("1/16", PPQ)  # 120
        # 130 -> destino 120, la mitad del camino = 125
        assert quantize_tick(130, grid, strength=50) == 125

    def test_strength_hundred_snaps_fully(self) -> None:
        grid = grid_to_ticks("1/16", PPQ)
        assert quantize_tick(100, grid, strength=100) == 120

    def test_swing_zero_no_offset(self) -> None:
        grid = grid_to_ticks("1/16", PPQ)
        assert quantize_tick(121, grid, strength=100, swing=0) == 120

    def test_swing_only_on_odd_subdivisions(self) -> None:
        grid = grid_to_ticks("1/8", PPQ)  # 240
        swing_offset = round((100 / 100) * (240 / 3))  # 80
        # Subdivisión 0 (par): sin swing
        assert quantize_tick(10, grid, strength=100, swing=100) == 0
        # Subdivisión 1 (impar): con swing
        assert quantize_tick(240, grid, strength=100, swing=100) == 240 + swing_offset
        # Subdivisión 2 (par): sin swing
        assert quantize_tick(480, grid, strength=100, swing=100) == 480

    def test_swing_fifty_applies_half_offset(self) -> None:
        grid = grid_to_ticks("1/8", PPQ)
        half = round(0.5 * (240 / 3))  # 40
        assert quantize_tick(240, grid, strength=100, swing=50) == 240 + half

    def test_humanize_stays_within_range(self) -> None:
        grid = grid_to_ticks("1/16", PPQ)
        rng = random.Random(42)
        for _ in range(200):
            result = quantize_tick(120, grid, strength=100, humanize_ticks=10, rng=rng)
            assert 110 <= result <= 130

    def test_humanize_never_negative(self) -> None:
        grid = grid_to_ticks("1/16", PPQ)
        rng = random.Random(7)
        for _ in range(200):
            assert quantize_tick(0, grid, humanize_ticks=50, rng=rng) >= 0

    def test_negative_tick_clamped(self) -> None:
        grid = grid_to_ticks("1/16", PPQ)
        assert quantize_tick(-50, grid) >= 0

    def test_tick_zero_quantizes_to_zero(self) -> None:
        grid = grid_to_ticks("1/16", PPQ)
        assert quantize_tick(0, grid, strength=100) == 0

    def test_grid_ticks_zero_raises(self) -> None:
        with pytest.raises(QuantizerError):
            quantize_tick(100, 0)

    def test_last_tick_of_song(self) -> None:
        grid = grid_to_ticks("1/4", PPQ)
        big_tick = 16 * grid + 37
        result = quantize_tick(big_tick, grid, strength=100)
        assert result % grid == 0


# ---------------------------------------------------------------------------
# quantize_notes
# ---------------------------------------------------------------------------

def make_note(start: int, end: int, note: int = 60, velocity: int = 100) -> Note:
    return Note(note=note, velocity=velocity, start=start, end=end)


class TestQuantizeNotes:
    """Cuantización de listas de notas."""

    def test_quantize_starts_true(self) -> None:
        notes = [make_note(130, 370)]
        result = quantize_notes(notes, PPQ, grid="1/16", strength=100)
        assert result[0].start == 120
        # Duración preservada (240) al no cuantizar finales
        assert result[0].end == 360

    def test_quantize_starts_false(self) -> None:
        notes = [make_note(133, 373)]
        result = quantize_notes(
            notes, PPQ, grid="1/16", strength=100, quantize_starts=False
        )
        assert result[0].start == 133
        assert result[0].end == 373

    def test_quantize_ends_true(self) -> None:
        notes = [make_note(130, 375)]
        result = quantize_notes(
            notes, PPQ, grid="1/16", strength=100, quantize_ends=True
        )
        assert result[0].start == 120
        assert result[0].end == 360

    def test_quantize_ends_false_preserves_duration(self) -> None:
        notes = [make_note(130, 375)]
        result = quantize_notes(
            notes, PPQ, grid="1/16", strength=100, quantize_ends=False
        )
        assert result[0].duration == 245

    def test_preserve_velocity(self) -> None:
        notes = [make_note(130, 370, velocity=87)]
        result = quantize_notes(notes, PPQ, grid="1/16", preserve_velocity=True)
        assert result[0].velocity == 87

    def test_no_negative_durations_when_end_before_start(self) -> None:
        # start=119 (cuantiza a 120), end=121 (cuantiza a 120): colisión
        notes = [make_note(119, 121)]
        result = quantize_notes(
            notes, PPQ, grid="1/16", strength=100, quantize_ends=True
        )
        assert result[0].end > result[0].start

    def test_output_sorted_chronologically(self) -> None:
        notes = [make_note(500, 600, note=62), make_note(100, 200, note=60)]
        result = quantize_notes(notes, PPQ, grid="1/16")
        assert result[0].start <= result[1].start

    def test_colliding_notes_merged(self) -> None:
        # Ambas cuantizan a start=240 con la misma nota
        notes = [make_note(238, 300), make_note(242, 350)]
        result = quantize_notes(notes, PPQ, grid="1/16", strength=100)
        assert len(result) == 1
        # mayor duración conservada: 240 + 108 = 348
        assert result[0].end == 348

    def test_swing_applied_to_notes(self) -> None:
        grid = grid_to_ticks("1/8", PPQ)
        notes = [make_note(grid, grid + 120)]  # subdivisión 1 (impar)
        result = quantize_notes(notes, PPQ, grid="1/8", strength=100, swing=100)
        assert result[0].start == grid + round(grid / 3)

    def test_humanize_within_range(self) -> None:
        rng = random.Random(1)
        notes = [make_note(120, 240) for _ in range(50)]
        result = quantize_notes(
            notes, PPQ, grid="1/16", humanize_ticks=10, rng=rng
        )
        for note in result:
            assert 110 <= note.start <= 130

    def test_invalid_grid_raises(self) -> None:
        with pytest.raises(QuantizerError):
            quantize_notes([make_note(0, 100)], PPQ, grid="1/7")

    def test_ppq_zero_raises(self) -> None:
        with pytest.raises(QuantizerError):
            quantize_notes([make_note(0, 100)], 0, grid="1/16")

    def test_empty_note_list(self) -> None:
        assert quantize_notes([], PPQ, grid="1/16") == []

    def test_note_at_tick_zero(self) -> None:
        notes = [make_note(0, 100)]
        result = quantize_notes(notes, PPQ, grid="1/16", strength=100)
        assert result[0].start == 0

    def test_strength_fifty_keeps_partial_groove(self) -> None:
        notes = [make_note(140, 380)]  # desplazada +20 respecto a 120
        result = quantize_notes(notes, PPQ, grid="1/16", strength=50)
        assert result[0].start == 130  # a medio camino, conserva algo de groove


# ---------------------------------------------------------------------------
# Groove template
# ---------------------------------------------------------------------------

class TestGrooveTemplate:
    """Extracción y aplicación de grooves."""

    def test_extract_groove_offsets(self) -> None:
        grid = grid_to_ticks("1/16", PPQ)  # 120
        # Notas sistemáticamente 12 ticks tarde
        notes = [make_note(grid * i + 12, grid * i + 100) for i in range(4)]
        groove = extract_groove(notes, grid)
        assert groove.grid_ticks == grid
        # Las notas caen en las subdivisiones 0..3, todas +12 ticks
        for subdivision in range(4):
            assert groove.offsets[subdivision] == 12

    def test_extract_groove_empty(self) -> None:
        groove = extract_groove([], 120)
        assert groove.offsets == {}

    def test_extract_groove_invalid_grid(self) -> None:
        with pytest.raises(QuantizerError):
            extract_groove([], 0)

    def test_apply_groove_shifts_notes(self) -> None:
        grid = 120
        groove = GrooveTemplate(grid_ticks=grid, offsets={1: 15})
        notes = [make_note(119, 239)]  # cuantiza a 120 (subdivisión 1)
        result = quantize_notes(notes, PPQ, grid="1/16", strength=100, groove=groove)
        assert result[0].start == 135
        assert result[0].duration == 120

    def test_groove_offset_for_unknown_position_is_zero(self) -> None:
        groove = GrooveTemplate(grid_ticks=120, offsets={30: 10})
        assert groove.offset_for(0) == 0
        assert groove.offset_for(30 * 120) == 10

    def test_groove_roundtrip_extract_and_apply(self) -> None:
        grid = grid_to_ticks("1/16", PPQ)
        reference = [make_note(grid + 8, grid + 100)]
        groove = extract_groove(reference, grid)
        target = [make_note(grid + 1, grid + 90)]
        result = quantize_notes(target, PPQ, grid="1/16", strength=100, groove=groove)
        assert result[0].start == grid + 8
