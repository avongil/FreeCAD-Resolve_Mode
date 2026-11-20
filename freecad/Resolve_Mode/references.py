"""Finding, fingerprinting and relinking PartDesign element references.

Console-safe: uses FreeCAD and Part only, never FreeCADGui or Qt.

A *reference* is one sub-element entry ("Edge14", "Face7", ...) inside an
``App::PropertyLinkSub*`` property of a PartDesign feature or sketch, e.g. a
fillet's ``Base`` edges, a pocket's ``UpToFace`` or a sketch's
``AttachmentSupport``. FreeCAD marks an entry whose element vanished with a
leading ``?`` (``?Edge14``).

While the model is healthy, the geometry of every referenced element is
stored as a fingerprint in a hidden property on the referencing object, so a
broken reference can later be matched against the elements that exist now.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import dataclass

import FreeCAD as App

from . import preferences as prefs
from .core import signature as sig

SIGNATURE_PROP = "ResolveModeSignatures"
SIGNATURE_GROUP = "ResolveMode"
# Hidden | Output | NoRecompute: invisible, and writing it never touches the object.
_SIGNATURE_ATTR = 4 | 8 | 16

KINDS = ("Edge", "Face", "Vertex")
_ELEMENT_RE = re.compile(r"^(Edge|Face|Vertex)(\d+)$")


@dataclass(frozen=True)
class Ref:
    """One sub-element entry of a link property."""

    doc: str
    obj: str  # referencing object Name
    prop: str  # property name, e.g. "Base"
    group: int  # index of the (target, subs) group in the property
    slot: int  # index of the sub inside that group
    target: str  # linked object Name
    sub: str  # the entry as stored, e.g. "?Edge14"
    prefix: str  # dotted path before the element, usually ""
    element: str  # "Edge14"
    kind: str  # "Edge", "Face" or "Vertex"
    broken: bool  # element no longer exists on the target
    blocked: bool  # target itself failed to recompute; fix it first

    @property
    def key(self) -> str:
        return f"{self.prop}|{self.target}|{self.element}"

    @property
    def broken_key(self) -> str:
        return f"{self.prop}|{self.target}|?{self.element}"

    def resolve(self):
        doc = App.getDocument(self.doc)
        return doc.getObject(self.obj), doc.getObject(self.target)


@dataclass
class Issue:
    """A broken reference with its match result."""

    ref: Ref
    fingerprint: dict | None
    from_plane: bool  # fingerprint guessed from the sketch placement
    verdict: sig.Verdict | None  # None when blocked or nothing to match against


# --------------------------------------------------------------------------
# Scope and property access


def in_scope(obj) -> bool:
    """PartDesign features, and anything living inside a PartDesign Body."""
    tid = obj.TypeId
    if tid == "PartDesign::Body":
        return False
    if tid.startswith("PartDesign::") or tid == "Sketcher::SketchObject":
        return True
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        return False
    return parent is not None and parent.TypeId == "PartDesign::Body"


def link_properties(obj) -> list[str]:
    out = []
    for name in obj.PropertiesList:
        if name == SIGNATURE_PROP:
            continue
        try:
            tid = obj.getTypeIdOfProperty(name)
        except Exception:
            continue
        if tid.startswith("App::PropertyLinkSub"):
            out.append(name)
    return out


def _is_list_prop(obj, prop: str) -> bool:
    return "LinkSubList" in obj.getTypeIdOfProperty(prop)


def read_groups(obj, prop: str) -> list[tuple[object, list[str]]]:
    """A link property as ``[(target, [sub, ...]), ...]``."""
    try:
        value = getattr(obj, prop)
    except Exception:
        return []
    if not value:
        return []
    if _is_list_prop(obj, prop):
        groups = []
        for entry in value:
            target, subs = entry[0], entry[1]
            if isinstance(subs, str):
                subs = [subs]
            groups.append((target, list(subs) or [""]))
        return groups
    target, subs = value[0], value[1]
    if isinstance(subs, str):
        subs = [subs]
    return [(target, list(subs) or [""])]


def write_groups(obj, prop: str, groups) -> None:
    if _is_list_prop(obj, prop):
        setattr(obj, prop, [(t, tuple(subs)) for t, subs in groups])
    else:
        target, subs = groups[0]
        setattr(obj, prop, (target, list(subs)))


def _split(sub: str) -> tuple[str, str, bool]:
    """'?Edge14' -> ('', 'Edge14', True); 'Pad.Face3' -> ('Pad.', 'Face3', False)."""
    marked = "?" in sub
    clean = sub.replace("?", "")
    cut = clean.rfind(".")
    return clean[: cut + 1], clean[cut + 1 :], marked


def target_shape(target, prefix: str = ""):
    """The shape element names are resolved against, or None."""
    try:
        if prefix:
            import Part

            shape = Part.getShape(target, prefix, needSubElement=False)
        else:
            shape = target.Shape
    except Exception:
        return None
    if shape is None or shape.isNull():
        return None
    return shape


def element_exists(shape, element: str) -> bool:
    m = _ELEMENT_RE.match(element)
    if not m or shape is None:
        return False
    try:
        return 1 <= int(m.group(2)) <= shape.countElement(m.group(1))
    except Exception:
        return False


def _target_ok(target) -> bool:
    try:
        return target.isValid()
    except Exception:
        return False


def iter_refs(obj):
    """Every Edge/Face/Vertex entry in the object's link properties."""
    doc = obj.Document.Name
    for prop in link_properties(obj):
        for gi, (target, subs) in enumerate(read_groups(obj, prop)):
            if target is None:
                continue
            ok = _target_ok(target)
            shape = None
            for si, sub in enumerate(subs):
                prefix, element, marked = _split(sub)
                m = _ELEMENT_RE.match(element)
                if not m:
                    continue
                if shape is None:
                    shape = target_shape(target, prefix)
                exists = ok and element_exists(shape, element)
                broken = marked or not exists
                yield Ref(
                    doc=doc,
                    obj=obj.Name,
                    prop=prop,
                    group=gi,
                    slot=si,
                    target=target.Name,
                    sub=sub,
                    prefix=prefix,
                    element=element,
                    kind=m.group(1),
                    broken=broken,
                    blocked=broken and not ok,
                )


