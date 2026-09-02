# `fom.py` — Figures of Merit

This module exposes the `fom` class, which computes standard photonic **figures of merit** from S-parameter data. All metrics are derived from the magnitude of the S-parameter columns selected during initialization.

---

## Class `fom(data, pol_in, input, id=None)`

### Constructor parameters

| Parameter | Type | Description |
|---|---|---|
| `data` | `str / Path / dict / DataFrame` | S-parameter source (see `DATA_TO_DF` in `utils.py`). |
| `pol_in` | `str` | Input polarization to filter (e.g. `"TE0"`). |
| `input` | `int` | Input port number used to select the relevant S-columns. |
| `id` | `str / None` | Component ID, required when `data` is a JSON file path. |

During initialization, the constructor calls `DATA_TO_DF` and `df_filter` to build a filtered DataFrame (`self.df`) and stores the relevant S-parameter column names. It also pre-selects the magnitude columns of transmission sparameters (`self.S_col_mag`) — i.e., those where the output port index differs from the input port index — which are used by the figure-of-merit methods.

---

## Methods

### `.magnitude()`
Returns a DataFrame with the raw **linear magnitude** of the S-parameters. Columns: `wavelength`, `pol_in`, `pol_out`, and all `*_magnitude` S-columns for the selected input port.

---

### `.phase()`
Returns a DataFrame with the **phase** (in radians) of the S-parameters. Columns: `wavelength`, `pol_in`, `pol_out`, and all `*_phase` S-columns for the selected input port.

---

### `.IL()` — Insertion Loss
Computes the **insertion loss** for each S-parameter column using:

$$IL = -10 \cdot \log_{10}(|S_{ij}|^2) \quad [\text{dB}]$$

Returns a DataFrame where magnitude columns are renamed from `*_magnitude` to `*_IL`.

---

### `.EL()` — Excess Loss
Computes the total **excess loss** as the combined power across all relevant output ports:

$$EL = -10 \cdot \log_{10}\left(\sum_j |S_{ij}|^2\right) \quad [\text{dB}]$$

Returns a DataFrame with a single `S_EL` column alongside `wavelength`, `pol_in`, and `pol_out`.

---

### `.XT()` — Crosstalk
Computes **crosstalk**, defined as the power in the undesired output port. Valid only for structures with a coupling ratio of `k = 0` or `k = 1` (e.g. fully-crossing or fully-through devices).

The method automatically identifies which of the two magnitude columns corresponds to the weaker (cross) port by comparing their mean values, then computes:

$$XT = -10 \cdot \log_{10}(|S_{\text{cross}}|^2) \quad [\text{dB}]$$

Returns a DataFrame with a single `S_XT` column.

---

### `.IB()` — Imbalance
Computes the **power imbalance** between the two output ports. Valid only for structures with a nominal coupling ratio of `k = 0.5` (e.g. 50/50 splitters):

$$IB = 20 \cdot \log_{10}\left(\frac{|S_{i1}|}{|S_{i2}|}\right) \quad [\text{dB}]$$

Returns a DataFrame with a single `S_IB` column.
