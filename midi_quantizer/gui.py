"""Interfaz gráfica Tkinter de MIDI Quantizer Pro."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import mido

from . import io as midi_io
from .quantizer import SUPPORTED_GRIDS, QuantizerError, quantize_notes


class QuantizerApp(tk.Tk):
    """Ventana principal de MIDI Quantizer Pro."""

    def __init__(self) -> None:
        """Inicializa la ventana y todos sus widgets."""
        super().__init__()
        self.title("MIDI Quantizer Pro")
        self.geometry("700x500")
        self.minsize(640, 460)

        self._midi: mido.MidiFile | None = None
        self._input_path: str = ""

        self._build_widgets()

    # ------------------------------------------------------------------ UI

    def _build_widgets(self) -> None:
        """Crea y dispone todos los widgets de la ventana."""
        main = ttk.Frame(self, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        # --- Archivo ---
        file_frame = ttk.LabelFrame(main, text="Archivo MIDI", padding=10)
        file_frame.pack(fill=tk.X)

        ttk.Button(file_frame, text="Cargar MIDI", command=self._on_load).pack(
            side=tk.LEFT
        )
        self.file_label = ttk.Label(file_frame, text="(ningún archivo cargado)")
        self.file_label.pack(side=tk.LEFT, padx=12)

        # --- Pista ---
        track_frame = ttk.LabelFrame(main, text="Pista", padding=10)
        track_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(track_frame, text="Pista a cuantizar:").pack(side=tk.LEFT)
        self.track_var = tk.StringVar(value="Todas")
        self.track_combo = ttk.Combobox(
            track_frame, textvariable=self.track_var, state="readonly", values=["Todas"]
        )
        self.track_combo.pack(side=tk.LEFT, padx=8)

        # --- Rejilla ---
        grid_frame = ttk.LabelFrame(main, text="Rejilla", padding=10)
        grid_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(grid_frame, text="Rejilla:").pack(side=tk.LEFT)
        self.grid_var = tk.StringVar(value="1/16")
        ttk.Combobox(
            grid_frame,
            textvariable=self.grid_var,
            state="readonly",
            values=SUPPORTED_GRIDS,
            width=8,
        ).pack(side=tk.LEFT, padx=8)

        # --- Sliders ---
        sliders = ttk.LabelFrame(main, text="Parámetros", padding=10)
        sliders.pack(fill=tk.X, pady=(10, 0))

        self.strength_var = tk.IntVar(value=100)
        self.swing_var = tk.IntVar(value=0)
        self._build_slider(sliders, "Strength:", self.strength_var, 0)
        self._build_slider(sliders, "Swing:", self.swing_var, 1)

        # --- Opciones ---
        options = ttk.LabelFrame(main, text="Opciones", padding=10)
        options.pack(fill=tk.X, pady=(10, 0))

        self.quantize_starts_var = tk.BooleanVar(value=True)
        self.quantize_ends_var = tk.BooleanVar(value=False)
        self.preserve_velocity_var = tk.BooleanVar(value=True)
        self.humanize_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(
            options, text="Cuantizar inicios", variable=self.quantize_starts_var
        ).grid(row=0, column=0, sticky=tk.W, padx=(0, 16))
        ttk.Checkbutton(
            options, text="Cuantizar finales", variable=self.quantize_ends_var
        ).grid(row=0, column=1, sticky=tk.W, padx=(0, 16))
        ttk.Checkbutton(
            options, text="Preservar velocidad", variable=self.preserve_velocity_var
        ).grid(row=1, column=0, sticky=tk.W, padx=(0, 16))
        ttk.Checkbutton(
            options, text="Humanizar", variable=self.humanize_var
        ).grid(row=1, column=1, sticky=tk.W, padx=(0, 16))

        ttk.Label(options, text="Humanize ticks:").grid(row=1, column=2, sticky=tk.E)
        self.humanize_entry = ttk.Entry(options, width=6)
        self.humanize_entry.insert(0, "0")
        self.humanize_entry.grid(row=1, column=3, sticky=tk.W, padx=(6, 0))

        # --- Acción ---
        ttk.Button(
            main, text="Cuantizar y guardar", command=self._on_quantize
        ).pack(pady=16)

        # --- Barra de estado ---
        self.status_var = tk.StringVar(value="Listo. Carga un archivo MIDI.")
        status = ttk.Label(
            self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=6
        )
        status.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_slider(
        self, parent: ttk.Frame, label: str, variable: tk.IntVar, row: int
    ) -> None:
        """Crea un slider 0-100 con etiqueta dinámica de valor."""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W)
        value_label = ttk.Label(parent, text=str(variable.get()), width=4)

        def on_change(_: str) -> None:
            value_label.config(text=str(variable.get()))

        slider = ttk.Scale(
            parent,
            from_=0,
            to=100,
            variable=variable,
            command=on_change,
            length=300,
        )
        slider.grid(row=row, column=1, sticky=tk.W, padx=8, pady=4)
        value_label.grid(row=row, column=2, sticky=tk.W)

    # -------------------------------------------------------------- Lógica

    def _on_load(self) -> None:
        """Abre el diálogo de carga y actualiza la lista de pistas."""
        path = filedialog.askopenfilename(
            title="Selecciona un archivo MIDI",
            filetypes=[("Archivos MIDI", "*.mid *.midi"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            self._midi = midi_io.load_midi(path)
        except QuantizerError as exc:
            messagebox.showerror("Error al cargar", str(exc))
            self.status_var.set(f"Error: {exc}")
            return

        self._input_path = path
        self.file_label.config(text=path.split("/")[-1])
        names = ["Todas"] + midi_io.list_tracks(self._midi)
        self.track_combo.config(values=names)
        self.track_var.set("Todas")
        self.status_var.set(
            f"Cargado: {len(self._midi.tracks)} pistas, PPQ={self._midi.ticks_per_beat}"
        )

    def _on_quantize(self) -> None:
        """Cuantiza el MIDI cargado y guarda el resultado."""
        if self._midi is None:
            messagebox.showwarning("Sin archivo", "Carga primero un archivo MIDI.")
            return

        track_selection = self.track_var.get()
        track_index: int | None = None
        if track_selection != "Todas":
            try:
                track_index = int(track_selection.split(":")[0])
            except ValueError:
                track_index = None

        try:
            humanize_ticks = (
                int(self.humanize_entry.get()) if self.humanize_var.get() else 0
            )
        except ValueError:
            messagebox.showerror(
                "Valor inválido", "Humanize ticks debe ser un entero >= 0."
            )
            return

        try:
            notes = midi_io.extract_notes(self._midi, track_index)
            if not notes:
                messagebox.showwarning(
                    "Sin notas", "La selección no contiene notas MIDI."
                )
                return
            quantized = quantize_notes(
                notes,
                ppq=self._midi.ticks_per_beat,
                grid=self.grid_var.get(),
                strength=float(self.strength_var.get()),
                swing=float(self.swing_var.get()),
                quantize_starts=self.quantize_starts_var.get(),
                quantize_ends=self.quantize_ends_var.get(),
                preserve_velocity=self.preserve_velocity_var.get(),
                humanize_ticks=humanize_ticks,
            )
        except QuantizerError as exc:
            messagebox.showerror("Error al cuantizar", str(exc))
            self.status_var.set(f"Error: {exc}")
            return

        output_path = filedialog.asksaveasfilename(
            title="Guardar MIDI cuantizado",
            defaultextension=".mid",
            filetypes=[("Archivos MIDI", "*.mid")],
        )
        if not output_path:
            self.status_var.set("Guardado cancelado.")
            return

        try:
            midi_io.save_quantized_midi(self._midi, quantized, output_path, track_index)
        except QuantizerError as exc:
            messagebox.showerror("Error al guardar", str(exc))
            self.status_var.set(f"Error: {exc}")
            return

        self.status_var.set(
            f"Guardado {output_path} ({len(quantized)} notas cuantizadas)"
        )
        messagebox.showinfo("Listo", f"Archivo guardado:\n{output_path}")


def run() -> None:
    """Lanza la aplicación gráfica."""
    app = QuantizerApp()
    app.mainloop()
