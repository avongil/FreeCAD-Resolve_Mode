"""Temporary 3D overlays. Nothing is added to the document.

Two modes, at most one at a time:

- ``show_on_base``: the candidate element on the feature the reference points
  at (e.g. Edge13 on the Pad a fillet is built on), with the later features
  of the Body hidden. This is the geometry the user saw when first picking.
- ``show_result``: the referencing feature as it would regenerate with the
  candidate, computed by :func:`references.preview_shape`. Solids are drawn
  shaded with the Body's features hidden; sketches are drawn as wires on top
  of the feature they attach to.
"""

from __future__ import annotations

import FreeCADGui as Gui

import FreeCAD as App

from .. import references as R
from .isolate import Isolation


def _view(doc_name: str):
    try:
        gdoc = Gui.getDocument(doc_name)
    except Exception:
        return None
    view = gdoc.ActiveView
    if view is not None and hasattr(view, "getSceneGraph"):
        return view
    try:
        views = gdoc.mdiViewsOfType("Gui::View3DInventor")
    except Exception:
        return None
    return views[0] if views else None


def _rgb(color: str):
    c = color.lstrip("#")
    return tuple(int(c[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def _parent_placement(obj):
    """Placement that maps obj.Shape coordinates to global ones."""
    try:
        return obj.getGlobalPlacement().multiply(obj.Placement.inverse())
    except Exception:
        return App.Placement()


HIGHLIGHT = "#3b9eff"
OLD = "#ef5350"
RESULT_FACE = "#9cc3ff"
RESULT_EDGE = "#1d3c78"


class Highlighter:
    """Owns at most one overlay, and the visibility changes made for it."""

    def __init__(self):
        self._root = None
        self._view = None
        self._iso = Isolation()
        self.current = None  # (mode, ref key, element) being shown

    def clear(self):
        if self._root is not None and self._view is not None:
            try:
                self._view.getSceneGraph().removeChild(self._root)
            except Exception:
                pass  # view already closed
        self._root = None
        self._view = None
        self._iso.restore()
        self.current = None

    def forget(self):
        """The document is closing: drop everything without touching it."""
        self._root = None
        self._view = None
        self._iso.forget()
        self.current = None

    # -- modes -----------------------------------------------------------------

    def show_on_base(self, ref: R.Ref, element: str | None, old_point=None):
        """``element`` on the ref's target, later features hidden, old location marked."""
        from pivy import coin

        self.clear()
        view = _view(ref.doc)
        _, target = ref.resolve()
        if view is None or target is None:
            return
        self._iso.isolate(target, show=target)
        root = self._new_root(coin, coin.SoAnnotation(), _parent_placement(target))
        shape = R.target_shape(target, ref.prefix)
        if element and shape is not None:
            try:
                sub = shape.getElement(element)
            except Exception:
                sub = None
            if sub is not None:
                size = max(shape.BoundBox.DiagonalLength, 1e-3)
                root.addChild(self._element_node(coin, sub, ref.kind, size, _rgb(HIGHLIGHT)))
        if old_point is not None:
            root.addChild(self._marker(coin, [old_point], _rgb(OLD), coin.SoMarkerSet.CIRCLE_LINE_9_9))
        self._attach(view, root, ("base", ref.key, element))

    def show_result(self, ref: R.Ref, element: str, shape):
        """The referencing feature regenerated with ``element`` (``shape`` from preview_shape)."""
        from pivy import coin

        self.clear()
        view = _view(ref.doc)
        obj, target = ref.resolve()
        if view is None or obj is None or shape is None:
            return
        size = max(shape.BoundBox.DiagonalLength, 1e-3)
        if shape.Faces:
            # A solid: hide the Body (its tip is the stale result) and draw the new one shaded.
            self._iso.isolate(obj, show=None)
            root = self._new_root(coin, coin.SoSeparator(), _parent_placement(obj))
            root.addChild(self._solid(coin, shape, size))
        else:
            # A sketch or datum: show what it attaches to and draw it on top.
            self._iso.isolate(obj, show=target)
            root = self._new_root(coin, coin.SoAnnotation(), _parent_placement(obj))
        root.addChild(self._edges(coin, shape, size, _rgb(HIGHLIGHT if not shape.Faces else RESULT_EDGE), 2))
        self._attach(view, root, ("result", ref.key, element))

    # -- scene graph helpers -------------------------------------------------------

    def _attach(self, view, root, current):
        view.getSceneGraph().addChild(root)
        self._root = root
        self._view = view
        self.current = current

    @staticmethod
    def _new_root(coin, root, plm):
        xf = coin.SoTransform()
        xf.translation.setValue(plm.Base.x, plm.Base.y, plm.Base.z)
        xf.rotation.setValue(coin.SbRotation(*plm.Rotation.Q))
        root.addChild(xf)
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        root.addChild(pick)
        return root

    @staticmethod
    def _marker(coin, points, rgb, index):
        sep = coin.SoSeparator()
        col = coin.SoBaseColor()
        col.rgb.setValue(*rgb)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), [tuple(p) for p in points])
        mk = coin.SoMarkerSet()
        mk.markerIndex = index
        mk.numPoints = len(points)
        sep.addChild(col)
        sep.addChild(coords)
        sep.addChild(mk)
        return sep

    @staticmethod
    def _lines(coin, polylines, rgb, width):
        sep = coin.SoSeparator()
        col = coin.SoBaseColor()
        col.rgb.setValue(*rgb)
        style = coin.SoDrawStyle()
        style.lineWidth = width
        pts = [(p.x, p.y, p.z) for line in polylines for p in line]
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(pts), pts)
        ls = coin.SoLineSet()
        ls.numVertices.setValues(0, len(polylines), [len(line) for line in polylines])
        for n in (col, style, coords, ls):
            sep.addChild(n)
        return sep

    def _edges(self, coin, shape, size, rgb, width):
        lines = []
        for e in shape.Edges:
            try:
                lines.append(e.discretize(Deflection=size * 0.002))
            except Exception:
                pass
        return self._lines(coin, lines, rgb, width) if lines else coin.SoSeparator()

    @staticmethod
    def _faces(coin, shape, size, rgb, transparency, emissive):
        sep = coin.SoSeparator()
        try:
            verts, tris = shape.tessellate(size * 0.003)
        except Exception:
            return sep
        if not verts or not tris:
            return sep
        mat = coin.SoMaterial()
        mat.diffuseColor.setValue(*rgb)
        mat.emissiveColor.setValue(*(c * emissive for c in rgb))
        mat.transparency = transparency
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING  # two-sided lighting
        hints.creaseAngle = 0.6
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(verts), [(v.x, v.y, v.z) for v in verts])
        faces = coin.SoIndexedFaceSet()
        idx = []
        for t in tris:
            idx.extend((t[0], t[1], t[2], -1))
        faces.coordIndex.setValues(0, len(idx), idx)
        for n in (mat, hints, coords, faces):
            sep.addChild(n)
        return sep

    def _solid(self, coin, shape, size):
        sep = coin.SoSeparator()
        offset = coin.SoPolygonOffset()  # keep the edge lines visible on the faces
        sep.addChild(offset)
        sep.addChild(self._faces(coin, shape, size, _rgb(RESULT_FACE), 0.0, 0.15))
        return sep

    def _element_node(self, coin, sub, kind, size, rgb):
        if kind == "Vertex":
            p = sub.Point
            return self._marker(coin, [(p.x, p.y, p.z)], rgb, coin.SoMarkerSet.CIRCLE_FILLED_9_9)
        if kind == "Edge":
            return self._lines(coin, [sub.discretize(Deflection=size * 0.002)], rgb, 5)
        sep = coin.SoSeparator()
        sep.addChild(self._faces(coin, sub, size, rgb, 0.35, 0.6))
        sep.addChild(self._edges(coin, sub, size, rgb, 3))
        return sep
