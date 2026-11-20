"""Toolbar/menu command that opens the Resolve_Mode panel."""

from pathlib import Path

import FreeCADGui as Gui
from PySide.QtCore import QT_TRANSLATE_NOOP

import FreeCAD as App

OPEN_CMD = "Resolve_Mode_Open"
_ICON = str(Path(__file__).parent / "resources" / "icons" / "Resolve_Mode.svg")


class OpenPanel:
    def __init__(self, controller):
        self._controller = controller

    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP(OPEN_CMD, "Resolve broken references"),
            "ToolTip": QT_TRANSLATE_NOOP(
                OPEN_CMD,
                "Show the broken PartDesign references of the active document, with suggested "
                "replacements you can preview, accept or pick in the 3D view",
            ),
            "Pixmap": _ICON,
            "CmdType": "Alter3DView",
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        self._controller.toggle()


def register(controller):
    Gui.addCommand(OPEN_CMD, OpenPanel(controller))
