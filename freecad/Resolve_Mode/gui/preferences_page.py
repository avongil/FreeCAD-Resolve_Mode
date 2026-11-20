"""Edit > Preferences > Resolve_Mode page."""

from __future__ import annotations

import FreeCAD as App

from .. import preferences as prefs
from .qt import QtWidgets

translate = App.Qt.translate


class ResolveModePreferencesPage:
    def __init__(self, _parent=None):
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Resolve_Mode")
        lay = QtWidgets.QVBoxLayout(self.form)

        g1 = QtWidgets.QGroupBox(translate("Resolve_Mode", "Behaviour"))
        l1 = QtWidgets.QVBoxLayout(g1)
        self.auto = QtWidgets.QCheckBox(
            translate("Resolve_Mode", "Open the panel automatically when a recompute leaves broken references")
        )
        self.store = QtWidgets.QCheckBox(
            translate("Resolve_Mode", "Remember the geometry of referenced elements (needed for suggestions)")
        )
        self.store.setToolTip(
            translate(
                "Resolve_Mode",
                "Stores a small fingerprint (type, size, position, direction) of each referenced edge/face "
                "in a hidden property of the referencing feature. Saved with the file.",
            )
        )
        l1.addWidget(self.auto)
        l1.addWidget(self.store)
        lay.addWidget(g1)

        g2 = QtWidgets.QGroupBox(translate("Resolve_Mode", "Matching"))
        form = QtWidgets.QFormLayout(g2)

        def spin(tip):
            s = QtWidgets.QSpinBox()
            s.setRange(1, 100)
            s.setSuffix(" %")
            s.setToolTip(tip)
            return s

        self.confident = spin(translate("Resolve_Mode", "Similarity a match needs to be offered as a suggestion."))
        self.margin = spin(
            translate(
                "Resolve_Mode", "How far the best match must lead the runner-up; otherwise the result is ambiguous."
            )
        )
        self.minimum = spin(translate("Resolve_Mode", "Similarity an element needs to be listed as a candidate."))
        self.margin.setRange(0, 50)
        form.addRow(translate("Resolve_Mode", "Suggest a match from"), self.confident)
        form.addRow(translate("Resolve_Mode", "Lead over the runner-up"), self.margin)
        form.addRow(translate("Resolve_Mode", "List candidates from"), self.minimum)
        lay.addWidget(g2)
        lay.addStretch(1)

    def loadSettings(self):
        self.auto.setChecked(prefs.get_bool("AutoOpen"))
        self.store.setChecked(prefs.get_bool("StoreSignatures"))
        self.confident.setValue(prefs.get_int("ConfidentScore"))
        self.margin.setValue(prefs.get_int("AmbiguityMargin"))
        self.minimum.setValue(prefs.get_int("CandidateScore"))

    def saveSettings(self):
        minimum = min(self.minimum.value(), self.confident.value())
        prefs.set_bool("AutoOpen", self.auto.isChecked())
        prefs.set_bool("StoreSignatures", self.store.isChecked())
        prefs.set_int("ConfidentScore", self.confident.value())
        prefs.set_int("AmbiguityMargin", self.margin.value())
        prefs.set_int("CandidateScore", minimum)
