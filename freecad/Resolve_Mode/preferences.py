"""Settings in the FreeCAD parameter store (console-safe)."""

from __future__ import annotations

import FreeCAD as App

PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/Resolve_Mode"

DEFAULT_BOOLS = {
    "AutoOpen": True,  # open the panel when a recompute leaves broken references
    "StoreSignatures": True,  # remember referenced geometry while the model is healthy
}
DEFAULT_INTS = {
    "ConfidentScore": 80,  # % needed for a suggestion
    "AmbiguityMargin": 8,  # % lead over the runner-up needed for a suggestion
    "CandidateScore": 55,  # % needed to be listed as a candidate
}


def params():
    return App.ParamGet(PARAM_PATH)


def get_bool(key: str) -> bool:
    return params().GetBool(key, DEFAULT_BOOLS[key])


def set_bool(key: str, value: bool) -> None:
    params().SetBool(key, bool(value))


def get_int(key: str) -> int:
    return params().GetInt(key, DEFAULT_INTS[key])


def set_int(key: str, value: int) -> None:
    params().SetInt(key, int(value))


def thresholds() -> tuple[float, float, float]:
    """(confident, margin, minimum) as 0..1 fractions."""
    return (
        get_int("ConfidentScore") / 100.0,
        get_int("AmbiguityMargin") / 100.0,
        get_int("CandidateScore") / 100.0,
    )
