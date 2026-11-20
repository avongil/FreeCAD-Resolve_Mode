"""Small line icons for the panel, tinted to the current theme at runtime."""

from __future__ import annotations

from .qt import QtCore, QtGui

_PATHS = {
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "hand": (
        '<path d="M9 11.5V4.8a1.6 1.6 0 0 1 3.2 0v5.7m0-1.2a1.6 1.6 0 0 1 3.2 0v1.6m0-.6a1.6 1.6 0 0 1 3.2 0'
        'V15a6.5 6.5 0 0 1-6.5 6.5h-.6a6.5 6.5 0 0 1-5.4-2.9L3.8 14.4a1.6 1.6 0 0 1 2.6-1.9L9 15.2"/>'
        '<path d="M5 3.5l1.2 1.2M3 7h1.6M14.5 3.5l-1 1"/>'
    ),
    "list": (
        '<path d="M9 6h12M9 12h12M9 18h12"/>'
        '<circle cx="4.5" cy="6" r=".9"/><circle cx="4.5" cy="12" r=".9"/><circle cx="4.5" cy="18" r=".9"/>'
    ),
    "bulb": (
        '<path d="M9.5 18h5M10.5 21h3M12 3a6 6 0 0 0-3.9 10.6c.7.7 1.1 1.5 1.1 2.4h5.6'
        'c0-.9.4-1.7 1.1-2.4A6 6 0 0 0 12 3z"/>'
        '<path d="M12 .8v.8M3.5 4.5l.6.6M20.5 4.5l-.6.6"/>'
    ),
    "alert": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.2v.3"/>',
    "warning": '<path d="M12 3.2L1.8 20.8h20.4L12 3.2z"/><path d="M12 10v4.8M12 17.6v.3"/>',
    "ok": '<circle cx="12" cy="12" r="9"/><path d="M7.8 12.3l2.9 2.9 5.5-5.6"/>',
    "refresh": '<path d="M20 12a8 8 0 1 1-2.4-5.7M20 4v5h-5"/>',
    "close": '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
}

_cache: dict[tuple[str, str, int], QtGui.QIcon] = {}


def icon(name: str, color: QtGui.QColor | str, size: int = 18) -> QtGui.QIcon:
    col = QtGui.QColor(color).name()
    key = (name, col, size)
    if key in _cache:
        return _cache[key]
    ico = QtGui.QIcon()
    for px in (size, size * 2):  # render each size natively so HiDPI stays sharp
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{col}" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'
            f"{_PATHS[name]}</svg>"
        )
        pix = QtGui.QPixmap()
        if pix.loadFromData(QtCore.QByteArray(svg.encode()), "SVG"):
            ico.addPixmap(pix)
    _cache[key] = ico
    return ico
