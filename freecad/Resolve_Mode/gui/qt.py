"""Qt compatibility in one place: FreeCAD's PySide shim plus shiboken validity."""

from PySide import QtCore, QtGui, QtWidgets  # noqa: F401  (re-exported)

try:
    from shiboken6 import isValid as _is_valid
except ImportError:  # Qt5 builds
    try:
        from shiboken2 import isValid as _is_valid
    except ImportError:

        def _is_valid(_obj):
            return True


def alive(widget) -> bool:
    """True if the Python wrapper still has a live C++ object behind it."""
    return widget is not None and _is_valid(widget)
