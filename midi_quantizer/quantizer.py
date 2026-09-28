"""Lógica pura de cuantización de eventos MIDI.

Contiene funciones sin estado que operan sobre ticks absolutos.
Todas las funciones están documentadas y tipadas.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Constantes y utilidades de rejilla
# ---------------------------------------------------------------------------

BINARY_GRIDS = {"1/4": 4, "1/8": 8, "1/16": 16, "1/32": 32}
TRIPLET_GRIDS = {"1/4T": 4, "1/8T": 8, "1/16T": 16}
SUPPORTED_GRIDS = list(BINARY_GRIDS) + list(TRIPLET_GRIDS)


class QuantizerError(Exception):
    """Error genérico del cuantizador."""


def grid_to_ticks(grid: str, ppq: int) -> int:
    """Convierte una rejilla musical a ticks.

    Fórmula binaria:   grid_ticks = ppq * 4 / denominador
    Fórmula tresillos: grid_ticks = (ppq * 4 / denominador) * 2 / 3

    Args:
        grid: Rejilla ("1/4", "1/8", "1/16", "1/32", "1/4T", "1/8T", "1/16T").
        ppq: Pulses per quarter note del archivo MIDI.

    Returns:
        Número de ticks que dura una subdivisión de la rejilla.

    Raises:
        QuantizerError: Si la rejilla no es válida o ppq <= 0.
    """
    if ppq <= 0:
        raise QuantizerError(f"PPQ inválido: {ppq}. Debe ser un entero positivo.")
    if grid in BINARY_GRIDS:
        denominator = BINARY_GRIDS[grid]
        return (ppq * 4) // denominator
    if grid in TRIPLET_GRIDS:
        denominator = TRIPLET_GRIDS[grid]
        return ((ppq * 4) // denominator) * 2 // 3
    raise QuantizerError(
        f"Rejilla inválida: '{grid}'. Soportadas: {', '.join(SUPPORTED_GRIDS)}"
    )


def is_triplet(grid: str) -> bool:
    """Indica si una rejilla es de tresillos."""
    return grid in TRIPLET_GRIDS


# ---------------------------------------------------------------------------
# Cuantización de un tick individual
# ---------------------------------------------------------------------------

def quantize_tick(
    tick: int,
    grid_ticks: int,
    strength: float = 100.0,
    swing: float = 0.0,
    humanize_ticks: int = 0,
    rng: Optional[random.Random] = None,
) -> int:
    """Cuantiza un tick absoluto a la rejilla indicada.

    Cuantización: nuevo_tick = round(tick / grid_ticks) * grid_ticks
    Strength:       final = tick + (nuevo_tick - tick) * (strength / 100)
    Swing:          si la subdivisión destino es impar, final += (swing/100) * (grid_ticks/3)
    Humanize:       final += random.randint(-humanize_ticks, humanize_ticks)

    Args:
        tick: Tick absoluto original (>= 0).
        grid_ticks: Tamaño de la rejilla en ticks (> 0).
        strength: Porcentaje de atracción hacia la rejilla (0-100).
        swing: Porcentaje de swing aplicado a subdivisiones impares (0-100).
        humanize_ticks: Amplitud máxima de aleatorización en ticks (>= 0).
        rng: Generador aleatorio opcional (para tests deterministas).

    Returns:
        Tick cuantizado (nunca negativo).

    Raises:
        QuantizerError: Si grid_ticks <= 0.
    """
    if grid_ticks <= 0:
        raise QuantizerError("grid_ticks debe ser un entero positivo.")

    tick = max(0, int(tick))
    nearest = round(tick / grid_ticks) * grid_ticks

    strength = min(100.0, max(0.0, float(strength)))
    final = tick + (nearest - tick) * (strength / 100.0)

    # Swing: solo si la subdivisión de destino es impar (notas "off-beat").
    swing = min(100.0, max(0.0, float(swing)))
    if swing > 0:
        subdivision = round(final / grid_ticks)
        if subdivision % 2 == 1:
            final += (swing / 100.0) * (grid_ticks / 3.0)

    if humanize_ticks > 0:
        generator = rng if rng is not None else random
        final += generator.randint(-humanize_ticks, humanize_ticks)

    return max(0, round(final))


# ---------------------------------------------------------------------------
# Modelo de notas y cuantización de pistas
# ---------------------------------------------------------------------------

@dataclass
class Note:
    """Nota MIDI con ticks absolutos."""

    note: int
    velocity: int
    start: int
    end: int
    channel: int = 0

    @property
    def duration(self) -> int:
        """Duración en ticks (>= 1)."""
        return max(1, self.end - self.start)


@dataclass
class GrooveTemplate:
    """Plantilla de groove: offsets medios por subdivisión de la rejilla.

    La clave de ``offsets`` es el índice de subdivisión
    (``round(tick / grid_ticks)``) y el valor es el desplazamiento medio
    en ticks respecto al punto de rejilla exacto.
    """

    grid_ticks: int
    offsets: dict[int, int] = field(default_factory=dict)

    def offset_for(self, tick: int) -> int:
        """Devuelve el offset del groove para un tick dado (0 si no hay)."""
        if self.grid_ticks <= 0:
            return 0
        subdivision = round(tick / self.grid_ticks)
        return self.offsets.get(subdivision, 0)


def extract_groove(notes: list[Note], grid_ticks: int) -> GrooveTemplate:
    """Extrae una plantilla de groove a partir de los inicios de las notas.

    Para cada subdivisión de la rejilla guarda el desplazamiento medio
    de las notas respecto al punto de rejilla más cercano.

    Args:
        notes: Notas de referencia (por ejemplo, de otro archivo MIDI).
        grid_ticks: Tamaño de la rejilla en ticks.

    Returns:
        GrooveTemplate con los offsets medios por subdivisión.

    Raises:
        QuantizerError: Si grid_ticks <= 0.
    """
    if grid_ticks <= 0:
        raise QuantizerError("grid_ticks debe ser un entero positivo.")

    buckets: dict[int, list[int]] = {}
    for note in notes:
        subdivision = round(note.start / grid_ticks)
        deviation = note.start - subdivision * grid_ticks
        buckets.setdefault(subdivision, []).append(deviation)

    offsets = {
        subdivision: round(sum(deviations) / len(deviations))
        for subdivision, deviations in buckets.items()
    }
    return GrooveTemplate(grid_ticks=grid_ticks, offsets=offsets)


def quantize_notes(
    notes: list[Note],
    ppq: int,
    grid: str = "1/16",
    strength: float = 100.0,
    swing: float = 0.0,
    quantize_starts: bool = True,
    quantize_ends: bool = False,
    preserve_velocity: bool = True,
    humanize_ticks: int = 0,
    groove: Optional[GrooveTemplate] = None,
    rng: Optional[random.Random] = None,
) -> list[Note]:
    """Cuantiza una lista de notas preservando velocidades y duraciones.

    Args:
        notes: Notas de entrada con ticks absolutos.
        ppq: Pulses per quarter note del archivo MIDI.
        grid: Rejilla de cuantización.
        strength: Porcentaje de cuantización (0-100).
        swing: Porcentaje de swing (0-100).
        quantize_starts: Si se cuantizan los inicios de las notas.
        quantize_ends: Si se cuantizan los finales de las notas.
        preserve_velocity: Si se conservan las velocidades originales.
        humanize_ticks: Aleatorización máxima en ticks (0 = desactivado).
        groove: Plantilla de groove opcional a aplicar tras cuantizar.
        rng: Generador aleatorio opcional (para tests deterministas).

    Returns:
        Nueva lista de notas cuantizadas, ordenadas cronológicamente.
        Las duraciones nunca son negativas ni cero.

    Raises:
        QuantizerError: Si ppq o la rejilla no son válidos.
    """
    grid_ticks = grid_to_ticks(grid, ppq)
    quantized: list[Note] = []

    for note in notes:
        duration = note.duration

        if quantize_starts:
            new_start = quantize_tick(
                note.start, grid_ticks, strength, swing, humanize_ticks, rng
            )
        else:
            new_start = note.start

        if quantize_ends:
            new_end = quantize_tick(
                note.end, grid_ticks, strength, swing, humanize_ticks, rng
            )
            if new_end <= new_start:
                # Evita duraciones negativas o cero tras cuantizar.
                new_end = new_start + duration
        else:
            # Preserva la duración original desplazando el final.
            new_end = new_start + duration

        if groove is not None:
            offset = groove.offset_for(new_start)
            new_start = max(0, new_start + offset)
            new_end = max(new_start + 1, new_end + offset)

        velocity = note.velocity if preserve_velocity else note.velocity
        quantized.append(
            Note(
                note=note.note,
                velocity=velocity,
                start=new_start,
                end=max(new_end, new_start + 1),
                channel=note.channel,
            )
        )

    quantized.sort(key=lambda n: (n.start, n.note))
    return _merge_collisions(quantized)


def _merge_collisions(notes: list[Note]) -> list[Note]:
    """Fusiona notas que colisionan (misma nota y mismo tick de inicio).

    Cuando dos notas idénticas caen en el mismo tick tras cuantizar,
    se conserva la de mayor duración y velocidad máxima.
    """
    merged: list[Note] = []
    for note in notes:
        if (
            merged
            and merged[-1].note == note.note
            and merged[-1].start == note.start
            and merged[-1].channel == note.channel
        ):
            previous = merged[-1]
            previous.end = max(previous.end, note.end)
            previous.velocity = max(previous.velocity, note.velocity)
        else:
            merged.append(note)
    return merged
