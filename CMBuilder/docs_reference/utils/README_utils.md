# `utils.py` — Reference Guide

This module provides all the core data-loading, filtering, and format-conversion utilities used by the rest of the package. It handles reading S-parameter data from multiple formats and converting it into the internal DataFrame structure expected by `fom` and `visualizer`.

---

## Public API (`__all__`)

```
DATA_TO_DF · df_filter · json_to_npz · npz_to_json · json_to_dat · dat_to_json
```

---

## Functions

### `DATA_TO_DF(data, id=None)`
**Universal data loader.** Accepts a JSON file path, a Python dictionary, or an existing Pandas DataFrame and returns a normalized DataFrame with columns `wavelength`, `pol_in`, `pol_out`, and one `<Sij>_magnitude` / `<Sij>_phase` column per S-parameter.

- If `data` is a `.json` path, it reads the entry matching `id` from the file.
- If `data` is a `dict`, it converts it directly.
- If `data` is already a `DataFrame`, it is returned as-is.

---

### `df_filter(df, pol_in, input)`
**DataFrame filter.** Given a full S-parameter DataFrame, it keeps only the rows corresponding to the requested input polarization (`pol_in`) and the S-parameter columns that correspond to the requested input port number (`input`).  
Returns a tuple `(filtered_df, S_columns)`.

---

## Private helpers (used internally)

### `_cm_json_to_dict(file, target_id, visualizer=None)`
Streams through a `BBinstances.json` file using `ijson` and returns the entry whose `"id"` field matches `target_id`. If `visualizer=1`, it returns the `"description"` field; otherwise it returns the full `"simulation" → "model"` block.

### `_cm_dict_to_df(dictionary)`
Converts a simulation model dictionary (with `wavelength`, `Sij → pol_in → pol_out → {magnitude, phase}` structure) into a long-format Pandas DataFrame with one row per `(wavelength, pol_in, pol_out)` combination.

---

## Classes

### `json_to_npz(source, wavelength_unit="nm")`
Converts S-parameter entries from a `BBinstances.json` into `.npz` files compatible with **gplugins / SAX** (gdsfactory ecosystem). Keys in the generated `.npz` follow the `"oOUT_mMODE_OUT,oIN_mMODE_IN"` convention.

| Method | Description |
|---|---|
| `list_ids()` | Returns all component IDs present in the loaded source. |
| `get_entry(component_id)` | Returns the raw dictionary entry for a given ID. |
| `to_arrays(component_id)` | Converts one component into a `dict` of NumPy arrays (complex S-parameters + wavelengths in µm). Reciprocal paths are added automatically if the reverse S-parameter is absent. |
| `save_npz(component_id, output_dir, filename)` | Calls `to_arrays()` and saves the result as a `.npz` file on disk. Returns the output `Path`. |
| `save_npz_all(output_dir)` | Exports every component in the source to individual `.npz` files. Returns a list of generated `Path` objects. |
| `summary(component_id)` | Prints a human-readable summary of the S-parameter arrays (key names, min / max / mean magnitudes, wavelength range). |

---

### `npz_to_json(source, mode_map, wavelength_unit_out, component_id, cell, settings, output_dir, filename)`
**Reverse converter.** Takes a `.npz` file (SAX/gplugins format) and reconstructs the `BBinstances.json`-compatible entry dict. Wavelengths are converted from µm back to nm by default. The result is saved to disk and also returned as a Python `dict`.

---

### `json_to_dat(...)` *(class)*
Converts a `BBinstances.json` entry into Lumerical-style `.dat` files, one block per `(Sij, pol_in, pol_out)` combination. The block header follows the format:  
`('port out', 'pol_in', mode_num_in, 'port in', mode_num_out, 'transmission', group_delay)`

---

### `dat_to_json(source, mode_map, component_id, cell, description, settings, output_dir, filename)`
**Reverse converter.** Parses a `.dat` file produced by `json_to_dat` and reconstructs a full `BBinstances.json`-compatible entry. Uses a `mode_map` dict (e.g. `{"TE0": 1, "TM0": 2}`) to convert numeric mode indices back to polarization names. The result is saved to disk as JSON and also returned as a `dict`.
