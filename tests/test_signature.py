"""Pure-Python tests for fingerprint scoring (no FreeCAD needed)."""

import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "signature", Path(__file__).resolve().parents[1] / "freecad" / "Resolve_Mode" / "core" / "signature.py"
)
sig = importlib.util.module_from_spec(_spec)
sys.modules["signature"] = sig  # dataclasses need the module registered
_spec.loader.exec_module(sig)


def edge(c, d=(1, 0, 0), s=20.0, t="Line", r=None):
    return {"k": "Edge", "t": t, "s": s, "c": list(c), "d": list(d) if d else None, "r": r}


def plane(c, n, s=100.0):
    return {"k": "Face", "t": "Plane", "s": s, "c": list(c), "d": list(n), "r": None, "o": True}


def test_identical_scores_one():
    e = edge((10, 10, 5))
    assert sig.score(e, e, 25) == 1.0


def test_kind_mismatch_scores_zero():
    assert sig.score(edge((0, 0, 0)), plane((0, 0, 0), (0, 0, 1)), 10) == 0.0


def test_moved_edge_beats_parallel_far_edge():
    old = edge((10, 10, 5))
    moved = edge((10, 12, 5))
    far = edge((10, 0, 5))
    assert sig.score(old, moved, 25) > sig.score(old, far, 25) + 0.1


def test_flipped_plane_normal_scores_lower():
    old = plane((0, 0, 5), (0, 0, 1))
    same = plane((0, 0, 5), (0, 0, 1))
    flipped = plane((0, 0, 5), (0, 0, -1))
    assert sig.score(old, same, 20) > sig.score(old, flipped, 20)


def test_edge_direction_is_unsigned():
    old = edge((0, 0, 0), d=(1, 0, 0))
    assert sig.score(old, edge((0, 0, 0), d=(-1, 0, 0)), 20) == 1.0


def test_plane_fallback_uses_distance_to_plane():
    fb = {"k": "Face", "t": "Plane", "s": None, "c": [0, 0, 5], "d": [0, 0, 1], "r": None, "plane": True}
    on_plane_far_away = plane((50, 50, 5), (0, 0, 1))
    off_plane = plane((0, 0, 9), (0, 0, 1))
    assert sig.score(fb, on_plane_far_away, 20) > sig.score(fb, off_plane, 20)


def test_radius_matters_for_circles():
    old = edge((0, 0, 0), d=(0, 0, 1), s=31.4, t="Circle", r=5)
    same = edge((0, 0, 0), d=(0, 0, 1), s=31.4, t="Circle", r=5)
    bigger = edge((0, 0, 0), d=(0, 0, 1), s=31.4, t="Circle", r=10)
    assert sig.score(old, same, 20) > sig.score(old, bigger, 20)


def test_classify_suggest():
    v = sig.classify([("Edge1", 0.95), ("Edge2", 0.70)])
    assert v.status == "suggest" and v.best.name == "Edge1"


def test_classify_ambiguous_when_close():
    v = sig.classify([("Face1", 0.90), ("Face2", 0.88)])
    assert v.status == "ambiguous" and len(v.candidates) == 2


def test_classify_ambiguous_when_low():
    v = sig.classify([("Face1", 0.70)])
    assert v.status == "ambiguous"


def test_classify_none():
    v = sig.classify([("Face1", 0.2)])
    assert v.status == "none" and v.best is None


def test_roundtrip_json():
    e = edge((1, 2, 3))
    assert sig.loads(sig.dumps(e)) == e
    assert sig.loads("not json") is None
    assert sig.loads('{"x": 1}') is None
