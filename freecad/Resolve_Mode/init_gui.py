"""GUI entry point. Resolve_Mode adds no workbench: it adds a toolbar button to
PartDesign, a Tools menu entry, a preference page, and a document observer
that keeps fingerprints up to date and opens the panel when something breaks.

Registration happens at import so the toolbar and menu entry exist before the
first workbench builds its UI. Nothing here is heavy; the panel is only built
when it is first shown.
"""

from pathlib import Path

import FreeCADGui as Gui

import FreeCAD as App

from . import commands
from .gui.controller import Controller
from .gui.preferences_page import ResolveModePreferencesPage

Gui.addIconPath(str(Path(__file__).parent / "resources" / "icons"))

TOOLBAR = "Resolve_Mode"


def _active_workbench_name() -> str:
    active = Gui.activeWorkbench()
    for name, handler in Gui.listWorkbenches().items():
        if handler is active:
            return name
    return ""


class _Manipulator:
    def modifyToolBars(self):
        if _active_workbench_name() != "PartDesignWorkbench":
            return []
        return [
            {"append": TOOLBAR, "toolBar": ""},
            {"append": commands.OPEN_CMD, "toolBar": TOOLBAR},
        ]

    def modifyMenuBar(self):
        return [{"insert": commands.OPEN_CMD, "menuItem": "Std_DlgParameter", "after": ""}]


_controller = Controller()
commands.register(_controller)
App.addDocumentObserver(_controller)
# FreeCAD keys Python preference pages by class name, so the name must be globally unique.
Gui.addPreferencePage(ResolveModePreferencesPage, "Resolve_Mode")
_manipulator = _Manipulator()
Gui.addWorkbenchManipulator(_manipulator)
