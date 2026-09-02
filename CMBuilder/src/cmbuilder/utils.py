from __future__ import annotations
import numpy as np
import re
import pandas as pd
from pathlib import Path
import json
from typing import Union

__all__ = ["DATA_TO_DF","df_filter","json_to_npz","npz_to_json","json_to_dat","dat_to_json"]

# PATH
base_path = Path(__file__).resolve().parent.parent
output_dir1 = base_path/'output_files'
output_dir1.mkdir(parents = True, exist_ok = True)
file_path1 = output_dir1

'''
Given an ID and the path to the json file, this function saves in memory a diccionary with 
the data of the component with this ID stored in BBinstances.json in data
'''
def _cm_json_to_dict(file, target_id, visualizer = None):
    import ijson
    dictionary = None
    with open(file,"r",encoding ="utf-8") as f:
        objects = ijson.items(f,"item")
        for object in objects:
            if object.get("id") == target_id:
                dictionary = object
                break
    if dictionary is None:
        raise ValueError(f"No object with id={target_id} was found")
    if visualizer == None:
        model = dictionary['simulation']['model']
        return model
    else:
        return dictionary["description"]


'''
Given a dictionary, this function returs a dataframe saved in memory
'''
def _cm_dict_to_df(dictionary):
    wavelengths = dictionary["wavelength"]
    pol_in_set = set()
    pol_out_set = set()
    for spar, spar_data in dictionary.items():
        if spar == "wavelength" or not isinstance(spar_data, dict):
            continue
        for pol_in, pol_in_data in spar_data.items():
            pol_in_set.add(pol_in)
            for pol_out in pol_in_data.keys():
                pol_out_set.add(pol_out)
    pol_in_list = sorted(pol_in_set)
    pol_out_list = sorted(pol_out_set)
    rows = []
    for pol_in in pol_in_list:
        for pol_out in pol_out_list:
            for i, wl in enumerate(wavelengths):
                row = {
                    "wavelength": wl,
                    "pol_in": pol_in,
                    "pol_out": pol_out
                }
                for spar, spar_data in dictionary.items():
                    if spar == "wavelength" or not isinstance(spar_data, dict):
                        continue
                    pol_in_block = spar_data.get(pol_in, {})
                    pol_out_block = pol_in_block.get(pol_out, {})
                    mag = pol_out_block.get("magnitude", [])
                    ph = pol_out_block.get("phase", [])
                    mag_val = mag[i] if len(mag) > i else np.nan
                    ph_val = ph[i] if len(ph) > i else np.nan
                    row[f"{spar}_magnitude"] = mag_val
                    row[f"{spar}_phase"] = ph_val
                rows.append(row)
    return pd.DataFrame(rows)

'''
Given a json file, a dictionary or a pandas dataframe, this function uses _cm_json_to_dict and _cm_dict_to_df to return a dataframe
'''
def DATA_TO_DF(data, id = None):
    if isinstance(data,(str,Path)):
        file = Path(data)
        if file.suffix == ".json":
            dictionary = _cm_json_to_dict(file = data, target_id = id)
            dataframe = _cm_dict_to_df(dictionary = dictionary)
        else:
            raise ValueError(f"File format not supported: {file.suffix} /n Only supported file format: .json")
    elif isinstance(data,dict):
        dataframe = _cm_dict_to_df(dictionary = data)
    elif isinstance(data, pd.DataFrame):
        dataframe = data
    else:
        raise TypeError("Unsupported input type. Valid data types: json,dict,dataframe")
    # Falta la validación del df
    return dataframe

'''
Given a pandas dataframe, this function filters all the columns that do not correspond with the input and polarization given.
It returns the necessary a df with the structure to be used in visualizer or fom module
'''
def df_filter(df,pol_in,input):
    df_filtered = df[df["pol_in"] == pol_in]
    # Select S-parameter columns corresponding to input port 
    S_columns = [col for col in df.columns if col.startswith("S") and col.split("_")[0][-1] == str(input)]
    final_columns = ["wavelength", "pol_in", "pol_out"] + S_columns
    df_final = df_filtered[final_columns].reset_index(drop=True)
    return df_final, S_columns