# --------------------------------------------------------------------------
# Fingerprints


def _vec(v) -> list[float]:
    return [round(v.x, 6), round(v.y, 6), round(v.z, 6)]


def fingerprint(element, kind: str) -> dict | None:
    """Fingerprint of a Part edge, face or vertex; None if it cannot be read."""
    try:
        if kind == "Vertex":
            return {"k": "Vertex", "t": "Point", "s": None, "c": _vec(element.Point), "d": None, "r": None}
        if kind == "Edge":
            fp = {"k": "Edge", "t": None, "s": round(element.Length, 6), "d": None, "r": None}
            fp["c"] = _vec(element.CenterOfMass)
            try:
                curve = element.Curve
                fp["t"] = type(curve).__name__
                if fp["t"] == "Line":
                    fp["d"] = _vec(curve.Direction)
                elif hasattr(curve, "Axis"):
                    fp["d"] = _vec(curve.Axis)
                if hasattr(curve, "Radius"):
                    fp["r"] = round(curve.Radius, 6)
            except Exception:
                pass
            return fp
        if kind == "Face":
            fp = {"k": "Face", "t": None, "s": round(element.Area, 6), "d": None, "r": None}
            fp["c"] = _vec(element.CenterOfMass)
            try:
                surf = element.Surface
                fp["t"] = type(surf).__name__
                if fp["t"] == "Plane":
                    u0, u1, v0, v1 = element.ParameterRange
                    fp["d"] = _vec(element.normalAt((u0 + u1) / 2, (v0 + v1) / 2))
                    fp["o"] = True
                elif hasattr(surf, "Axis"):
                    fp["d"] = _vec(surf.Axis)
                if hasattr(surf, "Radius"):
                    fp["r"] = round(surf.Radius, 6)
                elif hasattr(surf, "MajorRadius"):
                    fp["r"] = round(surf.MajorRadius, 6)
            except Exception:
                pass
            return fp
    except Exception:
        return None
    return None


def stored_signatures(obj) -> dict[str, str]:
    if SIGNATURE_PROP not in obj.PropertiesList:
        return {}
    try:
        return dict(getattr(obj, SIGNATURE_PROP))
    except Exception:
        return {}


def capture_object(obj) -> bool:
    """Refresh the stored fingerprints of ``obj``. Returns True if changed.

    Healthy references get a fresh fingerprint. A broken reference keeps the
    fingerprint it had while it was healthy, under a ``?`` key so a healthy
    reference later renumbered to the same name cannot overwrite it.
    """
    old = stored_signatures(obj)
    new: dict[str, str] = {}
    for ref in iter_refs(obj):
        if ref.broken:
            kept = old.get(ref.broken_key) or old.get(ref.key)
            if kept:
                new[ref.broken_key] = kept
            continue
        _, target = ref.resolve()
        shape = target_shape(target, ref.prefix)
        try:
            element = shape.getElement(ref.element)
        except Exception:
            continue
        fp = fingerprint(element, ref.kind)
        if fp is not None:
            new[ref.key] = sig.dumps(fp)
    if new == old:
        return False
    if SIGNATURE_PROP not in obj.PropertiesList:
        if not new:
            return False
        obj.addProperty(
            "App::PropertyMap",
            SIGNATURE_PROP,
            SIGNATURE_GROUP,
            "Resolve_Mode: geometry of referenced elements, used to repair broken references",
            _SIGNATURE_ATTR,
            False,
            True,
        )
    setattr(obj, SIGNATURE_PROP, new)
    return True


