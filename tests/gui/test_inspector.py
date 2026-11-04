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


def _commit(qtbot, inspector: ComponentInspector, text: str) -> None:
    inspector.value_edit.setText(text)
    inspector.value_edit.editingFinished.emit()


def test_prefixed_input_overrides_the_unit_box(qtbot) -> None:
    inspector = ComponentInspector()
    qtbot.addWidget(inspector)
    inspector.set_component(Capacitor("C1", "a", "b", 47e-6))
    assert inspector.unit_combo.currentText() == "μF"

    with qtbot.waitSignal(inspector.value_changed) as signal:
        _commit(qtbot, inspector, "4.7n")

    assert signal.args == ["C1", pytest.approx(4.7e-9)]
    assert inspector.unit_combo.currentText() == "nF"
    assert inspector.value_edit.text() == "4.7"


@pytest.mark.parametrize(
    ("text", "expected"),
    [("4k7", 4700.0), ("4.7k", 4700.0), ("2.2 MΩ", 2.2e6), ("330 ohm", 330.0), ("1e3", 1e3)],
)
def test_resistor_accepts_engineering_notation(qtbot, text: str, expected: float) -> None:
    inspector = ComponentInspector()
    qtbot.addWidget(inspector)
    inspector.set_component(Resistor("R1", "a", "b", 100.0))

    with qtbot.waitSignal(inspector.value_changed) as signal:
        _commit(qtbot, inspector, text)

    assert signal.args == ["R1", pytest.approx(expected)]


def test_unreadable_or_unchanged_input_emits_nothing(qtbot) -> None:
    inspector = ComponentInspector()
    qtbot.addWidget(inspector)
    inspector.set_component(Resistor("R1", "a", "b", 100.0))
    received: list[float] = []
    inspector.value_changed.connect(lambda _id, value: received.append(value))

    _commit(qtbot, inspector, "lots")
    assert "Couldn't read" in inspector.error_label.text()

    _commit(qtbot, inspector, "100")
    assert received == []
    assert inspector.error_label.text() == ""


def test_slider_produces_three_significant_figures(qtbot) -> None:
    inspector = ComponentInspector()
    qtbot.addWidget(inspector)
    inspector.set_component(Resistor("R1", "a", "b", 100.0))
    values: list[float] = []
    inspector.value_adjusted.connect(lambda _id, value, _session: values.append(value))

    inspector.slider.setValue(inspector.slider.value() + 7)

    assert values
    assert float(f"{values[-1]:.3g}") == values[-1]


def test_empty_inspector_explains_what_to_do(qtbot) -> None:
    inspector = ComponentInspector()
    qtbot.addWidget(inspector)

    assert inspector.editor.isHidden()
    assert "Click a component" in inspector.empty_hint.text()
