# MIDI Quantizer Pro

Herramienta de cuantización MIDI con CLI y GUI (Tkinter). Cuantiza inicios y
finales de nota a rejillas binarias o de tresillos, con control de fuerza
(strength), swing, humanización y plantillas de groove extraídas de otros
archivos MIDI. Preserva tempo, compás, meta eventos y velocidades.

## Características

- Rejillas: `1/4`, `1/8`, `1/16`, `1/32` y tresillos `1/4T`, `1/8T`, `1/16T`.
- **Strength** (0-100): cuánto se acerca cada nota a la rejilla.
- **Swing** (0-100): retrasa las subdivisiones impares para dar groove.
- **Humanize**: aleatorización controlada en ticks, nunca produce ticks negativos.
- **Groove template**: extrae el feel de otro MIDI y aplícalo al tuyo.
- Cuantización independiente de inicios y finales, sin duraciones negativas.
- Fusión automática de notas que colisionan tras cuantizar.
- CLI con subcomandos `quantize`, `info` y `extract-groove`.
- GUI nativa con Tkinter/ttk.
- Suite de 45 tests con pytest.

## Instalación

```bash
git clone https://github.com/pergolessi9-star/quantize-it-midi.git
cd quantize-it-midi
pip install -r requirements.txt
```

Requisitos: Python 3.11+ y `tkinter` (en Linux: `sudo apt install python3-tk`).

## Uso CLI

```bash
# Cuantización perfecta a 1/16
python -m midi_quantizer.main quantize -i entrada.mid -o salida.mid --grid 1/16

# Cuantización al 85% con swing 20 (ejemplo recomendado)
python -m midi_quantizer.main quantize -i entrada.mid -o salida.mid \
    --grid 1/16 --strength 85 --swing 20

# Cuantizar también los finales y humanizar ±8 ticks
python -m midi_quantizer.main quantize -i entrada.mid -o salida.mid \
    --grid 1/8 --quantize-ends --humanize 8

# Solo la pista 2
python -m midi_quantizer.main quantize -i entrada.mid -o salida.mid --track 2

# Información de un MIDI
python -m midi_quantizer.main info -i entrada.mid

# Extraer un groove y aplicarlo
python -m midi_quantizer.main extract-groove -i groove.mid -o groove.json
python -m midi_quantizer.main quantize -i entrada.mid -o salida.mid \
    --grid 1/16 --groove groove.mid
```

## Uso GUI

```bash
python -m midi_quantizer.main        # sin argumentos abre la GUI
```

1. **Cargar MIDI**: selecciona el archivo; la barra de estado muestra pistas y PPQ.
2. Elige la **pista** (o "Todas") y la **rejilla** en los desplegables.
3. Ajusta **Strength** y **Swing** con los sliders (valor visible al lado).
4. Marca las opciones: cuantizar inicios/finales, preservar velocidad, humanizar.
5. **Cuantizar y guardar**: elige la ruta de salida y listo.

Los errores (archivo inválido, rejilla incorrecta, etc.) se muestran en
diálogos y en la barra de estado.

## Ejemplos de cuantización

| Escenario | Parámetros | Resultado |
|---|---|---|
| Perfecta | `--grid 1/16 --strength 100` | Cada nota cae exactamente en múltiplos de 120 ticks (con PPQ=480). |
| Con groove | `--grid 1/16 --strength 85 --swing 20` | Las notas conservan un 15% de su desplazamiento original y las subdivisiones impares se retrasan un 20% de `grid/3`. |
| Groove template | `--groove otro.mid` | Los inicios adoptan los desplazamientos medios del MIDI de referencia. |

### Ejemplo detallado: 1/16, strength 85, swing 20

Con PPQ=480 la rejilla 1/16 son 120 ticks. Una nota en el tick 137:

1. Rejilla más cercana: 120. Con strength 85: `137 + (120-137)*0.85 ≈ 123`.
2. Swing: subdivisión 1 (impar) → `+0.20 * (120/3) = +8` → tick final **131**.

El resultado suena pegado a la rejilla pero con aire y vaivén.

## Solución de problemas

| Problema | Causa probable | Solución |
|---|---|---|
| `No se pudo iniciar la GUI` | Falta tkinter | `sudo apt install python3-tk` (Linux) o reinstala Python con tcl/tk. |
| `Rejilla inválida` | Rejilla no soportada | Usa una de: 1/4, 1/8, 1/16, 1/32, 1/4T, 1/8T, 1/16T. |
| El resultado no suena distinto | Strength muy bajo | Sube strength a 85-100. |
| Notas demasiado rígidas | Strength 100 sin swing | Prueba strength 85 y swing 15-25. |
| `Archivo no encontrado` | Ruta incorrecta | Usa rutas absolutas o verifica el nombre. |

## Tests

```bash
pytest tests/ -q
# 45 passed
```

## Empaquetado con PyInstaller

```bash
pip install pyinstaller

# Windows
pyinstaller --onefile --windowed --name MidiQuantizer midi_quantizer/main.py

# macOS
pyinstaller --onefile --windowed --name MidiQuantizer midi_quantizer/main.py

# Linux
pyinstaller --onefile --windowed --name MidiQuantizer midi_quantizer/main.py
```

`mido` es Python puro, se incluye automáticamente. El binario queda en
`dist/`. Para probarlo: ejecútalo sin argumentos (debe abrir la GUI) o
`dist/MidiQuantizer info -i archivo.mid`.

## Estructura del proyecto

```
midi_quantizer/
├── __init__.py
├── quantizer.py   # lógica pura de cuantización
├── io.py          # carga/guardado MIDI con mido
├── cli.py         # interfaz de línea de comandos
├── gui.py         # interfaz gráfica Tkinter
└── main.py        # punto de entrada (GUI o CLI)
tests/
└── test_quantizer.py
requirements.txt
README.md
```

## Licencia

MIT License. Copyright (c) 2026 MIDI Quantizer Pro.

Se concede permiso, de forma gratuita, a cualquier persona que obtenga una
copia de este software y su documentación, para usar, copiar, modificar,
fusionar, publicar, distribuir, sublicenciar y/o vender copias del software,
sujeto a incluir este aviso de copyright en todas las copias. El software se
proporciona "tal cual", sin garantía de ningún tipo.