def capture_document(doc) -> int:
    """Refresh fingerprints for every in-scope object. Returns objects changed."""
    changed = 0
    for obj in doc.Objects:
        try:
            if in_scope(obj) and capture_object(obj):
                changed += 1
        except Exception as exc:  # one bad object must not stop the rest
            App.Console.PrintLog(f"[Resolve_Mode] capture skipped {obj.Name}: {exc}\n")
    return changed


def _plane_fingerprint(obj) -> dict | None:
    """Guess an attachment face from where the sketch currently sits."""
    try:
        if getattr(obj, "MapMode", "") != "FlatFace":
            return None
        plm = obj.Placement.multiply(obj.AttachmentOffset.inverse())
        normal = plm.Rotation.multVec(App.Vector(0, 0, 1))
    except Exception:
        return None
    return {"k": "Face", "t": "Plane", "s": None, "c": _vec(plm.Base), "d": _vec(normal), "r": None, "plane": True}


# --------------------------------------------------------------------------
# Matching


def candidates_for(ref: Ref, fp: dict) -> list[tuple[str, float]]:
    """Score every element of the right kind on the target."""
    obj, target = ref.resolve()
    shape = target_shape(target, ref.prefix)
    if shape is None:
        return []
    taken = set()
    for gi, (t, subs) in enumerate(read_groups(obj, ref.prop)):
        if t is not None and t.Name == ref.target:
            for si, sub in enumerate(subs):
                if (gi, si) != (ref.group, ref.slot):
                    taken.add(_split(sub)[1])
    size = shape.BoundBox.DiagonalLength
    elements = {"Edge": shape.Edges, "Face": shape.Faces, "Vertex": shape.Vertexes}[ref.kind]
    out = []
    for i, element in enumerate(elements, 1):
        name = f"{ref.kind}{i}"
        if name in taken:
            continue
        nfp = fingerprint(element, ref.kind)
        if nfp is not None:
            out.append((name, sig.score(fp, nfp, size)))
    return out


def analyze(ref: Ref) -> Issue:
    obj, _ = ref.resolve()
    if ref.blocked:
        return Issue(ref, None, False, None)
    stored = stored_signatures(obj)
    fp = sig.loads(stored.get(ref.broken_key) or stored.get(ref.key) or "")
    from_plane = False
    if fp is None and ref.prop == "AttachmentSupport" and ref.kind == "Face":
        fp = _plane_fingerprint(obj)
        from_plane = fp is not None
    if fp is None:
        return Issue(ref, None, False, None)
    confident, margin, minimum = prefs.thresholds()
    verdict = sig.classify(candidates_for(ref, fp), confident, margin, minimum)
    return Issue(ref, fp, from_plane, verdict)


def broken_refs(doc) -> list[Ref]:
    out = []
    for obj in doc.Objects:
        if not in_scope(obj):
            continue
        try:
            out.extend(r for r in iter_refs(obj) if r.broken)
        except Exception as exc:
            App.Console.PrintLog(f"[Resolve_Mode] scan skipped {obj.Name}: {exc}\n")
    return out


def scan(doc) -> list[Issue]:
    """All broken references in the document, analyzed, in tree order."""
    return [analyze(ref) for ref in broken_refs(doc)]


# --------------------------------------------------------------------------
# Repair


class StaleReference(RuntimeError):
    """The property changed since the reference was scanned."""


def relink(ref: Ref, element: str) -> None:
    """Point the broken entry at ``element`` on the same target object."""
    obj, _ = ref.resolve()
    if obj is None:
        raise StaleReference(ref.obj)
    groups = read_groups(obj, ref.prop)
    try:
        target, subs = groups[ref.group]
        current = subs[ref.slot]
    except IndexError as exc:
        raise StaleReference(f"{ref.obj}.{ref.prop}") from exc
    if target is None or target.Name != ref.target or _split(current)[1] != ref.element:
        raise StaleReference(f"{ref.obj}.{ref.prop}")
    subs[ref.slot] = ref.prefix + element
    write_groups(obj, ref.prop, groups)


@contextmanager
def transaction(doc, name: str):
    doc.openTransaction(name)
    try:
        yield
    except Exception:
        doc.abortTransaction()
        raise
    else:
        doc.commitTransaction()
