"""Pick a replacement element in the 3D view.

While picking, the referenced feature (e.g. the Pad a fillet is built on) is
shown and the other visible features of its Body are hidden, so clicks land
on the right shape. Visibility is restored when picking ends.
"""

from __future__ import annotations

import FreeCADGui as Gui

import FreeCAD as App

from .. import references as R
from .isolate import Isolation
from .qt import QtCore

translate = App.Qt.translate


def kind_phrase(kind: str) -> str:
    """'an edge' / 'a face' / 'a vertex', translated as whole phrases."""
    return {
        "Edge": translate("Resolve_Mode", "an edge"),
        "Face": translate("Resolve_Mode", "a face"),
        "Vertex": translate("Resolve_Mode", "a vertex"),
    }.get(kind, kind)


class Picker:
    def __init__(self):
        self.ref: R.Ref | None = None
        self._on_pick = None
        self._on_hint = None
        self._iso = Isolation()
        self._pending = False

    @property
    def active(self) -> bool:
        return self.ref is not None

    def start(self, ref: R.Ref, on_pick, on_hint):
        """``on_pick(element)`` when a valid element is clicked; ``on_hint(text)`` otherwise."""
        self.stop()
        doc = App.getDocument(ref.doc)
        target = doc.getObject(ref.target)
        if target is None:
            return
        self.ref = ref
        self._on_pick = on_pick
        self._on_hint = on_hint
        self._iso.isolate(target, show=target)
        Gui.Selection.clearSelection()
        Gui.Selection.addObserver(self)

    def stop(self):
        if self.ref is None:
            return
        try:
            Gui.Selection.removeObserver(self)
        except Exception:
            pass
        self._iso.restore()
        self.ref = None
        self._on_pick = None
        self._on_hint = None

    def forget(self):
        """The document is closing: stop without touching it."""
        try:
            Gui.Selection.removeObserver(self)
        except Exception:
            pass
        self._iso.forget()
        self.ref = None
        self._on_pick = None
        self._on_hint = None

    # -- selection observer ------------------------------------------------

    def addSelection(self, doc, obj, sub, pnt):
        if self.ref is None or doc != self.ref.doc or self._pending:
            return
        self._pending = True
        QtCore.QTimer.singleShot(0, self._handle)  # never relink from inside the callback

    def _handle(self):
        self._pending = False
        ref = self.ref
        if ref is None:
            return
        for so in Gui.Selection.getSelectionEx(ref.doc):
            for name in so.SubElementNames:
                element = name.split(".")[-1]
                if so.Object.Name == ref.target and element.startswith(ref.kind):
                    on_pick = self._on_pick
                    Gui.Selection.clearSelection()
                    self.stop()
                    on_pick(element)
                    return
        Gui.Selection.clearSelection()
        target = App.getDocument(ref.doc).getObject(ref.target)
        if self._on_hint:
            self._on_hint(
                translate("Resolve_Mode", "That is not it: pick {kind} on {target}").format(
                    kind=kind_phrase(ref.kind), target=target.Label if target else ref.target
                )
            )
