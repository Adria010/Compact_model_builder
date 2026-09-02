from pydantic import BaseModel, Field
from typing import Dict, List
import uuid
from datetime import datetime, timezone
import json

class SParameterData(BaseModel):
    magnitude: List[float] = Field(default_factory=list)
    phase: List[float] = Field(default_factory=list)

class TXi(BaseModel):

    TE0: Dict[str, SParameterData] = Field(
        default_factory=lambda: {
            "TE0": SParameterData()
        }
    )

    TM0: Dict[str, SParameterData] = Field(
        default_factory=lambda: {
            "TM0": SParameterData()
        }
    )

class Sxy(BaseModel):

    TE0: Dict[str, TXi] = Field(
        default_factory=lambda: {
            "TE0": TXi()
        }
    )

    TM0: Dict[str, TXi] = Field(
        default_factory=lambda: {
            "TM0": TXi()
        }
    )

class Model(BaseModel):

    wavelength: List[float] = Field(default_factory=list)
    group_delay: str = Field(default="", alias="group delay")

    # S11, S21, S31, ...
    sparameters: Dict[
        str,
        Dict[str, Dict[str, SParameterData]]
    ] = Field(
        default_factory=lambda: {

            "S11": {

                "TE0": {

                    "TE0": SParameterData(),

                    "TM0": SParameterData()
                },

                "TM0": {

                    "TE0": SParameterData(),

                    "TM0": SParameterData(
                        magnitude=[
                            0.45,
                            0.51,
                            0.6
                        ],

                        phase=[
                            3.141592653589793,
                            3.141592653589793,
                            3.141592653589793
                        ]
                    )
                }
            }
        }
    )

    model_config = {
        "extra": "allow"
    }

    @classmethod
    def from_json_dict(cls, data: dict):

        wavelength = data.get("wavelength", [])

        sparams = {}

        for key, value in data.items():

            if key.startswith("S"):

                sparams[key] = value

        return cls(
            wavelength=wavelength,
            sparameters=sparams,
        )

class Simulation(BaseModel):

    model: Model = Field(default_factory=Model)

    mode_map: Dict[str, int] = Field(
        default_factory=dict
    )

class Settings(BaseModel):

    length_mmi: int

class BBinstance(BaseModel):

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4())
    )

    description: str = Field(default_factory=str)

    cell: str = Field(default_factory=str)

    settings: Settings

    technology: dict = Field(default_factory=dict)

    run: dict = Field(default_factory=dict)

    simulation: Simulation = Field(
        default_factory=Simulation
    )

    experimental: dict = Field(
        default_factory=dict
    )

    created_at: str = Field(
        default_factory=lambda:
        datetime.now(timezone.utc).isoformat()
    )

    @classmethod
    def from_json_dict(cls, data: dict):

        sim_data = data.get("simulation", {})

        model_data = sim_data.get("model", {})

        simulation = Simulation(
            model=Model.from_json_dict(model_data),
            mode_map=sim_data.get("mode_map", {}),
        )

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            description=data.get("description", ""),
            cell=data.get("cell", ""),
            settings=data.get("settings", {}),
            technology=data.get("technology", {}),
            run=data.get("run", {}),
            simulation=simulation,
            experimental=data.get("experimental", {}),
            created_at=data.get(
                "created_at",
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    
instance = BBinstance(

    description="mmi1x2 prueba 1",

    cell="mmi1x2_v1",

    settings={
        "length_mmi": 10
    },

    simulation=Simulation(

        model=Model(

            wavelength=[
                1500.0,
                1510.0,
                1520.0,
            ],

            sparameters={

                "S11": {

                    "TE0": {

                        "TE0": SParameterData(),
                        "TM0": SParameterData()
                    },

                    "TM0": {

                        "TE0": SParameterData(),
                        "TM0": SParameterData(
                            magnitude=[0.45,0.51,0.6,0.54,0.5,0.48,0.61,0.62,0.41,0.59,0.53,0.52],
                            phase=[3.141592653589793, 3.141592653589793, 3.141592653589793, 3.141592653589793, 3.141592653589793,3.141592653589793, 3.141592653589793, 3.141592653589793, 3.141592653589793, 3.141592653589793,3.141592653589793, 3.141592653589793]
                        )
                    }
                }
            })
        )
    )

if __name__ == "__main__":
    # -----------------------------
    # WRITE JSON FILE
    # -----------------------------
    print(instance.model_dump())

    with open(r"json_files\fromModel.json", "w") as f:
        json.dump(instance.model_dump(), f, indent=4)

    # instances = [instance]
    # with open(r"json_files\fromModel.json", "w") as f:
    #     json.dump([instance.model_dump() for instance in instances], f, indent=4)

    # =========================================================
    # ACCESS
    # =========================================================

    print(
        "\nhey:\n",
        instance
        .simulation
        .model
        .sparameters["S11"]["TM0"]["TM0"]
        .magnitude
    )
