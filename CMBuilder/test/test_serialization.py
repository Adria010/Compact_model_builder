"""
test_serialization.py
---------------------
Validates that BBinstances.json files conform to the Pydantic schema
defined in model.py.

Run from the repo root with:
    pytest test/test_serialization.py -v
"""

import json
import pytest
from pathlib import Path
from pydantic import ValidationError

from src.model import BBinstance, Simulation, Model, SParameterData, Settings
from src.validation_json import validate_content

# ---------------------------------------------------------------------------
# Path to your real JSON file — adjust if needed
# ---------------------------------------------------------------------------
JSON_PATH = Path("src/data/BBinstances.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> list:
    """Load a JSON file and always return a list of entries."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # BBinstances.json can be a list or a single object
    return data if isinstance(data, list) else [data]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def bbinstances_data():
    """Load the real BBinstances.json once for the whole test session."""
    if not JSON_PATH.exists():
        pytest.skip(f"JSON file not found: {JSON_PATH}")
    return load_json(JSON_PATH)


@pytest.fixture
def minimal_valid_instance() -> dict:
    """A minimal in-memory BBinstance dict that must always pass validation."""
    return {
        "description": "test component",
        "cell": "test_cell",
        "settings": {"length_mmi": 10},
        "technology": {},
        "run": {},
        "simulation": {
            "model": {
                "wavelength": [1500.0, 1510.0, 1520.0],
                "S21": {
                    "TE0": {
                        "TE0": {"magnitude": [0.7, 0.71, 0.72], "phase": [0.0, 0.1, 0.2]}
                    }
                }
            },
            "mode_map": {"TE0": 1, "TM0": 2}
        },
        "experimental": {}
    }


@pytest.fixture
def invalid_instance() -> dict:
    """A dict that is missing required fields — must always fail validation."""
    return {
        "description": "broken component",
        # 'cell' and 'settings' are missing
        "simulation": {}
    }


# ---------------------------------------------------------------------------
# Tests — file-level
# ---------------------------------------------------------------------------

class TestFileExists:

    def test_json_file_exists(self):
        """The BBinstances.json file must exist at the expected path."""
        assert JSON_PATH.exists(), (
            f"BBinstances.json not found at {JSON_PATH}. "
            "Check that the path in JSON_PATH matches your project layout."
        )

    def test_json_file_is_parseable(self):
        """The file must be valid JSON (no syntax errors)."""
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)  # raises json.JSONDecodeError if malformed
        assert data is not None


# ---------------------------------------------------------------------------
# Tests — schema validation against the real file
# ---------------------------------------------------------------------------

class TestSchemaValidation:

    def test_all_instances_pass_validation(self, bbinstances_data):
        """Every entry in BBinstances.json must pass BBinstance schema validation."""
        is_valid = validate_content(bbinstances_data, BBinstance, debug=True)
        assert is_valid, (
            "One or more entries in BBinstances.json failed Pydantic validation. "
            "Check the output above for details."
        )

    def test_instance_count_is_positive(self, bbinstances_data):
        """The file must contain at least one component."""
        assert len(bbinstances_data) > 0, "BBinstances.json is empty."

    @pytest.mark.parametrize("index", range(0, 1))  # extend range to test more entries
    def test_each_instance_has_required_fields(self, bbinstances_data, index):
        """Spot-check that key fields are present in each entry."""
        if index >= len(bbinstances_data):
            pytest.skip(f"Entry {index} does not exist in the file.")
        entry = bbinstances_data[index]
        for field in ("cell", "settings", "simulation"):
            assert field in entry, f"Entry {index} is missing required field '{field}'."

    def test_simulation_model_has_wavelength(self, bbinstances_data):
        """Every instance's simulation model must define a wavelength list."""
        for i, entry in enumerate(bbinstances_data):
            wl = entry.get("simulation", {}).get("model", {}).get("wavelength", None)
            assert wl is not None, f"Entry {i} is missing 'simulation.model.wavelength'."
            assert len(wl) > 0, f"Entry {i} has an empty wavelength list."

    def test_simulation_model_has_group_delay(self, bbinstances_data):
        """Every instance's simulation model must define a 'group delay' key."""
        for i, entry in enumerate(bbinstances_data):
            model = entry.get("simulation", {}).get("model", {})
            assert "group delay" in model, (
                f"Entry {i} is missing 'simulation.model.group delay'."
            )
            gd = model["group delay"]
            assert isinstance(gd, str) and gd.strip() != "", (
                f"Entry {i} has an empty or invalid 'group delay' value: {gd!r}."
            )

    def test_sparameters_have_magnitude_and_phase(self, bbinstances_data):
        """
        For every S-parameter block, all leaf nodes must have
        both 'magnitude' and 'phase' keys.
        """
        for i, entry in enumerate(bbinstances_data):
            model = entry.get("simulation", {}).get("model", {})
            for skey, sval in model.items():
                if not skey.startswith("S"):
                    continue
                # sval: {pol_in: {pol_out: {magnitude, phase}}}
                for pol_in, pol_in_data in sval.items():
                    for pol_out, leaf in pol_in_data.items():
                        assert "magnitude" in leaf, (
                            f"Entry {i} → {skey}[{pol_in}][{pol_out}] is missing 'magnitude'."
                        )
                        assert "phase" in leaf, (
                            f"Entry {i} → {skey}[{pol_in}][{pol_out}] is missing 'phase'."
                        )

    def test_magnitude_and_phase_lengths_match_wavelength(self, bbinstances_data):
        """
        The length of magnitude and phase arrays must match
        the number of wavelength points.
        """
        for i, entry in enumerate(bbinstances_data):
            model = entry.get("simulation", {}).get("model", {})
            n_wl = len(model.get("wavelength", []))
            for skey, sval in model.items():
                if not skey.startswith("S"):
                    continue
                for pol_in, pol_in_data in sval.items():
                    for pol_out, leaf in pol_in_data.items():
                        mag = leaf.get("magnitude", [])
                        phase = leaf.get("phase", [])
                        # Only check non-empty arrays
                        if mag:
                            assert len(mag) == n_wl, (
                                f"Entry {i} → {skey}[{pol_in}][{pol_out}]: "
                                f"magnitude has {len(mag)} points but wavelength has {n_wl}."
                            )
                        if phase:
                            assert len(phase) == n_wl, (
                                f"Entry {i} → {skey}[{pol_in}][{pol_out}]: "
                                f"phase has {len(phase)} points but wavelength has {n_wl}."
                            )


# ---------------------------------------------------------------------------
# Tests — in-memory fixtures (no file dependency)
# ---------------------------------------------------------------------------

class TestInMemoryValidation:

    def test_minimal_valid_instance_passes(self, minimal_valid_instance):
        """A correctly structured dict must pass validation."""
        is_valid = validate_content(minimal_valid_instance, BBinstance, debug=True)
        assert is_valid

    def test_invalid_instance_fails(self, invalid_instance):
        """A dict missing required fields must fail validation."""
        is_valid = validate_content(invalid_instance, BBinstance, debug=False)
        assert not is_valid

    def test_pydantic_raises_on_bad_settings(self):
        """settings.length_mmi must be an integer — passing a string should fail."""
        bad = {
            "cell": "x",
            "settings": {"length_mmi": "not_a_number"},
            "simulation": {}
        }
        with pytest.raises(ValidationError):
            BBinstance.model_validate(bad)

    def test_list_of_instances_passes(self, minimal_valid_instance):
        """validate_content must handle a list of instances correctly."""
        is_valid = validate_content([minimal_valid_instance, minimal_valid_instance], BBinstance, debug=True)
        assert is_valid
