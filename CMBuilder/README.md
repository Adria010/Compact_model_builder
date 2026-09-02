# CMBuilder
Compact Models Builder: Visualize magnitude, phase, insertion loss, crosstalk, excess loss, and imbalance of different photonic or RF components by processing their S-parameter data. The tool extracts relevant S-parameters from simulation or measurement results and computes key performance metrics, enabling a clear evaluation of each component's behavior. These metrics are then plotted to compare transmission efficiency, signal isolation between ports, and additional losses introduced by the device, for different polarization states.

The visualization can be performed using different input formats, including JSON files, in-memory Python dictionaries, or pandas DataFrames. However, it is strongly recommended to use components stored in the `BBinstances.json` file, as the data is expected to follow a specific structure required by the implementation. Using other formats may require careful preprocessing to ensure compatibility and correct results.

## Confidentiality Notice

**This content is confidential and belongs to UPVfab.**

All information contained in this repository is proprietary and confidential to UPVfab. Unauthorized copying, distribution, or use of this material is strictly prohibited.

---

## Installation & Setup (Windows + uv)

This project uses [uv](https://github.com/astral-sh/uv) for dependency management and virtual environment handling.

### 1. Install uv

If you don't have `uv` installed yet:

```bash
pip install uv
```

### 2. Clone the repository and navigate to it

```bash
cd C:\repos\CMBUILDER
```

### 3. Create the virtual environment with Python 3.12

```bash
uv venv --python 3.12
```

### 4. Activate the virtual environment

```powershell
.venv\Scripts\Activate.ps1
```

> **Note:** If you get a script execution error, run `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` in PowerShell first.

### 5. Install the package in editable mode

```bash
uv pip install -e ".[dev]"
```

The `[dev]` extra installs additional dependencies for development and testing. If you only need the core package:

```bash
uv pip install -e .
```

### Full setup — one-liner sequence

```powershell
cd C:\repos\CMBuilder
uv venv --python 3.12
.venv\Scripts\Activate.ps1
uv pip install -e ".[dev]"
```

---

## Project Structure

```
CMBUILDER/
├── docs_reference/        # Per-module reference documentation
├── example/               # Usage examples
├── src/
│   ├── cmbuilder/         # Main package (utils.py, fom.py, viz.py)
│   ├── data/              # Input data files (e.g. BBinstances.json)
│   └── output_files/      # Auto-generated output directory for .npz, .json, and .dat files
├── test/
│   └── read.ipynb         # Usage and testing notebook
├── .gitignore
├── .python-version
├── LICENSE
├── pyproject.toml
├── README.md
└── uv.lock
```

This project is for internal development and use of packages and modules. It is not intended to be published or packaged for external distribution.

---

## Modules Overview

### `utils.py` — Data Loading & Format Conversion

The backbone of the package. Handles reading S-parameter data from multiple sources and converting between all supported formats.

**Data loading:**  
The main entry point is `DATA_TO_DF(data, id)`, which accepts a `BBinstances.json` path, a Python dictionary, or an existing DataFrame and returns a normalized long-format DataFrame. `df_filter(df, pol_in, input)` then narrows it down to a specific input polarization and port, producing the structure expected by `fom` and `visualizer`.

**Format converters:**

| Class / Function | Direction | Description |
|---|---|---|
| `json_to_npz` | `.json` → `.npz` | Exports S-parameters to the gplugins/SAX format. Handles reciprocity automatically. |
| `npz_to_json` | `.npz` → `.json` | Reconstructs a `BBinstances.json`-compatible entry from a SAX-format `.npz` file. |
| `json_to_dat` | `.json` → `.dat` | Exports S-parameters to Lumerical-style `.dat` files. |
| `dat_to_json` | `.dat` → `.json` | Parses a Lumerican `.dat` file and reconstructs the internal JSON structure. |

> For full parameter and method documentation see [`docs_reference/README_utils.md`](docs_reference/README_utils.md).

---

### `fom.py` — Figures of Merit

Provides the `fom` class, which computes standard photonic performance metrics from the S-parameter data. All metrics are derived from the magnitude columns selected at construction time via `pol_in` and `input` port.

```python
from cmbuilder.fom import fom

f = fom(data="BBinstances.json", pol_in="TE0", input=1, id="<component-id>")
```

| Method | Metric | Formula |
|---|---|---|
| `.magnitude()` | Raw linear magnitude | — |
| `.phase()` | Phase in radians | — |
| `.IL()` | Insertion loss | $-10\log_{10}(\|S_{ij}\|^2)$ |
| `.EL()` | Excess loss | $-10\log_{10}(\sum_j \|S_{ij}\|^2)$ |
| `.XT()` | Crosstalk | $-10\log_{10}(\|S_\text{cross}\|^2)$ |
| `.IB()` | Imbalance | $20\log_{10}(\|S_{i1}\| / \|S_{i2}\|)$ |

All methods return a Pandas DataFrame with columns `wavelength`, `pol_in`, `pol_out`, and the computed metric.

> For full parameter and method documentation see [`docs_reference/README_fom.md`](docs_reference/README_fom.md).

---

### `viz.py` — Interactive Visualization

Provides the `visualizer` class, which generates interactive Plotly figures for one or more components simultaneously. It uses `fom` internally to compute the requested metric before plotting.

```python
from cmbuilder.viz import visualizer

v = visualizer(data="BBinstances.json", pol_in="TE0", input=1, id=["<id-1>", "<id-2>"])
v.plot("IL")
```

The generated figure is a subplot grid with **one row per component** and **one column per S-parameter**. Each component row is labeled with its description. TE polarizations are drawn as solid lines; TM polarizations as lines with markers, with automatic point thinning for large datasets. A consistent color is assigned to each `pol_out` value across all subplots.

Accepted values for `plot`: `"magnitude"`, `"phase"`, `"IL"`, `"EL"`, `"XT"`, `"IB"`.

> For full parameter and method documentation see [`docs_reference/README_viz.md`](docs_reference/README_viz.md).

---

## JSON Schema Validation

The `test/test_serialization.py` file validates that any `BBinstances.json` file conforms to the Pydantic schema defined in `model.py`. It uses **pytest** and requires no extra configuration beyond the normal installation.

### Running the tests

From the repo root, with the virtual environment active:

```bash
# Run all validation tests with detailed output
pytest test/test_serialization.py -v

# Stop at the first failure
pytest test/test_serialization.py -v -x

# Show a short summary of passed/failed tests
pytest test/test_serialization.py -v --tb=short
```

### Pointing to a different JSON file

By default the test reads `src/data/BBinstances.json`. To validate a different file, change the `JSON_PATH` variable at the top of `test_serialization.py`:

```python
JSON_PATH = Path("src/data/BBinstances.json")  # ← change this path
```

### What is validated

The test suite is split into three classes:

**`TestFileExists`** — sanity checks before anything else runs:
- The JSON file exists at `JSON_PATH`.
- The file is syntactically valid JSON (no missing brackets, trailing commas, etc.).

**`TestSchemaValidation`** — validates every entry in the file against the `BBinstance` Pydantic model:

| Test | What it checks |
|---|---|
| `test_all_instances_pass_validation` | Every entry passes full Pydantic schema validation. Prints the exact field that fails if any entry is invalid. |
| `test_instance_count_is_positive` | The file contains at least one component (not empty). |
| `test_each_instance_has_required_fields` | Each entry has the top-level keys `cell`, `settings`, and `simulation`. |
| `test_simulation_model_has_wavelength` | `simulation.model.wavelength` exists and is not empty. |
| `test_simulation_model_has_group_delay` | `simulation.model."group delay"` exists, is a string, and is not empty. |
| `test_sparameters_have_magnitude_and_phase` | Every S-parameter leaf node (e.g. `S21 → TE0 → TE0`) has both `magnitude` and `phase` keys. |
| `test_magnitude_and_phase_lengths_match_wavelength` | The length of each `magnitude` and `phase` array matches the number of wavelength points. |

**`TestInMemoryValidation`** — tests the validation logic itself, independent of any file:

| Test | What it checks |
|---|---|
| `test_minimal_valid_instance_passes` | A correctly structured in-memory dict passes validation. |
| `test_invalid_instance_fails` | A dict missing required fields is correctly rejected. |
| `test_pydantic_raises_on_bad_settings` | `settings.length_mmi` must be an integer; passing a string raises a `ValidationError`. |
| `test_list_of_instances_passes` | `validate_content` correctly handles a list of multiple instances. |

### Expected JSON structure

For a component entry to pass all tests, its `simulation.model` block must follow this structure:

```json
{
  "simulation": {
    "model": {
      "group delay": "1.12",
      "wavelength": [1500.0, 1510.0, 1520.0],
      "S21": {
        "TE0": {
          "TE0": { "magnitude": [0.7, 0.71, 0.72], "phase": [0.0, 0.1, 0.2] },
          "TM0": { "magnitude": [0.1, 0.1, 0.1],  "phase": [0.0, 0.0, 0.0] }
        }
      }
    },
    "mode_map": { "TE0": 1, "TM0": 2 }
  }
}
```

Key constraints:
- `wavelength`, `group delay`, and at least one S-parameter block (`S11`, `S21`, ...) are required inside `model`.
- Each S-parameter block must be nested as `Sij → pol_in → pol_out → {magnitude, phase}`.
- The length of `magnitude` and `phase` must match the length of `wavelength`.
- `group delay` must be a non-empty string.
- `settings.length_mmi` must be an integer.

---

## Author

- **Creator**: Adrià Alberola Escrivà
- **Contact**: aalbesc@upv.es
- **Organization**: UPVfab
