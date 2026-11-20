"""The Resolve_Mode dock panel: one card per broken reference."""

from __future__ import annotations

import FreeCAD as App

from .. import references as R
from . import icons
from .picker import kind_phrase
from .qt import QtCore, QtGui, QtWidgets

translate = App.Qt.translate

DOCK_NAME = "Resolve_Mode_Dock"


def _mix(a: QtGui.QColor, b: QtGui.QColor, t: float) -> str:
    return QtGui.QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    ).name()


class Theme:
    """Colors derived from the application palette, with fixed semantic accents."""

    def __init__(self, widget: QtWidgets.QWidget):
        pal = widget.palette()
        win = pal.color(QtGui.QPalette.Window)
        text = pal.color(QtGui.QPalette.WindowText)
        self.dark = win.lightness() < 128
        black, white = QtGui.QColor(0, 0, 0), QtGui.QColor(255, 255, 255)
        self.text = text.name()
        self.muted = _mix(text, win, 0.35)
        self.border = _mix(win, text, 0.16)
        self.hover = _mix(win, text, 0.08)
        self.info_bg = _mix(win, black, 0.32) if self.dark else _mix(win, black, 0.05)
        self.danger = "#f0716b" if self.dark else "#c62828"
        self.header_bg = (
            _mix(win, QtGui.QColor("#5c0f0f"), 0.75) if self.dark else _mix(win, QtGui.QColor("#ffcdd2"), 0.85)
        )
        self.badge_bg = (
            _mix(win, QtGui.QColor("#5c0f0f"), 0.85) if self.dark else _mix(win, QtGui.QColor("#ffcdd2"), 1.0)
        )
        self.ok = "#4caf50" if self.dark else "#2e7d32"
        self.ok_bg = _mix(win, QtGui.QColor("#1b4d22"), 0.6) if self.dark else _mix(win, QtGui.QColor("#c8e6c9"), 0.85)
        self.amber = "#e3a33a" if self.dark else "#9a6700"
        self.info = "#5ea9ff" if self.dark else "#0969da"
        self.primary = "#3b82d6"
        self.primary_hover = "#4b92e6"
        self.highlight = "#3b9eff"
        self.footer_bg = _mix(win, black, 0.2) if self.dark else _mix(win, black, 0.03)
        self.white = white.name()

    def stylesheet(self) -> str:
        return f"""
        #rmRoot {{ }}
        #rmHeader {{ background:{self.header_bg}; border-bottom:1px solid {self.border}; }}
        #rmHeader[ok="true"] {{ background:{self.ok_bg}; }}
        #rmHeaderTitle {{ color:{self.danger}; font-weight:600; }}
        #rmHeader[ok="true"] #rmHeaderTitle {{ color:{self.ok}; }}
        #rmCard {{ border-bottom:1px solid {self.border}; }}
        #rmTitle {{ font-weight:600; }}
        #rmSub {{ color:{self.muted}; }}
        #rmDetail {{ color:{self.muted}; }}
        #rmBadge {{ background:{self.badge_bg}; color:{self.danger}; border-radius:9px; padding:2px 9px; }}
        #rmInfo {{ background:{self.info_bg}; border-radius:8px; }}
        #rmInfoText {{ color:{self.muted}; }}
        #rmCandRow {{ background:{self.info_bg}; border-radius:6px; }}
        #rmFooter {{ background:{self.footer_bg}; border-top:1px solid {self.border}; }}
        QPushButton#rmBtn {{
            background:transparent; color:{self.text}; border:1px solid {self.border};
            border-radius:8px; padding:5px 11px;
        }}
        QPushButton#rmBtn:hover {{ background:{self.hover}; }}
        QPushButton#rmBtn:checked {{ border-color:{self.highlight}; color:{self.highlight}; }}
        QPushButton#rmBtn:disabled {{ color:{self.muted}; }}
        QPushButton#rmPrimary {{
            background:{self.primary}; color:{self.white}; border:1px solid {self.primary};
            border-radius:8px; padding:5px 14px;
        }}
        QPushButton#rmPrimary:hover {{ background:{self.primary_hover}; }}
        QPushButton#rmPrimary:disabled {{ background:{self.border}; border-color:{self.border}; color:{self.muted}; }}
        QToolButton#rmTool {{ border:none; padding:3px; border-radius:6px; }}
        QToolButton#rmTool:hover {{ background:{self.hover}; }}
        """


