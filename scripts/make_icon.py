"""Draw the CircuitCanvas app icon and write .icns, .ico, and PNG files.

Run from the repository root after changing the design:

    QT_QPA_PLATFORM=offscreen python scripts/make_icon.py

The icon is drawn with Qt, and the .icns/.ico containers are written directly
(both accept PNG-encoded images), so no macOS-only tools or Pillow are needed.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)

ASSETS = Path("assets/icon")
PACKAGE_ICON = Path("src/circuitcanvas/resources/icon.png")


def draw_icon(size: int = 1024) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 1024, size / 1024)

    # Rounded-square body inside Apple's 824 px icon grid.
    body = QRectF(100, 100, 824, 824)
    gradient = QLinearGradient(body.topLeft(), body.bottomLeft())
    gradient.setColorAt(0.0, QColor("#1e3a8a"))
    gradient.setColorAt(1.0, QColor("#0f172a"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(body, 185, 185)

    left, right, top, bottom = 250.0, 774.0, 330.0, 700.0
    wire = QPen(QColor("#e2e8f0"), 30, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    wire.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(wire)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Loop wires, leaving gaps for the battery (left), resistor (top), capacitor (bottom).
    painter.drawLine(QPointF(left, top), QPointF(392, top))
    painter.drawLine(QPointF(632, top), QPointF(right, top))
    painter.drawLine(QPointF(right, top), QPointF(right, bottom))
    painter.drawLine(QPointF(right, bottom), QPointF(540, bottom))
    painter.drawLine(QPointF(484, bottom), QPointF(left, bottom))
    painter.drawLine(QPointF(left, bottom), QPointF(left, 548))
    painter.drawLine(QPointF(left, 482), QPointF(left, top))

    # Resistor zigzag.
    resistor = QPainterPath(QPointF(392, top))
    for index, x in enumerate(range(412, 632, 40)):
        resistor.lineTo(x, top + (-46 if index % 2 == 0 else 46))
    resistor.lineTo(632, top)
    zigzag = QPen(QColor("#f87171"), 30, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    zigzag.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(zigzag)
    painter.drawPath(resistor)

    # Capacitor plates.
    painter.setPen(QPen(QColor("#fbbf24"), 30, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(QPointF(484, bottom - 62), QPointF(484, bottom + 62))
    painter.drawLine(QPointF(540, bottom - 62), QPointF(540, bottom + 62))

    # Battery: long positive plate above a short negative plate.
    painter.setPen(QPen(QColor("#60a5fa"), 30, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(QPointF(left - 78, 482), QPointF(left + 78, 482))
    painter.drawLine(QPointF(left - 42, 548), QPointF(left + 42, 548))

    # Current arrows flowing down the right-hand wire.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#22d3ee"))
    for y in (448.0, 578.0):
        painter.drawPolygon(
            QPolygonF(
                [QPointF(right, y + 40), QPointF(right - 38, y - 22), QPointF(right + 38, y - 22)]
            )
        )
    painter.end()
    return image


def png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError("Could not encode PNG")
    return bytes(data.data())


def scaled(master: QImage, size: int) -> QImage:
    return master.scaled(
        size,
        size,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def write_icns(path: Path, master: QImage) -> None:
    # PNG-backed ICNS element types and their pixel sizes.
    elements = (
        (b"icp4", 16),
        (b"icp5", 32),
        (b"ic11", 32),
        (b"ic12", 64),
        (b"ic07", 128),
        (b"ic08", 256),
        (b"ic13", 256),
        (b"ic09", 512),
        (b"ic14", 512),
        (b"ic10", 1024),
    )
    chunks = b""
    for kind, size in elements:
        data = png_bytes(scaled(master, size))
        chunks += kind + struct.pack(">I", len(data) + 8) + data
    path.write_bytes(b"icns" + struct.pack(">I", len(chunks) + 8) + chunks)


def write_ico(path: Path, master: QImage) -> None:
    sizes = (16, 24, 32, 48, 64, 128, 256)
    images = [png_bytes(scaled(master, size)) for size in sizes]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    directory = b""
    for size, data in zip(sizes, images, strict=True):
        dimension = 0 if size == 256 else size  # 0 means 256 in the ICO directory
        directory += struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.write_bytes(header + directory + b"".join(images))


def main() -> None:
    QGuiApplication([])
    master = draw_icon(1024)
    ASSETS.mkdir(parents=True, exist_ok=True)
    PACKAGE_ICON.parent.mkdir(parents=True, exist_ok=True)
    (ASSETS / "CircuitCanvas.png").write_bytes(png_bytes(master))
    write_icns(ASSETS / "CircuitCanvas.icns", master)
    write_ico(ASSETS / "CircuitCanvas.ico", master)
    PACKAGE_ICON.write_bytes(png_bytes(scaled(master, 256)))
    for path in (*sorted(ASSETS.iterdir()), PACKAGE_ICON):
        print(f"{path}  {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
