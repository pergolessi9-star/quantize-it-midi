"""Interfaz de línea de comandos de MIDI Quantizer Pro."""

from __future__ import annotations

import argparse
import sys

from . import io as midi_io
from .quantizer import (
    SUPPORTED_GRIDS,
    QuantizerError,
    extract_groove,
    grid_to_ticks,
    quantize_notes,
)


def build_parser() -> argparse.ArgumentParser:
    """Construye el parser de argumentos con los subcomandos disponibles."""
    parser = argparse.ArgumentParser(
        prog="midi-quantizer",
        description="MIDI Quantizer Pro - Cuantiza archivos MIDI con swing y groove.",
        epilog=(
            "Ejemplos:\n"
            "  %(prog)s quantize -i entrada.mid -o salida.mid --grid 1/16 --strength 85 --swing 20\n"
            "  %(prog)s info -i entrada.mid\n"
            "  %(prog)s extract-groove -i groove.mid -o groove.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- quantize ---
    quantize_parser = subparsers.add_parser(
        "quantize", help="Cuantiza un archivo MIDI."
    )
    quantize_parser.add_argument("--input", "-i", required=True, help="MIDI de entrada.")
    quantize_parser.add_argument("--output", "-o", required=True, help="MIDI de salida.")
    quantize_parser.add_argument(
        "--grid", default="1/16", choices=SUPPORTED_GRIDS, help="Rejilla (def: 1/16)."
    )
    quantize_parser.add_argument(
        "--strength", type=float, default=100.0, help="Fuerza 0-100 (def: 100)."
    )
    quantize_parser.add_argument(
        "--swing", type=float, default=0.0, help="Swing 0-100 (def: 0)."
    )
    quantize_parser.add_argument(
        "--quantize-starts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Cuantizar inicios de nota (def: activado).",
    )
    quantize_parser.add_argument(
        "--quantize-ends",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Cuantizar finales de nota (def: desactivado).",
    )
    quantize_parser.add_argument(
        "--preserve-velocity",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Preservar velocidades (def: activado).",
    )
    quantize_parser.add_argument(
        "--humanize", type=int, default=0, help="Humanizar en ticks (def: 0)."
    )
    quantize_parser.add_argument(
        "--track", type=int, default=None, help="Índice de pista (def: todas)."
    )
    quantize_parser.add_argument(
        "--groove", default=None, help="MIDI de referencia para groove template."
    )

    # --- info ---
    info_parser = subparsers.add_parser(
        "info", help="Muestra información de un archivo MIDI."
    )
    info_parser.add_argument("--input", "-i", required=True, help="MIDI a inspeccionar.")

    # --- extract-groove ---
    groove_parser = subparsers.add_parser(
        "extract-groove", help="Extrae un groove template de un MIDI."
    )
    groove_parser.add_argument("--input", "-i", required=True, help="MIDI de referencia.")
    groove_parser.add_argument(
        "--output", "-o", required=True, help="Archivo JSON de salida del groove."
    )
    groove_parser.add_argument(
        "--grid", default="1/16", choices=SUPPORTED_GRIDS, help="Rejilla base."
    )

    return parser


def cmd_quantize(args: argparse.Namespace) -> int:
    """Ejecuta el subcomando quantize."""
    mid = midi_io.load_midi(args.input)
    notes = midi_io.extract_notes(mid, args.track)
    if not notes:
        print("Aviso: el MIDI no contiene notas; se copia sin cambios.", file=sys.stderr)
        mid.save(args.output)
        return 0

    groove = None
    if args.groove:
        groove_mid = midi_io.load_midi(args.groove)
        groove_notes = midi_io.extract_notes(groove_mid)
        groove = extract_groove(
            groove_notes, grid_to_ticks(args.grid, mid.ticks_per_beat)
        )

    quantized = quantize_notes(
        notes,
        ppq=mid.ticks_per_beat,
        grid=args.grid,
        strength=args.strength,
        swing=args.swing,
        quantize_starts=args.quantize_starts,
        quantize_ends=args.quantize_ends,
        preserve_velocity=args.preserve_velocity,
        humanize_ticks=args.humanize,
        groove=groove,
    )
    midi_io.save_quantized_midi(mid, quantized, args.output, args.track)
    print(f"Cuantizadas {len(quantized)} notas -> {args.output}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Ejecuta el subcomando info."""
    mid = midi_io.load_midi(args.input)
    info = midi_io.midi_info(mid)
    print(f"Archivo:        {args.input}")
    print(f"Tipo:           {info['type']}")
    print(f"PPQ:            {info['ticks_per_beat']}")
    print(f"Duración:       {info['length_seconds']} s")
    print(f"Pistas:         {len(info['tracks'])}")
    for track in info["tracks"]:
        print(
            f"  [{track['index']}] {track['name'] or '(sin nombre)'}: "
            f"{track['notes']} notas, {track['messages']} mensajes"
        )
    return 0


def cmd_extract_groove(args: argparse.Namespace) -> int:
    """Ejecuta el subcomando extract-groove."""
    import json

    mid = midi_io.load_midi(args.input)
    notes = midi_io.extract_notes(mid)
    groove = extract_groove(notes, grid_to_ticks(args.grid, mid.ticks_per_beat))
    payload = {
        "grid": args.grid,
        "grid_ticks": groove.grid_ticks,
        "offsets": {str(k): v for k, v in groove.offsets.items()},
    }
    try:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
    except OSError as exc:
        raise QuantizerError(f"No se pudo escribir '{args.output}': {exc}") from exc
    print(f"Groove guardado en {args.output} ({len(groove.offsets)} posiciones)")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada del CLI. Devuelve el código de salida."""
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "quantize": cmd_quantize,
        "info": cmd_info,
        "extract-groove": cmd_extract_groove,
    }
    try:
        return handlers[args.command](args)
    except QuantizerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
