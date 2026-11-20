"""End-to-end check inside FreeCAD: freecadcmd tests/fc_scenario.py

Builds a padded rectangle with a fillet, a sketch on a face and a pocket
up-to-face, captures fingerprints, breaks the topology, then checks the
suggestions and relinks them.
"""

import sys
from pathlib import Path

import Part  # noqa: E402

import FreeCAD as App  # noqa: E402
import freecad  # noqa: E402

# test-only: let the repo copy shadow any installed one
freecad.__path__.insert(0, str(Path(__file__).resolve().parents[1] / "freecad"))
for _m in [m for m in sys.modules if m.startswith("freecad.Resolve_Mode")]:
    del sys.modules[_m]  # FreeCAD may already have imported an installed copy

from freecad.Resolve_Mode import references as R  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def rect(sk, pts):
    for i in range(len(pts)):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % len(pts)]))


def index_of(shape, kind, pred):
    for i, e in enumerate(getattr(shape, kind + "s"), 1):
        if pred(e):
            return f"{kind}{i}"
    raise LookupError(kind)


V = App.Vector
doc = App.newDocument("RM")
doc.UndoMode = 1  # console mode has undo off by default
body = doc.addObject("PartDesign::Body", "Body")
sk = body.newObject("Sketcher::SketchObject", "Sketch")
sk.AttachmentSupport = [(body.Origin.OriginFeatures[3], "")]
sk.MapMode = "FlatFace"
rect(sk, [V(0, 0, 0), V(20, 0, 0), V(20, 10, 0), V(0, 10, 0)])
pad = body.newObject("PartDesign::Pad", "Pad")
pad.Profile = sk
pad.Length = 5
doc.recompute()

# top edge at y=10 (will vanish), top edge at y=0 (survives)
e_gone = index_of(pad.Shape, "Edge", lambda e: abs(e.CenterOfMass.y - 10) < 1e-6 and abs(e.CenterOfMass.z - 5) < 1e-6)
e_keep = index_of(pad.Shape, "Edge", lambda e: abs(e.CenterOfMass.y) < 1e-6 and abs(e.CenterOfMass.z - 5) < 1e-6)
f_top = index_of(pad.Shape, "Face", lambda f: abs(f.CenterOfMass.z - 5) < 1e-6)
f_back = index_of(pad.Shape, "Face", lambda f: abs(f.CenterOfMass.y - 10) < 1e-6)

fil = body.newObject("PartDesign::Fillet", "Fillet")
fil.Base = (pad, [e_keep, e_gone])
fil.Radius = 1
sk2 = body.newObject("Sketcher::SketchObject", "Sketch001")
sk2.AttachmentSupport = [(pad, f_back)]
sk2.MapMode = "FlatFace"
doc.recompute()
check(fil.isValid() and sk2.isValid(), "model healthy before break")
check(not R.broken_refs(doc), "no broken refs before break")
n = R.capture_document(doc)
check(n == 2, f"captured fingerprints on 2 objects (got {n})")
check(R.capture_document(doc) == 0, "second capture is a no-op")
check("Touched" not in fil.State, "capturing does not touch the feature")


# Break: redraw the back of the profile 2 mm further out. The new lines have new
# geometry ids, so FreeCAD cannot map the old back face / back top edge to them.
def move_back(sketch, y):
    for _ in range(3):
        sketch.delGeometry(1)
    sketch.addGeometry(Part.LineSegment(V(20, 0, 0), V(20, y, 0)))
    sketch.addGeometry(Part.LineSegment(V(20, y, 0), V(0, y, 0)))
    sketch.addGeometry(Part.LineSegment(V(0, y, 0), V(0, 0, 0)))


move_back(sk, 12)
doc.recompute()
R.capture_document(doc)  # what the observer does after every recompute

issues = R.scan(doc)
for i in issues:
    r = i.ref
    print(
        "  issue",
        r.obj,
        r.prop,
        r.sub,
        "blocked" if r.blocked else "",
        i.verdict.status if i.verdict else None,
        [(c.name, round(c.score * 100)) for c in (i.verdict.candidates if i.verdict else ())][:3],
    )
fil_issue = next(i for i in issues if i.ref.obj == "Fillet")
check(fil_issue.fingerprint is not None, "fillet edge fingerprint survived the break")
check(fil_issue.verdict is not None and fil_issue.verdict.best is not None, "fillet has candidates")
best = fil_issue.verdict.best.name
be = pad.Shape.getElement(best)
check(
    abs(be.CenterOfMass.z - 5) < 1e-6 and abs(be.CenterOfMass.y - 12) < 1e-6,
    f"best fillet candidate {best} is the moved top back edge",
)
check(fil_issue.verdict.status == "suggest", f"fillet match is confident ({fil_issue.verdict.best.score:.0%})")

sk_issue = next((i for i in issues if i.ref.obj == "Sketch001"), None)
check(sk_issue is not None, "sketch attachment reported")
check(sk_issue.verdict is not None and sk_issue.verdict.status == "suggest", "sketch face match is confident")

# Preview: regenerate with the candidate, then leave the document exactly as it was
base_before, undo_before = list(fil.Base[1]), list(doc.UndoNames)
pv = R.preview_shape(fil_issue.ref, best)
check(pv.shape is not None and len(pv.shape.Faces) > 6, f"preview regenerates the fillet ({pv.error or 'ok'})")
check(list(fil.Base[1]) == base_before and not fil.isValid(), "preview restores the link and the error state")
check(list(doc.UndoNames) == undo_before and not doc.RedoNames, "preview leaves no undo or redo entry")

