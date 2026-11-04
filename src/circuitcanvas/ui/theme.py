"""Shared colors and the application style sheet.

Voltage is always blue and current always orange: on the canvas, in the readings,
and in the graphs, so a number's color tells you what it measures.
"""

from __future__ import annotations

ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
VOLTAGE = "#2563eb"
VOLTAGE_BG = "#eff6ff"
VOLTAGE_TEXT = "#1e40af"
CURRENT = "#ea580c"
CURRENT_BG = "#fff7ed"
CURRENT_TEXT = "#9a3412"
TEXT = "#0f172a"
TEXT_SECONDARY = "#475569"
TEXT_MUTED = "#64748b"
BORDER = "#e2e8f0"
BORDER_STRONG = "#cbd5e1"
SURFACE = "#ffffff"
SURFACE_MUTED = "#f8fafc"
WINDOW = "#f1f5f9"
DANGER = "#dc2626"
DANGER_BG = "#fef2f2"
SUCCESS_TEXT = "#166534"
SUCCESS_BG = "#f0fdf4"
WARNING_TEXT = "#9a3412"
WARNING_BG = "#fff7ed"
WARNING_BORDER = "#fdba74"
INFO_TEXT = "#1e40af"
INFO_BG = "#eff6ff"
INFO_BORDER = "#bfdbfe"

COMPONENT_COLORS = {
    "resistor": ("#ef4444", "#fff7f7"),
    "capacitor": ("#f59e0b", "#fffbeb"),
    "inductor": ("#8b5cf6", "#faf5ff"),
}

KIND_NAMES = {
    "resistor": "Resistor",
    "capacitor": "Capacitor",
    "inductor": "Inductor",
}

STYLESHEET = f"""
QMainWindow {{ background: {WINDOW}; }}
QLabel {{ background: transparent; }}

QToolBar#mainToolbar {{
    background: {SURFACE}; border: 0; border-bottom: 1px solid {BORDER};
    padding: 5px 10px; spacing: 4px;
}}
QToolBar#mainToolbar QToolButton {{
    border: 1px solid transparent; border-radius: 6px; padding: 5px;
}}
QToolBar#mainToolbar QToolButton:hover {{ background: {WINDOW}; }}
QToolButton#playButton {{
    background: {ACCENT}; color: white; font-weight: 600;
    border-radius: 6px; padding: 5px 12px 5px 8px;
}}
QToolButton#playButton:hover {{ background: {ACCENT_HOVER}; }}
QToolButton#playButton:disabled {{ background: {BORDER_STRONG}; color: white; }}

#rail, #sidePanel, #graphPanel {{ background: {SURFACE}; }}
#rail {{ border-right: 1px solid {BORDER}; }}
#sidePanel {{ border-left: 1px solid {BORDER}; }}
#graphPanel {{ border-top: 1px solid {BORDER}; }}
QLabel#sectionTitle {{ font-weight: 600; color: {TEXT}; }}
QLabel#muted {{ color: {TEXT_MUTED}; }}
QLabel#hint {{ color: {TEXT_MUTED}; font-size: 11px; }}

QLineEdit, QComboBox, QDoubleSpinBox {{
    background: {SURFACE}; border: 1px solid {BORDER_STRONG};
    border-radius: 6px; padding: 5px 7px; color: {TEXT};
}}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {{ border-color: {ACCENT}; }}
QPushButton {{
    background: {SURFACE}; border: 1px solid {BORDER_STRONG};
    border-radius: 6px; padding: 6px 10px; color: {TEXT};
}}
QPushButton:hover {{ background: {SURFACE_MUTED}; border-color: #94a3b8; }}
QPushButton:checked {{ background: {INFO_BG}; border-color: {ACCENT}; color: {ACCENT}; }}

QTabWidget::pane {{ border: 0; border-top: 1px solid {BORDER}; background: {SURFACE}; }}
QTabBar::tab {{
    padding: 8px 14px; background: transparent; color: {TEXT_SECONDARY};
    border: 0; border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}

QSplitter::handle {{ background: {BORDER}; }}
QStatusBar {{ background: {SURFACE}; border-top: 1px solid {BORDER}; color: {TEXT_SECONDARY}; }}
QStatusBar::item {{ border: 0; }}

QFrame#card {{ background: {SURFACE_MUTED}; border-radius: 8px; }}
QFrame#voltageCard {{ background: {VOLTAGE_BG}; border-radius: 8px; }}
QFrame#currentCard {{ background: {CURRENT_BG}; border-radius: 8px; }}
QFrame#statusCard[kind="ok"] {{
    background: {SUCCESS_BG}; border: 1px solid #bbf7d0; border-radius: 8px;
}}
QFrame#statusCard[kind="problem"] {{
    background: {WARNING_BG}; border: 1px solid {WARNING_BORDER}; border-radius: 8px;
}}
QFrame#statusCard[kind="info"] {{
    background: {INFO_BG}; border: 1px solid {INFO_BORDER}; border-radius: 8px;
}}
QFrame#banner[kind="problem"] {{
    background: {WARNING_BG}; border: 1px solid {WARNING_BORDER}; border-radius: 8px;
}}
QFrame#banner[kind="info"] {{
    background: {INFO_BG}; border: 1px solid {INFO_BORDER}; border-radius: 8px;
}}
QFrame#canvasControls {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
}}
QFrame#canvasControls QToolButton {{ border: 0; border-radius: 6px; padding: 4px; }}
QFrame#canvasControls QToolButton:hover {{ background: {WINDOW}; }}

QToolButton#segment {{
    border: 1px solid {BORDER_STRONG}; padding: 4px 12px; color: {TEXT_SECONDARY};
    background: {SURFACE};
}}
QToolButton#segment:checked {{ background: {INFO_BG}; color: {ACCENT}; border-color: {ACCENT}; }}

QToolButton#paletteButton {{
    border: 1px solid {BORDER}; border-radius: 8px; padding: 6px 2px;
    background: {SURFACE}; color: {TEXT}; font-size: 11px;
}}
QToolButton#paletteButton:hover {{ background: {INFO_BG}; border-color: {ACCENT}; }}
"""
