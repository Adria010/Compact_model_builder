# `viz.py` — Visualizer

This module provides the `visualizer` class, which generates interactive Plotly figures for one or more photonic components simultaneously. It relies on `fom` for metric computation and `utils` for data loading.

---

## Class `visualizer(data, pol_in, input, id=None)`

### Constructor parameters

| Parameter | Type | Description |
|---|---|---|
| `data` | `str / Path` | Path to a `BBinstances.json` file. |
| `pol_in` | `str` | Input polarization to filter (e.g. `"TE0"`). |
| `input` | `int` | Input port number used to select the relevant S-columns. |
| `id` | `str / list / None` | One or more component IDs to load and display. |

The constructor loads each component ID into an internal `self.components` dictionary. For every valid ID it stores the filtered DataFrame and the component description string (extracted from the JSON). If no valid ID can be loaded, a `ValueError` is raised.

---

## Methods

### `.plot(plot=None)`

Generates and displays an **interactive Plotly figure** combining all loaded components.

#### `plot` argument options

| Value | Description | Y-axis label |
|---|---|---|
| `"magnitude"` | Raw linear S-parameter magnitude | `Magnitude` |
| `"phase"` | S-parameter phase in radians | `Phase` |
| `"IL"` | Insertion loss (dB), via `fom.IL()` | `Insertion losses (dB)` |
| `"EL"` | Excess loss (dB), via `fom.EL()` | `Excess loss (dB)` |
| `"XT"` | Crosstalk (dB), via `fom.XT()` | `Crosstalk (dB)` |
| `"IB"` | Imbalance (dB), via `fom.IB()` | `Imbalance (dB)` |

Any other value raises a `ValueError`.

#### Figure layout

- The subplot grid has **one row per component** and **one column per S-parameter column**.
- Each component row is labeled with its description string as a bold annotation.
- Subplot column headers show the S-parameter key names (e.g. `S21_magnitude`).
- The x-axis of every subplot is labeled `Wavelength (nm)`.
- The y-axis label appears only on the first column of each row.

#### Trace styling

- **TE polarizations** are plotted as solid lines.
- **TM polarizations** are plotted as lines with markers. The marker density is automatically reduced for large datasets (step of 1 / 5 / 10 for < 200 / < 1000 / ≥ 1000 points) to keep the figure responsive.
- Each unique `pol_out` value gets a consistent color across all subplots (drawn from a 10-color palette).
- Legend entries are deduplicated so each `pol_out` appears only once in the legend.

#### Rendering

The figure is displayed with `fig.show(renderer="notebook_connected")`, making it suitable for use inside a Jupyter notebook.
