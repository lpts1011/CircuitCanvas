"""Deterministic transient-data and schematic-image exports."""

from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QGraphicsScene

from circuitcanvas.solver.results import SimulationResult


def export_branch_csv(path: str | Path, result: SimulationResult, component_id: str) -> None:
    try:
        branch = result.branches[component_id]
    except KeyError:
        raise ValueError(f"No transient result exists for {component_id}") from None
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_s", "voltage_v", "current_a", "power_w", "energy_j"])
        writer.writerows(
            zip(
                result.time,
                branch.voltage,
                branch.current,
                branch.power,
                branch.energy,
                strict=True,
            )
        )


def export_scene_png(
    path: str | Path,
    scene: QGraphicsScene,
    *,
    transparent: bool = False,
    scale: float = 2.0,
) -> None:
    source = scene.itemsBoundingRect().adjusted(-36, -36, 36, 36)
    width = max(1, round(source.width() * scale))
    height = max(1, round(source.height() * scale))
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(scale)
    image.fill(Qt.GlobalColor.transparent if transparent else QColor("#f8fafc"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(painter, QRectF(0, 0, width / scale, height / scale), source)
    painter.end()
    if not image.save(str(path)):
        raise OSError(f"Could not write PNG to {path}")