"""
Parser for S-parameter JSON files into the .npz format compatible with
gplugins/SAX (gdsfactory ecosystem).

Input JSON convention:
    "Sij": {
        "pol_in": {          <- INPUT polarization (j)
            "pol_out": {}    <- OUTPUT polarization (i)
        }
    }

where i = output port index, j = input port index.

Generated key in the .npz:
    "oi_mmode_out,oj_mmode_in"

Reciprocity:
    Sji is only added if it does NOT already exist as a key in the JSON.

Basic usage:
    from sparam_parser import SParamParser

    parser = SParamParser("data.json")
    npz_path = parser.save_npz("a3275604-4aee-42d1-b241-1a7e762dc16a")

    arrays = parser.to_arrays("a3275604-4aee-42d1-b241-1a7e762dc16a")
    print(parser.list_ids())
"""
class json_to_npz:
    """
    Converts entries from an S-parameter JSON into the .npz format
    expected by gplugins/SAX: keys of the form
    "oOUT_mmodeOUT,oIN_mmodeIN".

    Parameters
    ----------
    source : str | Path | list | dict
        Path to a JSON file, a list of entries, or a single entry.
        The input must follow the correct format, so it is recommended
        to use the components included in BBinstances.json.

    wavelength_unit : str
        Wavelength unit used in the JSON: "nm" (default) or "um".
        If "nm" is provided, values are divided by 1000 to convert
        them to µm (the unit expected by SAX).
    """

    def __init__(self,source: Union[str, Path, list, dict],wavelength_unit: str = "nm",):
        self._wl_unit = wavelength_unit.lower()
        self._entries: dict[str, dict] = {}  # id 
        self._load(source)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _check_id(self, component_id: str) -> None:
        if component_id not in self._entries:
            available = "\n  ".join(self._entries.keys())
            raise KeyError(
                f"ID '{component_id}' not found. Available IDs:\n  {available}"
            )

    @staticmethod
    def _normalize_mode_map(mode_map: dict[str, int]) -> dict[str, int]:
        """
        gplugins uses 0-based mode indices (@0, @1, ...).
        If the mode_map in the JSON uses 1-based indexing (TE0->1, TM0->2),
        it converts them automatically.
        """
        values = list(mode_map.values())
        if values and min(values) >= 1:
            return {k: v - 1 for k, v in mode_map.items()}
        return mode_map

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load(self, source: Union[str, Path, list, dict]) -> None:
        if isinstance(source, (str, Path)):
            with open(source, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = source

        if isinstance(data, dict):
            data = [data]

        for entry in data:
            eid = entry.get("id")
            if eid is None:
                raise ValueError(f"Input without an 'id' field: {entry}")
            self._entries[eid] = entry

    # ------------------------------------------------------------------
    # API 
    # ------------------------------------------------------------------
    def list_ids(self) -> list[str]:
        # Returns the list of IDs available in the JSON
        return list(self._entries.keys())

    def get_entry(self, component_id: str) -> dict:
        # Returns the full component entry by its ID.
        self._check_id(component_id)
        return self._entries[component_id]

    def to_arrays(self, component_id: str) -> dict[str, np.ndarray]:
        """
        Converts a component into a dictionary of NumPy arrays compatible with
        np.savez(**arrays).

        Expected JSON structure:
            "Sij": {
                "pol_in": {          <- first level: input polarization
                    "pol_out": {}     <- second level: output polarization
                }
            }

        i = output port, j = input port (matrix notation).

        Returns
        -------
        dict with key "wavelengths" (µm) and keys of the form
        "oi_mmode_out,oj_mmode_in".
        """

        self._check_id(component_id)
        entry = self._entries[component_id]
        model = entry["simulation"]["model"]
        mode_map: dict[str, int] = entry["simulation"].get("mode_map", {})

        # Normalize mode_map to 0-based indexing if it is 1-based.
        mode_map = self._normalize_mode_map(mode_map)

        # Wavelengths
        wl_raw = np.array(model["wavelength"], dtype=float)
        wl_um  = wl_raw / 1000.0 if self._wl_unit == "nm" else wl_raw
        n_wl   = len(wl_um)

        # Collect all Sij keys present in the JSON (e.g. {"S21", "S31", ...}).
        s_keys_in_json: set[str] = {k for k in model if k.startswith("S") and len(k) >= 3 and k[1:].isdigit()}

        def _skey_is_empty(skey: str) -> bool:
            # Returns True if Sij exists in the JSON but all its magnitudes are empty
            if skey not in model:
                return False  # does not exist, not applicable here
            entry = model[skey]
            if not isinstance(entry, dict):
                return True
            for pol_in_data in entry.values():
                if not isinstance(pol_in_data, dict):
                    continue
                for sp_data in pol_in_data.values():
                    if isinstance(sp_data, dict):
                        mag = sp_data.get("magnitude", [])
                        if mag and len(mag) == n_wl:
                            return False  # has at least one real data point
            return True  # all empty

        npz: dict[str, np.ndarray] = {"wavelengths": wl_um}
        # Registry of npz keys coming from real data (not reciprocal ones)
        keys_from_data: set[str] = set()

        for s_key in s_keys_in_json:
            in_modes = model[s_key]
            if not isinstance(in_modes, dict):
                continue

            indices  = s_key[1:]          # "21" -> i=2 (out), j=1 (in)
            idx_out  = indices[0]         # output port index
            idx_in   = indices[1]         # input port index
            port_out = f"o{idx_out}"      # "o2"
            port_in  = f"o{idx_in}"       # "o1"

            # Reciprocal key in the JSON: Sji
            s_key_recip = f"S{idx_in}{idx_out}"
            # Apply reciprocal if Sji does not exist, or if it exists but is empty
            recip_exists_in_json = (s_key_recip in s_keys_in_json and not _skey_is_empty(s_key_recip))

            # First level: INPUT polarization
            for mode_in_name, out_modes in in_modes.items():
                if not isinstance(out_modes, dict):
                    continue
                mode_in_num = mode_map.get(mode_in_name)
                if mode_in_num is None:
                    continue

                # Second level: OUTPUT polarization
                for mode_out_name, sp_data in out_modes.items():
                    if not isinstance(sp_data, dict):
                        continue
                    mode_out_num = mode_map.get(mode_out_name)
                    if mode_out_num is None:
                        continue

                    mag   = sp_data.get("magnitude", [])
                    phase = sp_data.get("phase", [])

                    # Ignore empty entries or incorrect length
                    if not mag or len(mag) != n_wl:
                        continue
                    if not phase or len(phase) != n_wl:
                        phase = [0.0] * n_wl

                    S = np.array(mag) * np.exp(1j * np.array(phase))

                    # Direct key: "oi@mode_out,oj@mode_in"
                    key = f"{port_out}_m{mode_out_num},{port_in}_m{mode_in_num}"
                    npz[key] = S
                    keys_from_data.add(key)

                    # Reciprocal only if Sji does NOT exist in the JSON
                    if not recip_exists_in_json:
                        key_recip = f"{port_in}_m{mode_in_num},{port_out}_m{mode_out_num}"
                        if key_recip not in keys_from_data:
                            npz[key_recip] = S

        if len(npz) == 1:
            raise ValueError(f"No valid S-parameters found for id='{component_id}'. Check that 'magnitude' entries are not empty.")
        return npz

    def save_npz(self, component_id: str, output_dir: Union[str, Path] = file_path1, filename: str | None = None,) -> Path:
        """
        Saves the .npz file to disk and returns its Path. If no path is specified,
        it is automatically saved in the output_dir folder, and if no filename is
        provided, the name stored in the component is used.

        Parameters
        ----------
        component_id : str
            ID of the component to export.
        output_dir : str | Path
            Output directory (created if it does not exist).
        filename : str | None
            Filename without extension. Default:
            "<cell>_<short_id>.npz"
        """
        arrays = self.to_arrays(component_id)
        entry  = self._entries[component_id]

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            cell     = entry.get("cell", "component")
            short_id = component_id.split("-")[0]
            filename = f"{cell}_{short_id}"

        out_path = output_dir / f"{filename}.npz"
        np.savez(out_path, **arrays)
        return out_path

    def save_npz_all(self, output_dir: Union[str, Path] = file_path1,) -> list[Path]:
        """
        Exports all components from the JSON into individual .npz files.

        Returns
        -------
        List of generated Paths.
        """
        paths = []
        for eid in self._entries:
            try:
                p = self.save_npz(eid, output_dir=output_dir)
                paths.append(p)
            except ValueError as e:
                print(f"[WARN] Skipping id='{eid}': {e}")
        return paths

    def summary(self, component_id: str) -> None:
        # Prints a readable summary of the .npz file that would be generated
        self._check_id(component_id)
        arrays = self.to_arrays(component_id)
        entry  = self._entries[component_id]
        wl = arrays["wavelengths"]

        print(f"ID      : {component_id}")
        print(f"Cell    : {entry.get('cell', 'N/A')}")
        print(f"Settings: {entry.get('settings', {})}")
        print(f"λ range : {wl[0]:.4f} – {wl[-1]:.4f} µm  ({len(wl)} puntos)")
        print(f"{'Clave S-param':40s}  |S| min   max   mean")
        print("-" * 70)
        for k, v in arrays.items():
            if k == "wavelengths":
                continue
            m = np.abs(v)
            print(f"  {k:38s}  {m.min():.3f}  {m.max():.3f}  {m.mean():.3f}")

'''
Given a npz file, this function returns a json with the rquired structure to use the rest of classes and functions
'''
def npz_to_json(
    source: Union[str, Path, np.lib.npyio.NpzFile, dict],
    mode_map: dict[str, int] | None = None,
    wavelength_unit_out: str = "nm",
    component_id: str | None = None,
    cell: str | None = None,
    settings: dict | None = None,
    output_dir: Union[str, Path] = file_path1, 
    filename: str | None = None
) -> dict:
    """
    Converts a .npz file (SAX/gplugins format) back to the original JSON
    structure used by BBinstances.json.

    The .npz is expected to contain:
      - "wavelengths"          : 1-D array in µm
      - "oOUT_mMODE,oIN_mMODE" : complex S-parameter arrays

    Parameters
    ----------
    source : str | Path | NpzFile | dict
        Path to a .npz file, an already-loaded NpzFile, or a plain dict
        (as returned by parser_sax.to_arrays).

    mode_map : dict[str, int] | None
        Mapping from polarization name to 0-based mode index, e.g.
        {"TE0": 0, "TM0": 1}.
        If None, generic names "mode0", "mode1", ... are used.
        The stored JSON will use 1-based indices (as the original convention).

    wavelength_unit_out : str
        Unit for wavelengths in the output JSON: "nm" (default) or "um".
        The .npz always stores wavelengths in µm; if "nm" is requested
        they are multiplied by 1000.

    component_id : str | None
        UUID to embed in the JSON entry. Auto-generated if not provided.

    cell : str | None
        Cell/component name string (e.g. "DC_50_50").

    settings : dict | None
        Arbitrary settings dict to embed.

    output_dir : str | Path | None
        If provided, the resulting dict is serialised to this path as JSON.
        If not provided, it is saved in the output_files folder

    Returns
    -------
    dict
        Full component entry compatible with BBinstances.json.
    """
    # ------------------------------------------------------------------
    # 1. Load arrays
    # ------------------------------------------------------------------
    if isinstance(source, (str, Path)):
        raw = np.load(source, allow_pickle=False)
        arrays: dict[str, np.ndarray] = {k: raw[k] for k in raw.files}
    elif isinstance(source, np.lib.npyio.NpzFile):
        arrays = {k: source[k] for k in source.files}
    elif isinstance(source, dict):
        arrays = dict(source)
    else:
        raise TypeError(
            f"Unsupported npz_source type: {type(source)}. "
            "Expected str, Path, NpzFile, or dict."
        )

    if "wavelengths" not in arrays:
        raise KeyError("'wavelengths' key not found in the .npz arrays.")

    wl_um: np.ndarray = np.asarray(arrays["wavelengths"], dtype=float)
    if wavelength_unit_out == "nm":
        wl_out = (wl_um * 1000.0).tolist()
    else:
        wl_out = wl_um.tolist()

    # ------------------------------------------------------------------
    # 2. Build reverse mode_map (0-based index -> polarization name)
    # ------------------------------------------------------------------
    all_mode_indices: set[int] = set()
    s_param_keys = [k for k in arrays if k != "wavelengths"]

    def _parse_npz_key(key: str):
        """
        Parses a key like "o2_m1,o1_m0" into
        (port_out, mode_out, port_in, mode_in).
        Returns None if the key doesn't match the expected pattern.
        """
        try:
            out_part, in_part = key.split(",")
            port_out, m_out = out_part.split("_m")
            port_in,  m_in  = in_part.split("_m")
            return port_out, int(m_out), port_in, int(m_in)
        except (ValueError, AttributeError):
            return None

    for key in s_param_keys:
        parsed = _parse_npz_key(key)
        if parsed:
            _, m_out, _, m_in = parsed
            all_mode_indices.add(m_out)
            all_mode_indices.add(m_in)

    # Build reverse map: 0-based index -> name
    if mode_map is not None:
        # Normalise to 0-based (mirrors _normalize_mode_map in parser_sax)
        values = list(mode_map.values())
        if values and min(values) >= 1:
            mode_map_0based = {k: v - 1 for k, v in mode_map.items()}
        else:
            mode_map_0based = dict(mode_map)
        reverse_mode: dict[int, str] = {v: k for k, v in mode_map_0based.items()}
    else:
        # Auto-generate generic names for all indices found
        reverse_mode = {i: f"mode{i}" for i in sorted(all_mode_indices)}
        mode_map_0based = {v: k for k, v in reverse_mode.items()}

    # mode_map for JSON uses 1-based indices (original convention)
    mode_map_1based: dict[str, int] = {
        name: idx + 1 for name, idx in mode_map_0based.items()
    }

    # ------------------------------------------------------------------
    # 3. Reconstruct model dict
    # ------------------------------------------------------------------
    model: dict = {"wavelength": wl_out}

    for key in s_param_keys:
        parsed = _parse_npz_key(key)
        if parsed is None:
            continue  # skip unrecognised keys

        port_out, mode_out_idx, port_in, mode_in_idx = parsed

        # Port index strings (e.g. "o2" -> "2")
        idx_out = port_out.lstrip("o")
        idx_in  = port_in.lstrip("o")
        s_name  = f"S{idx_out}{idx_in}"   # e.g. "S21"

        # Polarization names
        pol_out = reverse_mode.get(mode_out_idx)
        pol_in  = reverse_mode.get(mode_in_idx)
        if pol_out is None or pol_in is None:
            continue  # mode index not in map, skip gracefully

        # Complex -> magnitude + phase
        S: np.ndarray = np.asarray(arrays[key], dtype=complex)
        magnitude: list[float] = np.abs(S).tolist()
        phase: list[float]     = np.angle(S).tolist()

        # Build nested structure: model[Sij][pol_in][pol_out]
        model.setdefault(s_name, {})
        model[s_name].setdefault(pol_in, {})
        model[s_name][pol_in][pol_out] = {
            "magnitude": magnitude,
            "phase":     phase,
        }

    # ------------------------------------------------------------------
    # 4. Build full component entry
    # ------------------------------------------------------------------
    import uuid as _uuid
    entry = {
        "id":          component_id or str(_uuid.uuid4()),
        "cell":        cell or "unknown",
        "settings":    settings or {},
        "description": "",
        "simulation": {
            "mode_map": mode_map_1based,
            "model":    model,
        },
    }

    # ------------------------------------------------------------------
    # 5. Save to disk
    # ------------------------------------------------------------------
    out = Path(output_dir/filename)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump([entry], f, indent=2, ensure_ascii=False)

    return entry


def npz_dir_to_json(
    npz_dir: Union[str, Path],
    output_path: Union[str, Path],
    mode_map: dict[str, int] | None = None,
    wavelength_unit_out: str = "nm",
) -> list[dict]:
    """
    Converts every .npz file in npz_dir into a JSON entry and saves them
    all as a list in output_path (BBinstances-compatible format).
 
    Parameters
    ----------
    npz_dir : str | Path
        Directory containing .npz files.
    output_path : str | Path
        Destination JSON file.
    mode_map : dict[str, int] | None
        Shared mode_map for all files (see npz_to_json).
    wavelength_unit_out : str
        "nm" or "um".
 
    Returns
    -------
    List of entry dicts (also written to output_path).
    """
    npz_dir = Path(npz_dir)
    entries = []
    for npz_file in sorted(npz_dir.glob("*.npz")):
        # Derive cell name and a deterministic ID from the filename
        # Expected filename pattern: "CellName_shortID.npz"
        stem = npz_file.stem          # e.g. "DC_50_50_a3275604"
        parts = stem.rsplit("_", 1)
        cell     = parts[0] if len(parts) == 2 else stem
        short_id = parts[1] if len(parts) == 2 else stem
 
        entry = npz_to_json(
            npz_source=npz_file,
            mode_map=mode_map,
            wavelength_unit_out=wavelength_unit_out,
            cell=cell,
            component_id=short_id,
        )
        entries.append(entry)
 
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
 
    return entries

'''
Given a json file, this function returns a .dat file ready to be used for circuit-level simulations with Lumerical
'''
def json_to_dat(
    source: Union[str, Path, list, dict],
    component_id: str,
    output_dir: Union[str, Path] = file_path1, 
    filename: str | None = None
) -> Path:
    """
    Saves a .dat file from a BBinstances-style JSON entry.

    One block is written per (Sij, pol_in, pol_out) combination.

    Header format:
        ('port out', 'pol_in', mode_num_in, 'port in', mode_num_out, 'transmission', group_delay)

    Where mode numbers come from simulation["mode_map"].
    If no group delay is present in model, the literal 'group delay' is used.
    Empty magnitude/phase → -100.0 dB / 0.0 rad.

    Parameters
    ----------
    json_source : str | Path | list | dict
        Path to a BBinstances JSON file, a list of entries, or a single entry dict.
    component_id : str
        ID of the component to export.
    output_path : str | Path | None
        - None      → next to JSON file (or CWD) as "<short_id>.dat"
        - directory → inside it as "<short_id>.dat"
        - full path → used as-is (extension forced to .dat)

    Returns
    -------
    Path  Absolute path of the written .dat file.
    """

    # ------------------------------------------------------------------
    # 1. Load JSON and locate the entry by ID
    # ------------------------------------------------------------------
    source_path: Path | None = None

    if isinstance(source, (str, Path)):
        source_path = Path(source).resolve()
        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    elif isinstance(source, dict):
        data = [source]
    elif isinstance(source, list):
        data = source
    else:
        raise TypeError(
            f"Unsupported json_source type: {type(source)}. "
            "Expected str, Path, list, or dict."
        )

    entry = next((item for item in data if item.get("id") == component_id), None)
    if entry is None:
        available = [item.get("id") for item in data]
        raise KeyError(f"ID '{component_id}' not found. Available IDs: {available}")

    simulation = entry["simulation"]
    model      = simulation["model"]

    # mode_map lives in simulation: {"TE0": 1, "TM0": 2, "TE1": 3, "TM1": 4}
    mode_map: dict[str, int] = simulation.get("mode_map", {})

    # ------------------------------------------------------------------
    # 2. Group delay (optional scalar in model)
    # ------------------------------------------------------------------
    gd_raw = model.get("group delay", model.get("group_delay", None))
    if gd_raw is not None:
        try:
            group_delay_str = str(float(gd_raw))
        except (ValueError, TypeError):
            group_delay_str = f"'{gd_raw}'"
    else:
        group_delay_str = "'group delay'"   # literal fallback when not present

    # ------------------------------------------------------------------
    # 3. Resolve output path
    # ------------------------------------------------------------------
    default_stem = component_id.split("-")[0]

    if output_dir is None:
        base = source_path.parent if source_path else Path.cwd()
        out  = base / f"{default_stem}.dat"
    else:
        out = Path(output_dir/filename)
        if out.is_dir() or not out.suffix:
            out = out / f"{default_stem}.dat"
        else:
            out = out.with_suffix(".dat")

    out.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 4. Wavelengths
    # ------------------------------------------------------------------
    wavelengths = np.array(model.get("wavelength", []), dtype=float)
    n_wl = len(wavelengths)
    if n_wl == 0:
        raise ValueError("No wavelength data found in model.")

    # ------------------------------------------------------------------
    # 5. Collect and sort S-parameter keys
    # ------------------------------------------------------------------
    s_keys = sorted(
        k for k in model
        if k.startswith("S") and len(k) >= 3 and k[1:].isdigit()
    )

    # ------------------------------------------------------------------
    # 6. Write .dat — one block per (Sij, pol_in, pol_out)
    # ------------------------------------------------------------------
    with open(out, "w") as f:
        for s_key in s_keys:
            s_data = model[s_key]
            if not isinstance(s_data, dict):
                continue

            idx_out  = s_key[1]           # "2" from "S21"
            idx_in   = s_key[2]           # "1" from "S21"
            port_out = f"port {idx_out}"
            port_in  = f"port {idx_in}"

            for pol_in, pol_in_data in s_data.items():
                if not isinstance(pol_in_data, dict):
                    continue
                mode_num_in = mode_map.get(pol_in, 1)

                for pol_out, sp_data in pol_in_data.items():
                    if not isinstance(sp_data, dict):
                        continue
                    mode_num_out = mode_map.get(pol_out, 1)

                    mag   = sp_data.get("magnitude", [])
                    phase = sp_data.get("phase", [])

                    # --- Header ---
                    header = (
                        f"('{port_out}', '{pol_in}', {mode_num_in}, "
                        f"'{port_in}', {mode_num_out}, 'transmission', {group_delay_str})"
                    )
                    f.write(header + "\n")
                    f.write(f"({n_wl}, 3)\n")

                    # --- Data rows ---
                    for i in range(n_wl):
                        wl = wavelengths[i]

                        mag_val = float(mag[i]) if (mag and i < len(mag) and mag[i] is not None) else 0.0
                        ph      = float(phase[i]) if (phase and i < len(phase)) else 0.0

                        f.write(f"{wl:.6f} {mag_val:.6f} {ph:.6f}\n")

    return out.resolve()

'''
Given a dat file it returns a json with the structure required to use the other functions and classes
'''
def dat_to_json(
    source: Union[str, Path],
    mode_map: dict[str, int] = {"TE0": 1, "TM0": 2, "TE1": 3, "TM1": 4},
    component_id: str | None = None,
    cell: str | None = None,
    description: str = "",
    settings: dict | None = None,
    output_dir: Union[str, Path] = file_path1, 
    filename: str | None = None
) -> dict:
    """
    Converts a .dat file (generated by save_dat_from_json) back to a
    BBinstances-style JSON entry.

    .dat block format:
        ('port out', 'pol_in', mode_num_in, 'port in', mode_num_out, 'transmission', group_delay)
        (n_wl, 3)
        wavelength(nm)   magnitude(dB)   phase(rad)
        ...

    Parameters
    ----------
    dat_source : str | Path
        Path to the .dat file.

    mode_map : dict[str, int]
        Mapping from polarization name to mode number (1-based), e.g.
        {"TE0": 1, "TM0": 2, "TE1": 3, "TM1": 4}.
        Used to convert mode numbers back to polarization names.

    component_id : str | None
        UUID for the JSON entry. Auto-generated if not provided.

    cell : str | None
        Cell/component name. Defaults to the .dat filename stem.

    description : str
        Free-text description to embed.

    settings : dict | None
        Arbitrary settings dict to embed.

    output_path : str | Path | None
        - None      → saved next to the .dat file as "<stem>.json"
        - directory → saved inside it as "<stem>.json"
        - full path → used as-is (extension forced to .json)

    Returns
    -------
    dict
        Full component entry compatible with BBinstances.json.
    """

    dat_path = Path(source).resolve()
    if not dat_path.exists():
        raise FileNotFoundError(f".dat file not found: {dat_path}")

    # ------------------------------------------------------------------
    # 1. Build reverse mode map: mode_number (int) -> pol_name (str)
    # ------------------------------------------------------------------
    reverse_mode: dict[int, str] = {v: k for k, v in mode_map.items()}

    # ------------------------------------------------------------------
    # 2. Parse the .dat file into blocks
    # ------------------------------------------------------------------
    # Header regex:
    # ('port X', 'POL_IN', mode_in, 'port Y', mode_out, 'transmission', gd)
    header_re = re.compile(
        r"\(\s*'port\s+(\w+)'\s*,\s*'(\w+)'\s*,\s*(\d+)\s*,"
        r"\s*'port\s+(\w+)'\s*,\s*(\d+)\s*,\s*'transmission'\s*,\s*(.+?)\s*\)"
    )

    model: dict = {}
    wavelengths_global: list[float] | None = None
    group_delay_val: str | None = None

    with open(dat_path, "r") as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        m = header_re.match(line)
        if m is None:
            i += 1
            continue

        idx_out    = m.group(1)          # "1", "2", "3", ...
        pol_in     = m.group(2)          # "TE0", "TM0", ...
        # mode_num_in = int(m.group(3))  # not needed; pol_in is already the name
        idx_in     = m.group(4)
        mode_num_out = int(m.group(5))
        gd_raw     = m.group(6).strip()

        # Decode group delay
        if group_delay_val is None:
            # Strip surrounding quotes if it is a string literal
            if gd_raw.startswith("'") and gd_raw.endswith("'"):
                group_delay_val = gd_raw[1:-1]   # e.g. "group delay"
            else:
                group_delay_val = gd_raw          # numeric string e.g. "1.12"

        # Recover pol_out from mode_num_out
        pol_out = reverse_mode.get(mode_num_out)
        if pol_out is None:
            # Unknown mode number — skip block
            i += 1
            continue

        s_name = f"S{idx_out}{idx_in}"  # e.g. "S21"

        # Next line: size "(n_wl, 3)" — skip it, we count data rows directly
        i += 1
        if i >= len(lines):
            break
        # skip size line
        i += 1

        # Read data rows until next header or EOF
        wl_list  : list[float] = []
        mag_list : list[float] = []
        ph_list  : list[float] = []

        while i < len(lines):
            row = lines[i].strip()
            if header_re.match(row):
                break                    # next block starts
            parts = row.split()
            if len(parts) == 3:
                try:
                    wl  = float(parts[0])
                    mag = float(parts[1])
                    ph  = float(parts[2])
                except ValueError:
                    i += 1
                    continue

                wl_list.append(wl)
                mag_list.append(mag)
                ph_list.append(ph)
            i += 1

        # Store wavelengths (same for all blocks)
        if wavelengths_global is None and wl_list:
            wavelengths_global = wl_list

        # Build nested model structure: model[Sij][pol_in][pol_out]
        model.setdefault(s_name, {})
        model[s_name].setdefault(pol_in, {})
        model[s_name][pol_in][pol_out] = {
            "magnitude": mag_list,
            "phase":     ph_list,
        }

    # ------------------------------------------------------------------
    # 3. Add wavelength (and optional group delay) to model
    # ------------------------------------------------------------------
    final_model: dict = {}

    # group delay goes first if it's a real numeric value
    if group_delay_val is not None and group_delay_val != "group delay":
        final_model["group delay"] = group_delay_val

    final_model["wavelength"] = wavelengths_global or []

    # Add S-param blocks sorted
    for k in sorted(model.keys()):
        final_model[k] = model[k]

    # ------------------------------------------------------------------
    # 4. Build full entry
    # ------------------------------------------------------------------
    import uuid as _uuid
    entry = {
        "id":          component_id or str(_uuid.uuid4()),
        "description": description,
        "cell":        cell or dat_path.stem,
        "settings":    settings or {},
        "technology":  {},
        "run":         {},
        "simulation": {
            "model":    final_model,
            "mode_map": mode_map,
        },
        "experimental": {},
    }

    # ------------------------------------------------------------------
    # 5. Save to disk
    # ------------------------------------------------------------------
    out = Path(output_dir/filename)
    if out.is_dir() or not out.suffix:
        out = out / f"{dat_path.stem}.json"
        
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump([entry], f, indent=4, ensure_ascii=False)

    return entry
