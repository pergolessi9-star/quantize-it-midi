"""Entrada/salida de archivos MIDI con mido.

Carga y guarda archivos MIDI preservando tempo, compás, pistas y meta eventos.
"""

from __future__ import annotations

import mido

from .quantizer import Note, QuantizerError


def load_midi(path: str) -> mido.MidiFile:
    """Carga un archivo MIDI.

    Args:
        path: Ruta al archivo .mid.

    Returns:
        Objeto mido.MidiFile.

    Raises:
        QuantizerError: Si el archivo no existe o no es un MIDI válido.
    """
    try:
        return mido.MidiFile(path)
    except FileNotFoundError as exc:
        raise QuantizerError(f"Archivo no encontrado: {path}") from exc
    except (OSError, ValueError, EOFError) as exc:
        raise QuantizerError(f"No se pudo leer el MIDI '{path}': {exc}") from exc


def list_tracks(mid: mido.MidiFile) -> list[str]:
    """Devuelve los nombres (o índices) de las pistas de un MIDI.

    Args:
        mid: Archivo MIDI cargado.

    Returns:
        Lista de descripciones de pista, por ejemplo ["0: Piano", "1: Drums"].
    """
    names = []
    for index, track in enumerate(mid.tracks):
        track_name = ""
        for msg in track:
            if msg.type == "track_name":
                track_name = msg.name
                break
        label = f"{index}: {track_name}" if track_name else f"{index}"
        names.append(label)
    return names


def extract_notes(
    mid: mido.MidiFile, track_index: int | None = None
) -> list[Note]:
    """Extrae las notas de un MIDI como lista de Note con ticks absolutos.

    Los eventos note_on con velocity 0 se tratan como note_off.

    Args:
        mid: Archivo MIDI cargado.
        track_index: Índice de pista a procesar, o None para todas.

    Returns:
        Lista de notas ordenada por tick de inicio.

    Raises:
        QuantizerError: Si el índice de pista no existe.
    """
    if track_index is not None and not (0 <= track_index < len(mid.tracks)):
        raise QuantizerError(
            f"Pista {track_index} fuera de rango (hay {len(mid.tracks)} pistas)."
        )

    indices = (
        [track_index] if track_index is not None else range(len(mid.tracks))
    )
    notes: list[Note] = []

    for index in indices:
        track = mid.tracks[index]
        absolute_tick = 0
        # Pendientes: (note, channel) -> (start_tick, velocity)
        pending: dict[tuple[int, int], tuple[int, int]] = {}

        for msg in track:
            absolute_tick += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                pending[(msg.note, msg.channel)] = (absolute_tick, msg.velocity)
            elif msg.type == "note_off" or (
                msg.type == "note_on" and msg.velocity == 0
            ):
                key = (msg.note, msg.channel)
                if key in pending:
                    start_tick, velocity = pending.pop(key)
                    if absolute_tick > start_tick:
                        notes.append(
                            Note(
                                note=msg.note,
                                velocity=velocity,
                                start=start_tick,
                                end=absolute_tick,
                                channel=msg.channel,
                            )
                        )

        # Cierra notas colgadas al final de la pista.
        for (note_number, channel), (start_tick, velocity) in pending.items():
            end_tick = max(absolute_tick, start_tick + 1)
            notes.append(
                Note(
                    note=note_number,
                    velocity=velocity,
                    start=start_tick,
                    end=end_tick,
                    channel=channel,
                )
            )

    notes.sort(key=lambda n: (n.start, n.note))
    return notes


def save_quantized_midi(
    source: mido.MidiFile,
    quantized_notes: list[Note],
    output_path: str,
    track_index: int | None = None,
) -> None:
    """Guarda un MIDI reemplazando las notas de la pista indicada por las cuantizadas.

    Preserva tempo, compás, meta eventos y eventos que no sean notas.

    Args:
        source: MIDI original cargado.
        quantized_notes: Notas ya cuantizadas (ticks absolutos).
        output_path: Ruta del archivo de salida.
        track_index: Pista a reemplazar, o None para reemplazar todas
            las pistas que contengan notas.

    Raises:
        QuantizerError: Si no se puede escribir el archivo.
    """
    new_mid = mido.MidiFile(ticks_per_beat=source.ticks_per_beat, type=source.type)

    for index, track in enumerate(source.tracks):
        has_notes = any(
            msg.type in ("note_on", "note_off") for msg in track
        )
        should_replace = has_notes and (
            track_index is None or index == track_index
        )

        if not should_replace:
            new_mid.tracks.append(track.copy())
            continue

        # Conserva meta eventos y eventos que no son notas con su tick absoluto.
        absolute_tick = 0
        kept: list[tuple[int, mido.Message]] = []
        for msg in track:
            absolute_tick += msg.time
            if msg.type not in ("note_on", "note_off"):
                kept.append((absolute_tick, msg.copy()))

        # Notas cuantizadas de esta pista.
        track_notes = [n for n in quantized_notes]
        events: list[tuple[int, mido.Message]] = list(kept)
        for note in track_notes:
            events.append(
                (
                    note.start,
                    mido.Message(
                        "note_on",
                        note=note.note,
                        velocity=note.velocity,
                        channel=note.channel,
                    ),
                )
            )
            events.append(
                (
                    note.end,
                    mido.Message(
                        "note_off",
                        note=note.note,
                        velocity=0,
                        channel=note.channel,
                    ),
                )
            )

        # Ordena por tick absoluto y convierte a tiempos delta.
        events.sort(key=lambda item: (item[0], 0 if item[1].type != "note_off" else -1))
        new_track = mido.MidiTrack()
        last_tick = 0
        for tick, msg in events:
            msg.time = max(0, tick - last_tick)
            last_tick = tick
            new_track.append(msg)
        new_track.append(mido.MetaMessage("end_of_track", time=0))
        new_mid.tracks.append(new_track)

    try:
        new_mid.save(output_path)
    except OSError as exc:
        raise QuantizerError(
            f"No se pudo guardar el MIDI '{output_path}': {exc}"
        ) from exc


def midi_info(mid: mido.MidiFile) -> dict:
    """Devuelve información resumida de un archivo MIDI.

    Args:
        mid: Archivo MIDI cargado.

    Returns:
        Diccionario con tipo, ppq, número de pistas, duración y
        estadísticas por pista.
    """
    info: dict = {
        "type": mid.type,
        "ticks_per_beat": mid.ticks_per_beat,
        "length_seconds": round(mid.length, 3),
        "tracks": [],
    }
    for index, track in enumerate(mid.tracks):
        note_count = sum(
            1 for msg in track if msg.type == "note_on" and msg.velocity > 0
        )
        name = ""
        for msg in track:
            if msg.type == "track_name":
                name = msg.name
                break
        info["tracks"].append(
            {
                "index": index,
                "name": name,
                "messages": len(track),
                "notes": note_count,
            }
        )
    return info