def _label(text="", name=None, wrap=False) -> QtWidgets.QLabel:
    lab = QtWidgets.QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def _scaled_font(widget, factor: float, bold=False) -> QtGui.QFont:
    f = QtGui.QFont(widget.font())
    if f.pointSizeF() > 0:
        f.setPointSizeF(f.pointSizeF() * factor)
    f.setBold(bold)
    return f


def describe(ref: R.Ref) -> str:
    kind = ref.kind.lower()
    if ref.prop == "AttachmentSupport":
        if ref.kind == "Face":
            return translate("Resolve_Mode", "Broken attachment plane")
        return translate("Resolve_Mode", "Broken attachment {kind}").format(kind=kind)
    if ref.prop == "ExternalGeometry":
        return translate("Resolve_Mode", "Missing external {kind}").format(kind=kind)
    return translate("Resolve_Mode", "Missing {kind} reference").format(kind=kind)


class Card(QtWidgets.QFrame):
    """One broken reference."""

    def __init__(self, panel: Panel, issue: R.Issue):
        super().__init__()
        self.panel = panel
        self.issue = issue
        self.setObjectName("rmCard")
        self.cand_previews: list[QtWidgets.QPushButton] = []
        th = panel.theme
        ref = issue.ref
        obj, target = ref.resolve()
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        top = QtWidgets.QHBoxLayout()
        title = _label(obj.Label if obj else ref.obj, "rmTitle")
        title.setFont(_scaled_font(self, 1.15, bold=True))
        title.setCursor(QtCore.Qt.PointingHandCursor)
        title.setToolTip(translate("Resolve_Mode", "Select in the tree"))
        title.mousePressEvent = lambda _e: panel.controller.select_object(ref.doc, ref.obj)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(_label(ref.element, "rmBadge"))
        lay.addLayout(top)

        lay.addWidget(_label(describe(ref), "rmSub"))
        detail = _label(
            translate("Resolve_Mode", "{prop} on {target}").format(
                prop=ref.prop, target=target.Label if target else ref.target
            ),
            "rmDetail",
        )
        detail.setFont(_scaled_font(self, 0.9))
        lay.addWidget(detail)

        # info box
        self.info = QtWidgets.QFrame()
        self.info.setObjectName("rmInfo")
        il = QtWidgets.QHBoxLayout(self.info)
        il.setContentsMargins(10, 8, 10, 8)
        il.setSpacing(8)
        self.info_icon = QtWidgets.QLabel()
        self.info_text = _label("", "rmInfoText", wrap=True)
        il.addWidget(self.info_icon, 0, QtCore.Qt.AlignTop)
        il.addWidget(self.info_text, 1)
        lay.addSpacing(4)
        lay.addWidget(self.info)

        # buttons
        self.buttons = QtWidgets.QHBoxLayout()
        self.buttons.setSpacing(8)
        lay.addSpacing(4)
        lay.addLayout(self.buttons)

        # candidate list (hidden until asked)
        self.cand_box = QtWidgets.QWidget()
        cl = QtWidgets.QVBoxLayout(self.cand_box)
        cl.setContentsMargins(0, 4, 0, 0)
        cl.setSpacing(4)
        self.cand_box.setVisible(False)
        lay.addWidget(self.cand_box)

        self._build(th)

    # ------------------------------------------------------------------

    def _btn(self, text, icon_name, slot, checkable=False, primary=False):
        th = self.panel.theme
        b = QtWidgets.QPushButton(text)
        b.setObjectName("rmPrimary" if primary else "rmBtn")
        b.setIcon(icons.icon(icon_name, th.white if primary else th.text))
        b.setCheckable(checkable)
        b.setCursor(QtCore.Qt.PointingHandCursor)
        if slot is not None:
            b.clicked.connect(slot)
        return b

    def _set_info(self, icon_name, color, text):
        self.info_icon.setPixmap(icons.icon(icon_name, color, 18).pixmap(18, 18))
        self.info_text.setText(text)

    def _info_state(self):
        """(icon, color, text) for the info box in its resting state."""
        th = self.panel.theme
        issue, ref, v = self.issue, self.issue.ref, self.issue.verdict
        _, target = ref.resolve()
        tlabel = target.Label if target else ref.target
        if ref.blocked:
            return (
                "lock",
                th.muted,
                translate("Resolve_Mode", "Waiting on {target}: it failed to recompute. Fix it first.").format(
                    target=tlabel
                ),
            )
        if v is not None and v.status == "suggest":
            text = translate("Resolve_Mode", "Suggested match: {el}, geometric similarity {pct}%").format(
                el=v.best.name, pct=round(v.best.score * 100)
            )
            if issue.from_plane:
                text += " " + translate("Resolve_Mode", "(matched to where the sketch sits now)")
            return "bulb", th.info, text
        if v is not None and v.candidates:
            n = len(v.candidates)
            if n == 1:
                text = translate("Resolve_Mode", "No confident match: 1 candidate within tolerance")
            else:
                text = translate("Resolve_Mode", "No confident match: {n} candidates within tolerance").format(n=n)
            return "alert", th.amber, text
        if issue.fingerprint is not None:
            return (
                "alert",
                th.amber,
                translate("Resolve_Mode", "No match within tolerance. Pick the replacement in the 3D view."),
            )
        return (
            "alert",
            th.amber,
            translate(
                "Resolve_Mode",
                "No stored geometry for this reference (it broke before Resolve_Mode saw it). "
                "Pick the replacement in the 3D view.",
            ),
        )

    def _build(self, th: Theme):
        ref, v = self.issue.ref, self.issue.verdict
        self._set_info(*self._info_state())
        _, target = ref.resolve()
        tlabel = target.Label if target else ref.target
        if ref.blocked:
            self.buttons.addWidget(
                self._btn(
                    translate("Resolve_Mode", "Select {target}").format(target=tlabel),
                    "hand",
                    lambda: self.panel.controller.select_object(ref.doc, ref.target),
                )
            )
        elif v is not None and v.status == "suggest":
            prev = self._btn(translate("Resolve_Mode", "Preview"), "eye", None, checkable=True)
            prev.toggled.connect(lambda on, b=prev: self.panel.preview(self, b, v.best.name, on))
            self.buttons.addWidget(prev)
            self.buttons.addWidget(
                self._btn(translate("Resolve_Mode", "Accept"), "check", lambda: self.panel.accept([(ref, v.best.name)]))
            )
        elif v is not None and v.candidates:
            show = self._btn(translate("Resolve_Mode", "Show candidates"), "list", None, checkable=True)
            show.toggled.connect(self._toggle_candidates)
            self.buttons.addWidget(show)
        if not ref.blocked:
            self.pick_btn = self._btn(translate("Resolve_Mode", "Pick in 3D view"), "hand", self._pick, checkable=True)
            self.buttons.addWidget(self.pick_btn)
        self.buttons.addStretch(1)

    def _toggle_candidates(self, on: bool):
        if on and self.cand_box.layout().count() == 0:
            self._fill_candidates()
        self.cand_box.setVisible(on)
        if not on:
            for b in self.cand_previews:
                b.setChecked(False)

    def _fill_candidates(self):
        ref = self.issue.ref
        lay = self.cand_box.layout()
        for cand in self.issue.verdict.candidates[:8]:
            row = QtWidgets.QFrame()
            row.setObjectName("rmCandRow")
            rl = QtWidgets.QHBoxLayout(row)
            rl.setContentsMargins(10, 4, 6, 4)
            name = _label(cand.name)
            name.setFont(_scaled_font(self, 1.0, bold=True))
            rl.addWidget(name)
            bar = QtWidgets.QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(round(cand.score * 100))
            bar.setFormat("%p%")
            bar.setMaximumHeight(14)
            bar.setMaximumWidth(110)
            rl.addWidget(bar)
            rl.addStretch(1)
            prev = self._btn("", "eye", None, checkable=True)
            prev.setToolTip(translate("Resolve_Mode", "Preview {el}").format(el=cand.name))
            prev.toggled.connect(lambda on, b=prev, el=cand.name: self.panel.preview(self, b, el, on))
            self.cand_previews.append(prev)
            rl.addWidget(prev)
            acc = self._btn("", "check", lambda _=False, el=cand.name: self.panel.accept([(ref, el)]))
            acc.setToolTip(translate("Resolve_Mode", "Use {el}").format(el=cand.name))
            rl.addWidget(acc)
            lay.addWidget(row)

    def _pick(self, on: bool):
        if on:
            self.panel.start_pick(self)
        else:
            self.panel.controller.cancel_pick()

    def set_picking(self, on: bool, hint: str | None = None):
        th = self.panel.theme
        if hasattr(self, "pick_btn"):
            self.pick_btn.blockSignals(True)
            self.pick_btn.setChecked(on)
            self.pick_btn.blockSignals(False)
        if on:
            ref = self.issue.ref
            _, target = ref.resolve()
            tlabel = target.Label if target else ref.target
            self._set_info(
                "hand",
                th.highlight,
                hint
                or translate(
                    "Resolve_Mode", "Click {kind} on {target} in the 3D view. Click the button again to cancel."
                ).format(kind=kind_phrase(ref.kind), target=tlabel),
            )
        else:
            self._set_info(*self._info_state())


