"""Interactive ordinary and differential Kirchhoff equation browser."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from circuitcanvas.solver.equations import EquationLine, EquationReport


class EquationPanel(QWidget):
    equation_selected = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._report: EquationReport | None = None
        self._lines: dict[str, EquationLine] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        heading = QLabel("KIRCHHOFF EQUATIONS")
        heading.setStyleSheet("font-size:11px;font-weight:700;color:#64748b;letter-spacing:1px")
        layout.addWidget(heading)
        toggle = QHBoxLayout()
        self.ordinary_button = QPushButton("Ordinary")
        self.differential_button = QPushButton("Differential")
        for button in (self.ordinary_button, self.differential_button):
            button.setCheckable(True)
            toggle.addWidget(button)
        self.ordinary_button.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.ordinary_button)
        self.mode_group.addButton(self.differential_button)
        layout.addLayout(toggle)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumHeight(180)
        layout.addWidget(self.tree)
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMinimumHeight(180)
        self.detail.setStyleSheet("font-family:Menlo,monospace;font-size:11px")
        layout.addWidget(self.detail)

        self.tree.currentItemChanged.connect(self._tree_selection_changed)
        self.ordinary_button.clicked.connect(self._show_ordinary)
        self.differential_button.clicked.connect(self._show_differential)

    def set_report(self, report: EquationReport) -> None:
        self._report = report
        self._lines = {line.id: line for line in (*report.kcl, *report.kvl, *report.laws)}
        self.tree.clear()
        for title, lines in (
            ("KCL nodes", report.kcl),
            ("KVL loops", report.kvl),
            ("Element laws", report.laws),
        ):
            parent = QTreeWidgetItem([title])
            self.tree.addTopLevelItem(parent)
            for line in lines:
                child = QTreeWidgetItem(
                    [f"✓ {line.id}" if abs(line.residual) <= 1e-9 else f"⚠ {line.id}"]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, line.id)
                child.setForeground(
                    0,
                    Qt.GlobalColor.darkGreen if abs(line.residual) <= 1e-9 else Qt.GlobalColor.red,
                )
                parent.addChild(child)
            parent.setExpanded(True)
        if self.ordinary_button.isChecked() and self._lines:
            self.select_equation(next(iter(self._lines)))
        else:
            self._show_differential()

    def clear(self) -> None:
        self._report = None
        self._lines = {}
        self.tree.clear()
        self.detail.clear()

    def visible_text(self) -> str:
        return self.detail.toPlainText()

    def select_equation(self, equation_id: str) -> None:
        iterator = self.tree.invisibleRootItem()
        for parent_index in range(iterator.childCount()):
            parent = iterator.child(parent_index)
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                if child.data(0, Qt.ItemDataRole.UserRole) == equation_id:
                    self.tree.setCurrentItem(child)
                    return

    def reveal_component(self, component_id: str) -> None:
        for line in self._lines.values():
            if component_id in line.component_ids:
                self.select_equation(line.id)
                return

    def _tree_selection_changed(
        self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None
    ) -> None:
        del previous
        if current is None or not self.ordinary_button.isChecked():
            return
        equation_id = current.data(0, Qt.ItemDataRole.UserRole)
        line = self._lines.get(str(equation_id))
        if line is None:
            return
        self.detail.setPlainText("\n".join((line.symbolic, line.substituted, line.result)))
        self.equation_selected.emit(line)

    def _show_ordinary(self) -> None:
        current = self.tree.currentItem()
        if current is not None:
            self._tree_selection_changed(current, None)

    def _show_differential(self) -> None:
        if self._report is None:
            self.detail.clear()
            return
        self.detail.setPlainText(
            self._report.differential_text + "\n\n" + self._report.descriptor_text
        )
