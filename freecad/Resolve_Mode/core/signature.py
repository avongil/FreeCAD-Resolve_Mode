"""Geometric fingerprints and similarity scoring. Pure Python, no FreeCAD.

A fingerprint is a small JSON-safe dict describing one topological element:

    k  kind: "Edge", "Face" or "Vertex"
    t  geometry type name ("Line", "Circle", "Plane", "Cylinder", ...)
    s  size: length (edge) or area (face); None for vertices
    c  [x, y, z] centre of mass (vertex: the point)
    d  [x, y, z] unit direction: line direction, circle/cylinder axis,
       or plane normal; None when the geometry has none
    r  radius (circle, cylinder, sphere, torus major radius) or None
    o  True when ``d`` is an oriented normal (plane faces): a flipped
       normal then scores 0 instead of 1
    plane  True for a fallback fingerprint that only knows a plane
       (normal ``d`` through point ``c``); position is then scored by the
       candidate's distance to that plane
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

# Component weights. Missing components are skipped and the rest renormalized.
WEIGHTS = {"type": 0.15, "size": 0.25, "pos": 0.35, "dir": 0.15, "radius": 0.10}

# Distance (as a fraction of the model size) at which position score drops to 1/e.
POSITION_FALLOFF = 0.25


@dataclass(frozen=True)
class Candidate:
    name: str  # element name on the target shape, e.g. "Edge21"
    score: float  # 0..1


@dataclass(frozen=True)
class Verdict:
    """Outcome of matching one broken reference against the new shape."""

    status: str  # "suggest", "ambiguous" or "none"
    candidates: tuple[Candidate, ...]  # sorted best first, above the candidate threshold

    @property
    def best(self) -> Candidate | None:
        return self.candidates[0] if self.candidates else None


def dumps(fp: dict) -> str:
    return json.dumps(fp, separators=(",", ":"), sort_keys=True)


def loads(text: str) -> dict | None:
    try:
        fp = json.loads(text)
    except (TypeError, ValueError):
        return None
    return fp if isinstance(fp, dict) and "k" in fp else None


def _ratio(a, b) -> float | None:
    if a is None or b is None:
        return None
    a, b = abs(a), abs(b)
    if a == b:
        return 1.0
    hi = max(a, b)
    return min(a, b) / hi if hi > 0 else 1.0


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    return [a[0] / n, a[1] / n, a[2] / n] if n > 1e-12 else None


def score(old: dict, new: dict, model_size: float) -> float:
    """Similarity of ``new`` to ``old`` in 0..1. Different kinds score 0."""
    if old.get("k") != new.get("k"):
        return 0.0
    scale = max(model_size, 1e-6) * POSITION_FALLOFF
    parts: dict[str, float] = {}

    if old.get("t") and new.get("t"):
        parts["type"] = 1.0 if old["t"] == new["t"] else 0.3

    size = _ratio(old.get("s"), new.get("s"))
    if size is not None:
        parts["size"] = size

    oc, nc = old.get("c"), new.get("c")
    if oc is not None and nc is not None:
        od = _unit(old["d"]) if old.get("d") else None
        if old.get("plane") and od is not None:
            dist = abs(_dot(_sub(nc, oc), od))
        else:
            dist = _norm(_sub(nc, oc))
        parts["pos"] = math.exp(-dist / scale)

    od, nd = old.get("d"), new.get("d")
    if od and nd:
        ou, nu = _unit(od), _unit(nd)
        if ou and nu:
            dot = max(-1.0, min(1.0, _dot(ou, nu)))
            if old.get("o") and new.get("o") and not old.get("plane"):
                parts["dir"] = max(0.0, dot)
            else:
                parts["dir"] = abs(dot)
    elif od or nd:
        parts["dir"] = 0.5

    radius = _ratio(old.get("r"), new.get("r"))
    if radius is not None:
        parts["radius"] = radius
    elif old.get("r") is not None or new.get("r") is not None:
        parts["radius"] = 0.3

    total = sum(WEIGHTS[k] for k in parts)
    if total <= 0:
        return 0.0
    return sum(WEIGHTS[k] * v for k, v in parts.items()) / total


def classify(
    scored: list[tuple[str, float]],
    confident: float = 0.80,
    margin: float = 0.08,
    minimum: float = 0.55,
) -> Verdict:
    """Turn raw ``(name, score)`` pairs into a verdict.

    - suggest: the best is at least ``confident`` and leads the runner-up by
      at least ``margin``
    - ambiguous: one or more candidates reach ``minimum`` but none is clear
    - none: nothing reaches ``minimum``
    """
    ranked = sorted(scored, key=lambda p: (-p[1], p[0]))
    cands = tuple(Candidate(n, s) for n, s in ranked if s >= minimum)
    if not cands:
        return Verdict("none", ())
    best = cands[0].score
    runner = cands[1].score if len(cands) > 1 else 0.0
    if best >= confident and best - runner >= margin:
        return Verdict("suggest", cands)
    return Verdict("ambiguous", cands)
