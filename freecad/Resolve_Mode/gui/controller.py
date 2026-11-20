"""Glue between FreeCAD events, the reference logic and the panel.

One Controller lives for the whole session (created in init_gui). It is a
document observer: after each recompute it refreshes the stored fingerprints
and, when references are broken and auto mode is on, opens the panel.
All work triggered by observer slots is deferred to the Qt event loop and
postponed while a recompute is still running.
"""

from __future__ import annotations

import FreeCADGui as Gui

import FreeCAD as App

from .. import preferences as prefs
from .. import references as R
from .highlight import Highlighter
from .picker import Picker
from .qt import QtCore, QtWidgets, alive

translate = App.Qt.translate


class Controller:
    def __init__(self):
        self.panel = None
        self.highlighter = Highlighter()
        self.picker = Picker()
        self._pending: set[str] = set()
        self._timer = None
        self._busy = False
        self._dismissed: dict[str, frozenset] = {}  # doc -> broken set the user closed the panel on

    # -- document observer slots (App.addDocumentObserver) ----------------

    def slotRecomputedDocument(self, doc):
        self._schedule(doc.Name)

    def slotRecomputedObject(self, obj):
        try:
            self._schedule(obj.Document.Name)
        except Exception:
            pass

    def slotUndoDocument(self, doc):
        self._schedule(doc.Name)

    def slotRedoDocument(self, doc):
        self._schedule(doc.Name)

    def slotActivateDocument(self, doc):
        if self._panel_visible():
            self._schedule(doc.Name)

    def slotDeletedDocument(self, doc):
        name = doc.Name
        self._pending.discard(name)
        self._dismissed.pop(name, None)
        if self.picker.active and self.picker.ref.doc == name:
            self.picker.ref = None  # document is going away; nothing to restore
        if self.highlighter.current is not None:
            self.highlighter.clear()
        if self._panel_visible() and self.panel.doc_name == name:
            QtCore.QTimer.singleShot(0, self._show_active)

    def slotStartSaveDocument(self, doc, _path):
        # Files that are saved without a recompute still get fingerprints.
        if prefs.get_bool("StoreSignatures") and not doc.Recomputing:
            try:
                R.capture_document(doc)
            except Exception as exc:
                App.Console.PrintLog(f"[Resolve_Mode] capture on save failed: {exc}\n")

    # -- scheduling ---------------------------------------------------------

    def _schedule(self, doc_name: str, delay: int = 120):
        self._pending.add(doc_name)
        if self._timer is None:
            self._timer = QtCore.QTimer()
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._run)
        self._timer.start(delay)

    def _run(self):
        pending, self._pending = self._pending, set()
        for name in pending:
            doc = App.listDocuments().get(name)
            if doc is None:
                continue
            if doc.Recomputing or self._busy:
                self._schedule(name, 300)
                continue
            self._process(doc)

    def _process(self, doc):
        if prefs.get_bool("StoreSignatures"):
            R.capture_document(doc)
        if self._panel_visible():
            if self.panel.doc_name in (doc.Name, None) and App.ActiveDocument is doc:
                self._fill(doc)
            return
        if not prefs.get_bool("AutoOpen") or App.ActiveDocument is not doc:
            return
        refs = R.broken_refs(doc)
        if not refs:
            self._dismissed.pop(doc.Name, None)
            return
        if self._signature(refs) == self._dismissed.get(doc.Name):
            return  # user already closed the panel on exactly this set
        self.show(doc)

    @staticmethod
    def _signature(refs) -> frozenset:
        return frozenset((r.obj, r.prop, r.element) for r in refs)

    # -- panel ----------------------------------------------------------------

    def _panel_visible(self) -> bool:
        return self.panel is not None and alive(self.panel.dock) and self.panel.dock.isVisible()

    def _ensure_panel(self):
        if self.panel is None or not alive(self.panel.dock):
            from .panel import Panel

            self.panel = Panel(self, Gui.getMainWindow())
        return self.panel

    def show(self, doc=None):
        doc = doc or App.ActiveDocument
        panel = self._ensure_panel()
        self._fill(doc)
        panel.dock.show()
        panel.dock.raise_()

    def toggle(self):
        if self._panel_visible():
            self.panel.dock.close()
        else:
            self.show()

    def _show_active(self):
        if self._panel_visible():
            self._fill(App.ActiveDocument)

    def _fill(self, doc):
        panel = self._ensure_panel()
        self.picker.stop()
        if doc is None:
            panel.set_issues(None, "", [], prefs.get_bool("AutoOpen"))
            return
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            issues = R.scan(doc)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        panel.set_issues(doc.Name, doc.Label, issues, prefs.get_bool("AutoOpen"))

    def refresh(self):
        doc = App.ActiveDocument
        if doc is not None and prefs.get_bool("StoreSignatures"):
            R.capture_document(doc)
        self._fill(doc)

    def on_panel_closed(self):
        self.picker.stop()
        self.clear_preview()
        if self.panel is not None and self.panel.doc_name and self.panel.issues:
            self._dismissed[self.panel.doc_name] = frozenset(
                (i.ref.obj, i.ref.prop, i.ref.element) for i in self.panel.issues
            )

    def set_auto(self, on: bool):
        prefs.set_bool("AutoOpen", on)

    # -- actions ----------------------------------------------------------------

    def select_object(self, doc_name: str, obj_name: str):
        doc = App.listDocuments().get(doc_name)
        obj = doc.getObject(obj_name) if doc else None
        if obj is None:
            return
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(obj)

    def preview(self, issue: R.Issue, element: str | None):
        fp = issue.fingerprint
        old = fp.get("c") if fp and not issue.from_plane else None
        try:
            self.highlighter.show(issue.ref, element, old_point=old)
        except Exception as exc:
            App.Console.PrintWarning(f"[Resolve_Mode] preview failed: {exc}\n")

    def clear_preview(self):
        self.highlighter.clear()

    def apply(self, fixes):
        """Relink ``[(ref, element), ...]`` in one undo step, then recompute."""
        if not fixes or self._busy:
            return
        doc = App.listDocuments().get(fixes[0][0].doc)
        if doc is None or doc.Recomputing:
            return
        self.picker.stop()
        self.clear_preview()
        if len(fixes) == 1:
            ref, el = fixes[0]
            label = f"Resolve_Mode: {ref.element} -> {el}"
        else:
            label = f"Resolve_Mode: relink {len(fixes)} references"
        self._busy = True
        if self.panel is not None:
            self.panel.set_busy(True)
        stale = []
        try:
            with R.transaction(doc, label):
                for ref, el in fixes:
                    try:
                        R.relink(ref, el)
                    except R.StaleReference:
                        stale.append(ref)
            doc.recompute()
        finally:
            self._busy = False
            if self.panel is not None and alive(self.panel.dock):
                self.panel.set_busy(False)
        for ref in stale:
            App.Console.PrintWarning(
                f"[Resolve_Mode] {ref.obj}.{ref.prop} changed since the scan; {ref.element} was not relinked\n"
            )
        self._process(doc)

    def start_pick(self, issue: R.Issue, on_hint):
        self.clear_preview()

        def picked(element):
            if self.panel is not None:
                self.panel.pick_ended()
            self.apply([(issue.ref, element)])

        self.picker.start(issue.ref, picked, on_hint)

    def cancel_pick(self):
        self.picker.stop()
        if self.panel is not None:
            self.panel.pick_ended()

    def edit_manually(self, issue: R.Issue):
        """Hand the feature to FreeCAD's own editor."""
        self.picker.stop()
        self.clear_preview()
        ref = issue.ref
        doc = App.listDocuments().get(ref.doc)
        obj = doc.getObject(ref.obj) if doc else None
        if obj is None:
            return
        if Gui.Control.activeDialog():
            Gui.getMainWindow().statusBar().showMessage(
                translate("Resolve_Mode", "Close the open task dialog first"), 4000
            )
            return
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(obj)
        if ref.prop == "AttachmentSupport":
            Gui.runCommand("Part_EditAttachment", 0)
        else:
            Gui.ActiveDocument.setEdit(obj.Name)

    def shutdown(self):
        self.picker.stop()
        self.clear_preview()