class _Dock(QtWidgets.QDockWidget):
    def __init__(self, panel, parent):
        super().__init__(parent)
        self._panel = panel

    def closeEvent(self, event):
        self._panel.on_closed()
        super().closeEvent(event)


class Panel:
    """Builds and owns the dock widget. Logic lives in the controller."""

    def __init__(self, controller, main_window):
        self.controller = controller
        self.doc_name: str | None = None
        self.issues: list[R.Issue] = []
        self.cards: list[Card] = []
        self._checked_preview: QtWidgets.QPushButton | None = None
        self._picking_card: Card | None = None

        self.dock = _Dock(self, main_window)
        self.dock.setObjectName(DOCK_NAME)
        self.dock.setWindowTitle(translate("Resolve_Mode", "Resolve Mode"))
        self.theme = Theme(main_window)

        root = QtWidgets.QWidget()
        root.setObjectName("rmRoot")
        root.setStyleSheet(self.theme.stylesheet())
        outer = QtWidgets.QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # header
        self.header = QtWidgets.QFrame()
        self.header.setObjectName("rmHeader")
        hl = QtWidgets.QHBoxLayout(self.header)
        hl.setContentsMargins(14, 10, 8, 10)
        self.header_icon = QtWidgets.QLabel()
        self.header_title = _label("", "rmHeaderTitle")
        self.header_title.setFont(_scaled_font(root, 1.25, bold=True))
        hl.addWidget(self.header_icon)
        hl.addWidget(self.header_title, 1)
        self.auto = QtWidgets.QCheckBox(translate("Resolve_Mode", "Auto"))
        self.auto.setToolTip(
            translate("Resolve_Mode", "Open this panel automatically when a recompute leaves broken references")
        )
        self.auto.toggled.connect(controller.set_auto)
        hl.addWidget(self.auto)
        self.refresh_btn = QtWidgets.QToolButton()
        self.refresh_btn.setObjectName("rmTool")
        self.refresh_btn.setIcon(icons.icon("refresh", self.theme.text))
        self.refresh_btn.setToolTip(translate("Resolve_Mode", "Scan again"))
        self.refresh_btn.clicked.connect(controller.refresh)
        hl.addWidget(self.refresh_btn)
        outer.addWidget(self.header)

        # cards
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.list_widget = QtWidgets.QWidget()
        self.list_layout = QtWidgets.QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.scroll.setWidget(self.list_widget)
        outer.addWidget(self.scroll, 1)

        # footer
        self.footer = QtWidgets.QFrame()
        self.footer.setObjectName("rmFooter")
        fl = QtWidgets.QHBoxLayout(self.footer)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.addStretch(1)
        self.manual_btn = QtWidgets.QPushButton(translate("Resolve_Mode", "Resolve manually"))
        self.manual_btn.setObjectName("rmBtn")
        self.manual_btn.setToolTip(
            translate("Resolve_Mode", "Open the first unresolved feature in its own FreeCAD editor")
        )
        self.manual_btn.clicked.connect(self._manual)
        self.accept_all_btn = QtWidgets.QPushButton()
        self.accept_all_btn.setObjectName("rmPrimary")
        self.accept_all_btn.clicked.connect(self._accept_all)
        fl.addWidget(self.manual_btn)
        fl.addWidget(self.accept_all_btn)
        outer.addWidget(self.footer)

        self.dock.setWidget(root)
        self.dock.setMinimumWidth(340)
        main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock)

    # ------------------------------------------------------------------

    def set_issues(self, doc_name: str | None, doc_label: str, issues: list[R.Issue], auto: bool):
        self.controller.clear_preview()
        self._checked_preview = None
        self._picking_card = None
        self.doc_name = doc_name
        self.issues = issues
        self.auto.blockSignals(True)
        self.auto.setChecked(auto)
        self.auto.blockSignals(False)

        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards = []

        th = self.theme
        ok = not issues
        self.header.setProperty("ok", "true" if ok else "false")
        self.header.style().unpolish(self.header)
        self.header.style().polish(self.header)
        self.header_title.style().unpolish(self.header_title)
        self.header_title.style().polish(self.header_title)
        if ok:
            self.header_icon.setPixmap(icons.icon("ok", th.ok, 22).pixmap(22, 22))
            self.header_title.setText(translate("Resolve_Mode", "No broken references"))
            msg = _label(
                translate("Resolve_Mode", "Everything in {doc} links to existing geometry.").format(doc=doc_label)
                if doc_name
                else translate("Resolve_Mode", "No document open."),
                "rmSub",
                wrap=True,
            )
            msg.setContentsMargins(14, 14, 14, 14)
            self.list_layout.addWidget(msg)
        else:
            self.header_icon.setPixmap(icons.icon("warning", th.danger, 22).pixmap(22, 22))
            self.header_title.setText(translate("Resolve_Mode", "Broken references ({n})").format(n=len(issues)))
            for issue in issues:
                card = Card(self, issue)
                self.cards.append(card)
                self.list_layout.addWidget(card)
        self.list_layout.addStretch(1)

        n_sugg = sum(1 for i in issues if i.verdict is not None and i.verdict.status == "suggest")
        self.accept_all_btn.setText(translate("Resolve_Mode", "Accept all suggested ({n})").format(n=n_sugg))
        self.accept_all_btn.setEnabled(n_sugg > 0)
        self.manual_btn.setEnabled(bool(issues))
        self.footer.setVisible(bool(issues))

    def set_busy(self, busy: bool):
        self.dock.widget().setEnabled(not busy)

    # -- actions -----------------------------------------------------------

    def preview(self, card: Card, button, element: str, on: bool):
        if on:
            if self._checked_preview is not None and self._checked_preview is not button:
                prev = self._checked_preview
                self._checked_preview = None
                prev.blockSignals(True)
                prev.setChecked(False)
                prev.blockSignals(False)
            self._checked_preview = button
            self.controller.preview(card.issue, element)
        elif self._checked_preview is button:
            self._checked_preview = None
            self.controller.clear_preview()

    def accept(self, fixes):
        self.controller.apply(fixes)

    def _accept_all(self):
        fixes = [
            (i.ref, i.verdict.best.name) for i in self.issues if i.verdict is not None and i.verdict.status == "suggest"
        ]
        if fixes:
            self.controller.apply(fixes)

    def _manual(self):
        if not self.issues:
            return
        pending = [i for i in self.issues if not i.ref.blocked]
        self.controller.edit_manually((pending or self.issues)[0])

    def start_pick(self, card: Card):
        if self._picking_card is not None and self._picking_card is not card:
            self._picking_card.set_picking(False)
        self._picking_card = card
        card.set_picking(True)
        self.controller.start_pick(card.issue, lambda hint: card.set_picking(True, hint))

    def pick_ended(self):
        if self._picking_card is not None:
            self._picking_card.set_picking(False)
            self._picking_card = None

    def on_closed(self):
        self.controller.on_panel_closed()
