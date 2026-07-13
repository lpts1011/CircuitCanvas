import pytest
from PySide6.QtCore import Qt

from circuitcanvas.domain.components import Capacitor, Resistor
from circuitcanvas.ui.inspector import ComponentInspector


def test_capacitor_input_emits_si_value(qtbot) -> None:
    inspector = ComponentInspector()
    qtbot.addWidget(inspector)
    inspector.set_component(Capacitor("C1", "a", "b", 1e-6))
    inspector.unit_combo.setCurrentText("μF")
    inspector.value_edit.clear()
    qtbot.keyClicks(inspector.value_edit, "47")

    with qtbot.waitSignal(inspector.value_changed) as signal:
        qtbot.keyPress(inspector.value_edit, Qt.Key.Key_Return)

    assert signal.args == ["C1", pytest.approx(47e-6)]


def test_typed_value_is_not_rounded_by_slider_sync(qtbot) -> None:
    inspector = ComponentInspector()
    inspector.set_component(Resistor("R1", "a", "b", 123.4567))

    inspector.sync_slider_to_value()

    assert float(inspector.value_edit.text()) == pytest.approx(123.4567)


def test_delete_signal_carries_selected_id(qtbot) -> None:
    inspector = ComponentInspector()
    qtbot.addWidget(inspector)
    inspector.set_component(Resistor("R1", "a", "b", 100.0))

    with qtbot.waitSignal(inspector.delete_requested) as signal:
        inspector.delete_button.click()

    assert signal.args == ["R1"]