# Relink the fillet (another entry in the same property is healthy)
with R.transaction(doc, "relink"):
    R.relink(fil_issue.ref, best)
doc.recompute()
check(fil.isValid(), f"fillet valid after relink -> {fil.Base[1]}")

# Relink the sketch to its best candidate
issues = R.scan(doc)
sk_issue = next(i for i in issues if i.ref.obj == "Sketch001")
check(sk_issue.verdict is not None and sk_issue.verdict.best is not None, "sketch has candidates after fillet fix")
with R.transaction(doc, "relink sketch"):
    R.relink(sk_issue.ref, sk_issue.verdict.best.name)
doc.recompute()
check(sk2.isValid(), f"sketch valid after relink -> {sk2.AttachmentSupport}")
check(not R.scan(doc), "no broken refs left")

# Each relink is one undo step
check(doc.UndoNames[:2] == ["relink sketch", "relink"], f"relinks are undo steps {doc.UndoNames[:2]}")
doc.undo()
check(doc.RedoNames[:1] == ["relink sketch"], "undo reverts the last relink")

# A split edge has no single true match: it must not be suggested with confidence
doc3 = App.newDocument("RM3")
b3 = doc3.addObject("PartDesign::Body", "Body")
s3 = b3.newObject("Sketcher::SketchObject", "Sketch")
s3.AttachmentSupport = [(b3.Origin.OriginFeatures[3], "")]
s3.MapMode = "FlatFace"
rect(s3, [V(0, 0, 0), V(20, 0, 0), V(20, 10, 0), V(0, 10, 0)])
p3 = b3.newObject("PartDesign::Pad", "Pad")
p3.Profile = s3
p3.Length = 5
doc3.recompute()
eg = index_of(p3.Shape, "Edge", lambda e: abs(e.CenterOfMass.y - 10) < 1e-6 and abs(e.CenterOfMass.z - 5) < 1e-6)
f3 = b3.newObject("PartDesign::Fillet", "Fillet")
f3.Base = (p3, [eg])
f3.Radius = 1
fb = index_of(p3.Shape, "Face", lambda f: abs(f.CenterOfMass.y - 10) < 1e-6)
sk3 = b3.newObject("Sketcher::SketchObject", "Sketch001")
sk3.AttachmentSupport = [(p3, fb)]
sk3.MapMode = "FlatFace"
doc3.recompute()
R.capture_document(doc3)
s3.delGeometry(2)
s3.addGeometry(Part.LineSegment(V(20, 10, 0), V(10, 11, 0)))
s3.addGeometry(Part.LineSegment(V(10, 11, 0), V(0, 10, 0)))
doc3.recompute()
i3 = R.scan(doc3)[0]
check(i3.verdict.status != "suggest", f"split edge is not suggested confidently ({i3.verdict.status})")

# Fallback without stored fingerprints: the sketch plane from its placement
sk3.removeProperty(R.SIGNATURE_PROP)
iss = R.analyze(next(r for r in R.broken_refs(doc3) if r.obj == "Sketch001"))
check(iss.from_plane and iss.verdict is not None, f"plane fallback gives candidates ({iss.verdict.status})")

# Writing back a property that still contains another broken entry
doc2 = App.newDocument("RM2")
b2 = doc2.addObject("PartDesign::Body", "Body")
s2 = b2.newObject("Sketcher::SketchObject", "Sketch")
s2.AttachmentSupport = [(b2.Origin.OriginFeatures[3], "")]
s2.MapMode = "FlatFace"
rect(s2, [V(0, 0, 0), V(20, 0, 0), V(20, 10, 0), V(0, 10, 0)])
p2 = b2.newObject("PartDesign::Pad", "Pad")
p2.Profile = s2
p2.Length = 5
doc2.recompute()
tops = [f"Edge{i}" for i, e in enumerate(p2.Shape.Edges, 1) if abs(e.CenterOfMass.z - 5) < 1e-6]
f2 = b2.newObject("PartDesign::Fillet", "Fillet")
f2.Base = (p2, tops)
f2.Radius = 0.5
doc2.recompute()
R.capture_document(doc2)
move_back(s2, 14)
doc2.recompute()
R.capture_document(doc2)
bad = [i for i in R.scan(doc2) if i.ref.obj == "Fillet"]
print("  doc2 broken:", [(i.ref.sub, i.verdict.status, i.verdict.best and i.verdict.best.name) for i in bad])
check(len(bad) >= 2, "two broken entries in one property")
with R.transaction(doc2, "one"):
    R.relink(bad[0].ref, bad[0].verdict.best.name)
print("  after first relink:", f2.Base[1])
check(sum(s.startswith("?") for s in f2.Base[1]) == len(bad) - 1, "other broken entry kept its ? marker")
doc2.recompute()
rest = [i for i in R.scan(doc2) if i.ref.obj == "Fillet"]
check(len(rest) == len(bad) - 1, "rescan still sees the remaining broken entry")
with R.transaction(doc2, "rest"):
    for i in rest:
        R.relink(i.ref, i.verdict.best.name)
doc2.recompute()
check(f2.isValid(), f"fillet valid after fixing all -> {f2.Base[1]}")

print("\nRESULT:", "OK" if not FAILS else f"{len(FAILS)} FAILED")
