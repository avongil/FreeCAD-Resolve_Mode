"""Temporarily change which features of a Body are visible, and put it back.

Used by Pick in 3D view and both preview modes, so the user sees the shape
that matters (the feature a reference points at, or nothing but the preview)
instead of the stale tip of the Body.
"""

from __future__ import annotations

import FreeCAD as App


class Isolation:
    def __init__(self):
        self._doc: str | None = None
        self._hidden: list[str] = []
        self._shown: str | None = None

    @property
    def active(self) -> bool:
        return self._doc is not None

    def isolate(self, context, show=None):
        """Hide the visible shapes in ``context``'s Body; then show ``show`` (or nothing).

        ``context`` is any object in the Body. The previous state is restored by
        :meth:`restore`; calling isolate again restores first.
        """
        self.restore()
        doc = context.Document
        body = context.getParentGeoFeatureGroup()
        siblings = body.Group if body is not None else doc.Objects
        self._doc = doc.Name
        for o in siblings:
            vo = getattr(o, "ViewObject", None)
            if o is not show and vo is not None and vo.Visibility and hasattr(o, "Shape"):
                vo.Visibility = False
                self._hidden.append(o.Name)
        if show is not None and show.ViewObject is not None and not show.ViewObject.Visibility:
            show.ViewObject.Visibility = True
            self._shown = show.Name

    def restore(self):
        doc = App.listDocuments().get(self._doc) if self._doc else None
        if doc is not None:
            if self._shown and (o := doc.getObject(self._shown)) is not None and o.ViewObject is not None:
                o.ViewObject.Visibility = False
            for name in self._hidden:
                o = doc.getObject(name)
                if o is not None and o.ViewObject is not None:
                    o.ViewObject.Visibility = True
        self._doc = None
        self._hidden = []
        self._shown = None

    def forget(self):
        """Drop the saved state without touching the document (it is closing)."""
        self._doc = None
        self._hidden = []
        self._shown = None
