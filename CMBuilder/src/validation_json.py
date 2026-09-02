from typing import List, Type
from pydantic import ValidationError

def validate_content(data, model: Type, debug: bool = False) -> bool:
    """
    Validate JSON-like content using a Pydantic model.

    Parameters
    ----------
    data : dict | list
        JSON data to validate
    model : BaseModel subclass
        The Pydantic model class to validate against
    debug : bool
        If True, prints validation errors

    Returns
    -------
    bool
        True if valid, False otherwise
    """

    try:
        # Case 1: list of objects (your case)
        if isinstance(data, list):
            for i, item in enumerate(data):
                model.model_validate(item)

        # Case 2: single object
        else:
            model.model_validate(data)

        return True

    except ValidationError as e:

        if debug:
            print("❌ Validation error:")
            print(e.json(indent=4))

        return False
