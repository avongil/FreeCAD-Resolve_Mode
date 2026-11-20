"""Temporary 3D overlay: draws one candidate element and the old location.

The overlay is a plain Coin separator added to the view's scene graph, drawn
on top of the model (SoAnnotation) so it shows even when the referenced
feature is hidden behind later features. Nothing is added to the document.
"""

from __future__ import annotations

import FreeCADGui as Gui

import FreeCAD as App

from .. import references as R


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


class Highlighter:
    """Owns at most one overlay at a time."""

    def __init__(self):
        self._root = None
        self._view = None
        self.current = None  # (ref key, element) being shown

    def clear(self):
        if self._root is not None and self._view is not None:
            try:
                self._view.getSceneGraph().removeChild(self._root)
            except Exception:
                pass  # view already closed
        self._root = None
        self._view = None
        self.current = None

    def show(self, ref: R.Ref, element: str | None, old_point=None, color="#3b9eff", old_color="#ef5350"):
        """Draw ``element`` of the ref's target, plus a marker at ``old_point``."""
        from pivy import coin

        self.clear()
        view = _view(ref.doc)
        if view is None:
            return
        _, target = ref.resolve()
        if target is None:
            return

        root = coin.SoAnnotation()
        xf = coin.SoTransform()
        try:
            plm = target.getGlobalPlacement().multiply(target.Placement.inverse())
        except Exception:
            plm = App.Placement()
        xf.translation.setValue(plm.Base.x, plm.Base.y, plm.Base.z)
        xf.rotation.setValue(coin.SbRotation(*plm.Rotation.Q))
        root.addChild(xf)
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        root.addChild(pick)

        shape = R.target_shape(target, ref.prefix)
        if element and shape is not None:
            try:
                sub = shape.getElement(element)
            except Exception:
                sub = None
            if sub is not None:
                size = max(shape.BoundBox.DiagonalLength, 1e-3)
                root.addChild(self._element_node(coin, sub, ref.kind, size, _rgb(color)))

        if old_point is not None:
            root.addChild(self._marker(coin, [old_point], _rgb(old_color), coin.SoMarkerSet.CIRCLE_LINE_9_9))

        view.getSceneGraph().addChild(root)
        self._root = root
        self._view = view
        self.current = (ref.key, element)

    # ------------------------------------------------------------------

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

    def _element_node(self, coin, sub, kind, size, rgb):
        if kind == "Vertex":
            p = sub.Point
            return self._marker(coin, [(p.x, p.y, p.z)], rgb, coin.SoMarkerSet.CIRCLE_FILLED_9_9)
        defl = size * 0.002
        if kind == "Edge":
            return self._lines(coin, [sub.discretize(Deflection=defl)], rgb, 5)
        sep = coin.SoSeparator()
        try:
            verts, tris = sub.tessellate(size * 0.005)
        except Exception:
            verts, tris = [], []
        if verts and tris:
            mat = coin.SoMaterial()
            mat.diffuseColor.setValue(*rgb)
            mat.emissiveColor.setValue(*(c * 0.6 for c in rgb))
            mat.transparency = 0.35
            hints = coin.SoShapeHints()
            hints.vertexOrdering = coin.SoShapeHints.COUNTERCLOCKWISE
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, len(verts), [(v.x, v.y, v.z) for v in verts])
            faces = coin.SoIndexedFaceSet()
            idx = []
            for t in tris:
                idx.extend((t[0], t[1], t[2], -1))
            faces.coordIndex.setValues(0, len(idx), idx)
            for n in (mat, hints, coords, faces):
                sep.addChild(n)
        outline = []
        for e in sub.Edges:
            try:
                outline.append(e.discretize(Deflection=defl))
            except Exception:
                pass
        if outline:
            sep.addChild(self._lines(coin, outline, rgb, 3))
        return sep
